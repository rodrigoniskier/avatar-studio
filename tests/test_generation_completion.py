import ast
import importlib.util
import json
import subprocess
import sys
import types
import wave
from pathlib import Path

import pytest
import torch
from fastapi.testclient import TestClient
from safetensors.torch import save_file

from studio import config, consent, jobs, media, pipeline, resources, telemetry
from studio.api import app
from studio.engines.checkpoint_loading import assign_shards, assign_torch_checkpoint
from studio.engines.upstream_compat import build_overlay, build_preprocess_overlay, patched_source

ROOT = Path(__file__).parents[1]


def ffmpeg(*args):
    subprocess.run(["ffmpeg", "-y", "-v", "error", *map(str, args)], check=True)


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(config, "MODELS", tmp_path / "models")
    monkeypatch.setattr(config, "ACCESS_TOKEN", "")
    monkeypatch.setattr(config, "INFINITETALK_QUANT", "none")


def test_sharded_meta_loading_matches_full_load_and_applies_adapter(tmp_path):
    baseline = torch.nn.Sequential(torch.nn.Linear(3, 4), torch.nn.Linear(4, 2)).eval()
    state = baseline.state_dict()
    state["1.bias"] = torch.tensor([.5, -.7])
    baseline.load_state_dict(state)
    save_file({k:v for k,v in state.items() if k.startswith("0.")}, tmp_path/"base1.safetensors")
    save_file({k:torch.zeros_like(v) for k,v in state.items() if k.startswith("1.")}, tmp_path/"base2.safetensors")
    save_file({k:v for k,v in state.items() if k.startswith("1.")}, tmp_path/"adapter.safetensors")
    with torch.device("meta"):
        model = torch.nn.Sequential(torch.nn.Linear(3, 4), torch.nn.Linear(4, 2)).eval()
    assign_shards(model, [tmp_path/n for n in ("base1.safetensors", "base2.safetensors", "adapter.safetensors")])
    x = torch.randn(8, 3)
    torch.testing.assert_close(model(x), baseline(x))
    assert not any(p.is_meta for p in model.parameters())


@pytest.mark.parametrize("problem", ["missing", "shape", "unexpected"])
def test_shard_loading_fails_closed_for_incompatible_weights(tmp_path, problem):
    state = {"weight": torch.ones(2,3), "bias": torch.ones(2)}
    if problem == "missing": del state["bias"]
    if problem == "shape": state["weight"] = torch.ones(4,3)
    if problem == "unexpected": state["unknown"] = torch.ones(1)
    path = tmp_path/"bad.safetensors"; save_file(state, path)
    with torch.device("meta"): model = torch.nn.Linear(3,2)
    with pytest.raises(RuntimeError): assign_shards(model, [path])


@pytest.mark.parametrize("legacy", [False,True])
def test_torch_checkpoint_is_mapped_and_cast_without_initialized_model(tmp_path, monkeypatch, legacy):
    original = torch.nn.Linear(3, 2)
    path = tmp_path/"t5.pt"; torch.save(original.state_dict(), path, _use_new_zipfile_serialization=not legacy)
    with torch.device("meta"): model = torch.nn.Linear(3,2,dtype=torch.float16)
    load = torch.load; observed = []
    def capture(*a, **kw):
        observed.append(kw)
        return load(*a, **kw)
    monkeypatch.setattr(torch, "load", capture)
    assign_torch_checkpoint(model, path)
    assert observed[0]["mmap"]== (not legacy) and observed[0]["weights_only"]
    assert all(p.device.type=="cpu" and p.dtype==torch.float16 for p in model.parameters())
    torch.testing.assert_close(model.weight, original.weight.half())


@pytest.mark.parametrize("upstream", ["InfiniteTalk", "Wan2.2"])
def test_actual_t5_constructor_loads_meta_checkpoint_on_cpu(tmp_path, upstream):
    source = (ROOT/"upstreams"/upstream/"wan/modules/t5.py").read_text()
    tree = ast.parse(patched_source(source, "modules/t5.py", False))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name=="T5EncoderModel")
    init = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name=="__init__")
    # A default argument probes CUDA at definition time in the upstream; use CPU in this test.
    init.args.defaults = [ast.parse("'cpu'", mode="eval").body if isinstance(n,ast.Call)
                          and "current_device" in ast.unparse(n) else n for n in init.args.defaults]
    created=[]
    def tiny(**kw):
        created.append(kw["device"])
        return torch.nn.Linear(3,2,device=kw["device"],dtype=kw["dtype"])
    scope={"torch":torch,"umt5_xxl":tiny,"avatar_assign_checkpoint":assign_torch_checkpoint,
           "logging":types.SimpleNamespace(info=lambda *a:None),"HuggingfaceTokenizer":lambda **kw:None}
    ast.fix_missing_locations(cls)
    exec(compile(ast.Module(body=[cls],type_ignores=[]),"actual-t5","exec"),scope)
    original=torch.nn.Linear(3,2); path=tmp_path/"weights.pt";torch.save(original.state_dict(),path)
    instance=scope["T5EncoderModel"](text_len=10,dtype=torch.float32,device="cpu",checkpoint_path=path)
    assert created==["meta"]
    torch.testing.assert_close(instance.model.weight,original.weight)


def test_infinite_overlay_keeps_identity_and_seeds_only_first_motion(tmp_path):
    build_overlay(ROOT/"upstreams/InfiniteTalk", tmp_path/"overlay", fp16=True)
    code=(tmp_path/"overlay/wan/multitalk.py").read_text()
    assert "assign_shards" in code and "merged_state_dict" not in code
    tree=ast.parse(code)
    condition=next(n for n in ast.walk(tree) if isinstance(n,ast.If)
                   and ast.unparse(n.test)=="is_first_clip" and "initial_frame" in ast.unparse(n))
    encoded=[]
    scope={"input_data":{"initial_frame":"last.png"},"is_first_clip":True,
           "self":types.SimpleNamespace(device="cpu",vae=types.SimpleNamespace(encode=lambda x:encoded.append(x) or [x])),
           "extract_specific_frames":lambda path,index:torch.full((1,3,1,2,2),255.),
           "resize_and_centercrop":lambda x,shape:x,"target_h":2,"target_w":2,"cond_image":torch.zeros(1,3,1,2,2)}
    exec(compile(ast.Module(body=[condition],type_ignores=[]),"first-motion","exec"),scope)
    assert torch.all(encoded[0]==1)
    assert torch.all(scope["cond_image"]==0)  # identity conditioning was not replaced
    entry=patched_source((ROOT/"upstreams/InfiniteTalk/generate_infinitetalk.py").read_text(),"generate_infinitetalk.py",True)
    assert "input_clip['initial_frame'] = input_data.get('initial_frame')" in entry


def test_wan_retarget_imports_do_not_require_sam_or_flux(tmp_path):
    build_preprocess_overlay(ROOT/"upstreams/Wan2.2", tmp_path/"preprocess")
    tree=ast.parse((tmp_path/"preprocess/process_pipepline.py").read_text())
    top="\n".join(ast.unparse(n) for n in tree.body if not isinstance(n,ast.ClassDef))
    assert "sam2" not in top and "sam_utils" not in top and "FluxKontextPipeline" not in top
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef))
    scope={"Pose2d":lambda **kw:"pose"}
    exec(compile(ast.Module(body=[cls],type_ignores=[]),"actual-preprocessor","exec"),scope)
    instance=scope["ProcessPipeline"]("det","pose",None,None)
    assert instance.pose2d=="pose" and not hasattr(instance,"predictor")


@pytest.mark.parametrize("seconds", [.15, 3, 3.24, 4])
def test_infinite_short_audio_padding_preserves_approved_master(tmp_path, seconds):
    original=tmp_path/"approved.wav"
    ffmpeg("-f","lavfi","-i",f"sine=sample_rate=16000:duration={seconds}",original)
    before=original.read_bytes()
    result=media.inference_audio(original,tmp_path/"padded.wav")
    assert original.read_bytes()==before
    assert media.duration(result)>=3.4
    if seconds>=3.4: assert result==original
    else:
        with wave.open(str(result),"rb") as reader, wave.open(str(original),"rb") as master:
            assert reader.readframes(master.getnframes())==master.readframes(master.getnframes())
            assert set(reader.readframes(reader.getnframes()))<={0}


def make_profile():
    folder=config.profile_dir("eu");consent.register(folder,"eu")
    (folder/"voice.wav").write_bytes(b"reference")
    (folder/"avatar.mp4").write_bytes(b"video")
    (folder/"identity.png").write_bytes(b"original-identity")
    return folder


def test_continuity_resumes_and_invalidates_following_scene_on_previous_change(tmp_path,monkeypatch):
    folder=make_profile();jdir=config.job_dir("continuity");jdir.mkdir(parents=True)
    audio=jdir/"speech.wav";ffmpeg("-f","lavfi","-i","sine=duration=7",audio)
    monkeypatch.setattr(config,"SCENE_SECONDS",5)
    seen=[]
    class Engine:
        def render(self,identity,motion,speech,prompt,out,seed,*,initial_frame=None):
            assert identity==folder/"identity.png"
            seen.append(initial_frame)
            if initial_frame: assert media.probe(initial_frame)["streams"][0]["width"]==64
            ffmpeg("-f","lavfi","-i",f"color=c=blue:s=64x64:r=25:d={media.duration(speech)}","-c:v","libx264",out)
    monkeypatch.setattr(pipeline,"get_video",lambda name:Engine())
    for _ in range(2): pipeline._render_scenes(folder,jdir,audio,jdir/"out.mp4","avatar","","last_frame")
    assert len(seen)==2 and seen[0] is None and seen[1] is not None
    # Simulate a replaced, valid preceding scene and refresh its stamp. Dependency must invalidate scene 2.
    first=jdir/"scenes/scene0000.mp4"; prior=json.loads(first.with_suffix(".ready.json").read_text())
    ffmpeg("-f","lavfi","-i","color=c=red:s=64x64:r=25:d=5","-i",jdir/"scenes/scene0000.wav","-c:v","libx264","-crf","0","-c:a","aac",first)
    prior["sha256"]=pipeline.digest(first);pipeline.write_json(first.with_suffix(".ready.json"),prior)
    pipeline._render_scenes(folder,jdir,audio,jdir/"out.mp4","avatar","","last_frame")
    assert len(seen)==3 and seen[-1] is not None
    assert media.duration(jdir/"out.mp4")==pytest.approx(7,abs=.1)


def test_job_image_and_continuity_are_saved_without_changing_profile(tmp_path,monkeypatch):
    folder=make_profile()
    monkeypatch.setattr(resources,"require",lambda name:{"ok":True})
    client=TestClient(app,base_url="http://localhost")
    response=client.post("/jobs",data={"profile":"eu","text":"Olá","mode":"avatar","continuity":"last_frame"},
                         files={"image":("new.png",b"new-scene","image/png")})
    assert response.status_code==200,response.text
    jid=response.json()["job_id"]
    assert (config.job_dir(jid)/"identity.png").read_bytes()==b"new-scene"
    assert (folder/"identity.png").read_bytes()==b"original-identity"
    assert json.loads(jobs.get(jid)["request"])["continuity"]=="last_frame"
    bad=client.post("/jobs",data={"profile":"eu","text":"Olá","mode":"dub","continuity":"last_frame"})
    assert bad.status_code==400


def test_failed_scene_upload_does_not_leave_orphan_job(monkeypatch):
    make_profile();monkeypatch.setattr(resources,"require",lambda name:{"ok":True})
    def bad(*a,**kw): raise ValueError("Imagem inválida")
    monkeypatch.setattr(media,"prepare_image",bad)
    client=TestClient(app,base_url="http://localhost")
    response=client.post("/jobs",data={"profile":"eu","text":"Olá","mode":"avatar"},files={"image":("bad.png",b"broken")})
    assert response.status_code==400
    assert jobs.list_all()==[] and list((config.DATA_DIR/"jobs").iterdir())==[]


def test_telemetry_preserves_failure_and_reports_real_sample_scope(tmp_path,monkeypatch):
    monkeypatch.setattr(resources,"snapshot",lambda:{"available_ram_gb":8,"gpus":[{"free_gb":5}]})
    target=tmp_path/"performance.json"
    with pytest.raises(RuntimeError,match="OOM"):
        with telemetry.measure(target,{"mode":"avatar"}): raise RuntimeError("OOM")
    report=json.loads(target.read_text())
    assert report["state"]=="failed" and report["error"].endswith("OOM")
    assert report["min_free_vram_gib"]==5 and report["min_available_ram_gib"]==8
    assert "not process peak" in report["scope"]


def test_video_requirements_exclude_unused_cuda_build_but_keep_pose_runtime():
    spec=importlib.util.spec_from_file_location("video_requirements",ROOT/"scripts/video_requirements.py")
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    text=module.prepare("wan-animate",ROOT)
    assert "sam2.git" not in text and "flash_attn" not in text
    assert "onnxruntime" in text and "peft" in text
    assert "librosa" in text and "setuptools" in text


def test_cgroup_memory_limit_overrides_host_available_ram(monkeypatch):
    read=Path.read_text
    def contents(path,*a,**kw):
        values={"/proc/meminfo":"MemAvailable: 134217728 kB", "/sys/fs/cgroup/memory.max":str(4*1024**3),
                "/sys/fs/cgroup/memory.current":str(1024**3)}
        return values[str(path)] if str(path) in values else read(path,*a,**kw)
    monkeypatch.setattr(Path,"read_text",contents)
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES","-1")
    assert resources.snapshot()["available_ram_gb"]==3


def test_last_frame_is_the_actual_end_not_the_first_frame(tmp_path):
    video=tmp_path/"colors.mp4"; image=tmp_path/"last.png"
    ffmpeg("-f","lavfi","-i","color=c=red:s=32x32:r=25:d=1",
           "-f","lavfi","-i","color=c=blue:s=32x32:r=25:d=1",
           "-filter_complex","[0:v][1:v]concat=n=2:v=1:a=0","-c:v","libx264",video)
    media.last_frame(video,image)
    pixels=subprocess.check_output(["ffmpeg","-v","error","-i",str(image),"-pix_fmt","rgb24","-f","rawvideo","-"])
    assert pixels[2]>240 and pixels[0]<10 and pixels[1]<10


@pytest.mark.parametrize("quant", ["none","fp8"])
def test_adapter_short_tail_and_fp8_contract_keep_reference_and_approved_audio(tmp_path,monkeypatch,quant):
    from studio.engines import generative
    monkeypatch.setattr(resources,"require",lambda name:{"ok":True})
    monkeypatch.setattr(config,"INFINITETALK_QUANT",quant)
    monkeypatch.setattr(config,"UPSTREAMS",tmp_path/"upstreams")
    monkeypatch.setattr(config,"venv_python",lambda name:"python")
    repo=config.UPSTREAMS/"InfiniteTalk";repo.mkdir(parents=True);(repo/"generate_infinitetalk.py").touch()
    root=config.MODELS/"infinitetalk"
    for folder in ("Wan2.1-I2V-14B-480P","chinese-wav2vec2-base","InfiniteTalk/single","InfiniteTalk/quant_models"):
        (root/folder).mkdir(parents=True)
    (root/"InfiniteTalk/single/infinitetalk.safetensors").touch()
    for name in ("infinitetalk_single_fp8.safetensors","infinitetalk_single_fp8.json","t5_fp8.safetensors","t5_map_fp8.json"):
        (root/"InfiniteTalk/quant_models"/name).touch()
    audio=tmp_path/"speech.wav";ffmpeg("-f","lavfi","-i","sine=duration=0.2",audio)
    before=audio.read_bytes();identity=tmp_path/"identity.png";identity.touch();initial=tmp_path/"initial.png";initial.touch()
    out=tmp_path/"out.mp4";calls=[]
    def run(cmd,cwd=None): calls.append(cmd);out.touch()
    monkeypatch.setattr(generative,"run_logged",run)
    generative.InfiniteTalk().render(identity,None,audio,"quiet",out,42,initial_frame=initial)
    task=json.loads(out.with_suffix(".json").read_text())
    assert task["cond_video"]==str(identity) and task["initial_frame"]==str(initial)
    assert task["cond_audio"]["person1"]!=str(audio)
    assert media.duration(Path(task["cond_audio"]["person1"]))>=3.4 and audio.read_bytes()==before
    assert ("--quant" in calls[0])==(quant=="fp8")


def load_download_script(monkeypatch, files):
    fake=types.ModuleType("huggingface_hub")
    class API:
        def model_info(self,repo,**kw):
            names=files if repo=="MeiGen-AI/InfiniteTalk" else ["config.json","model.safetensors"]
            return types.SimpleNamespace(sha="fixed",siblings=[types.SimpleNamespace(rfilename=n,size=1000) for n in names])
    fake.HfApi=API;fake.snapshot_download=lambda **kw:None;fake.hf_hub_download=lambda *a,**kw:None
    monkeypatch.setitem(sys.modules,"huggingface_hub",fake)
    spec=importlib.util.spec_from_file_location("download_fp8_test",ROOT/"scripts/download_generative_weights.py")
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.QUANT="fp8"
    return module


def test_fp8_plan_requires_both_models_and_maps_before_download(tmp_path,monkeypatch):
    names=["quant_models/"+n for n in ("infinitetalk_single_fp8.safetensors","infinitetalk_single_fp8.json","t5_fp8.safetensors","t5_map_fp8.json")]
    module=load_download_script(monkeypatch,names);module.ROOT=tmp_path
    plans=module.plan("infinitetalk")
    assert set(names)<=set(plans[2]["patterns"])
    assert "models_t5_umt5-xxl-enc-bf16.pth" in plans[0]["excluded"]
    assert plans[1]["audio_encoder_revision"]=="fixed"
    module=load_download_script(monkeypatch,names[:-1]);module.ROOT=tmp_path
    with pytest.raises(SystemExit,match="FP8 incompleto"): module.plan("infinitetalk")


def test_cli_holds_same_lock_as_queue_and_propagates_lease(monkeypatch):
    from studio import cli
    from studio.lease import worker_lease
    observed=[]
    def generate(*a,**kw):
        observed.append(worker_lease.get())
        jobs.enqueue({"profile":"eu","text":"fala","lang":"pt"})
        assert not jobs.drain_one()
        return "speech.wav"
    monkeypatch.setattr(pipeline,"generate",generate)
    monkeypatch.setattr(sys,"argv",["studio","generate","eu","fala"])
    cli.main()
    assert observed[0] is not None and worker_lease.get() is None


def test_cli_cannot_start_inference_while_worker_lease_is_held(monkeypatch):
    from studio import cli
    from studio.lease import inference_lease
    monkeypatch.setattr(sys,"argv",["studio","generate","eu","fala"])
    monkeypatch.setattr(pipeline,"generate",lambda *a,**kw:pytest.fail("Must not start another inference"))
    with inference_lease(), pytest.raises(ValueError,match="Outro trabalho"):
        cli.main()
