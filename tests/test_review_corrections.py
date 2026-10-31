import ast
import fcntl
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from studio import config, media, pipeline, resources, quality, audio_quality, jobs
from studio.api import app
from studio.engines import musetalk_lipsync as muse
from studio.engines.qwen_tts import QwenTTS


@pytest.fixture(autouse=True)
def isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(config,"DATA_DIR",tmp_path/"data")
    monkeypatch.setattr(config,"MODELS",tmp_path/"models")
    monkeypatch.setattr(config,"TTS_ENGINE","mock")
    monkeypatch.setattr(config,"LIPSYNC_ENGINE","mock")
    monkeypatch.setattr(config,"ACCESS_TOKEN","")
    monkeypatch.delenv("STUDIO_TRANSCRIBE",raising=False)


def run_ffmpeg(*args):
    subprocess.run(["ffmpeg","-y","-v","error",*map(str,args)],check=True)


def profile():
    from studio import consent
    folder=config.profile_dir("eu")
    consent.register(folder,"eu")
    (folder/"voice.wav").write_bytes(b"reference")
    (folder/"avatar.mp4").write_bytes(b"video")
    (folder/"identity.png").write_bytes(b"image")
    return folder


@pytest.mark.parametrize("seconds",[1.5,3,4.8,7,12,15])
def test_generated_scene_keeps_full_length_and_skips_segment_selection(tmp_path,monkeypatch,seconds):
    # Real FFmpeg and the actual pinned MuseTalk inference source; neural call is substituted.
    base=tmp_path/"base.mp4"; audio=tmp_path/"audio.wav"; out=tmp_path/"out.mp4"
    run_ffmpeg("-f","lavfi","-i",f"color=s=64x64:r=25:d={seconds}","-c:v","libx264",base)
    run_ffmpeg("-f","lavfi","-i",f"sine=duration={seconds}",audio)
    repo=Path(__file__).parents[1]/"upstreams/MuseTalk"
    assert (repo/"scripts/inference.py").exists()
    fakeup=tmp_path/"upstreams"; fakeup.mkdir(); (fakeup/"MuseTalk").symlink_to(repo,target_is_directory=True)
    monkeypatch.setattr(config,"UPSTREAMS",fakeup)
    monkeypatch.setattr(config,"venv_python",lambda name:sys.executable)
    monkeypatch.setattr(muse,"pick_segment",lambda *a,**k:pytest.fail("Generated motion must not be selected/cropped"))
    def infer(cmd,cwd=None,**kwargs):
        task=Path(cmd[cmd.index("--inference_config")+1])
        prepared=task.parent/"base.mp4"
        assert prepared.read_bytes()==base.read_bytes()
        assert media.duration(prepared)==pytest.approx(seconds,abs=.05)
        code=Path(cmd[1]).read_text()
        assert "frame_list + frame_list[::-1]" not in code
        assert "_forward_frames(frame_list, len(whisper_chunks))" in code
        result=Path(cmd[cmd.index("--result_dir")+1]);result.mkdir()
        (result/"generated.mp4").write_bytes(b"inference-result")
        return []
    monkeypatch.setattr(muse,"run_logged",infer)
    muse.MuseTalk().render(base,audio,out,preserve_motion=True)
    assert out.read_bytes()==b"inference-result"


def test_generated_motion_padding_is_last_frame_only():
    tree=ast.parse(muse.HELPER)
    function=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=="_forward_frames")
    scope={}
    exec(compile(ast.Module(body=[function],type_ignores=[]),"helper","exec"),scope)
    assert scope["_forward_frames"]([0,1,2],5)==[0,1,2,2,2]
    with pytest.raises(RuntimeError):scope["_forward_frames"]([0,1,2],6)


def test_short_driving_video_rejected_before_any_neural_call(tmp_path,monkeypatch):
    folder=profile();jdir=config.job_dir("shortmotion");jdir.mkdir(parents=True)
    audio=jdir/"speech.wav"; motion=jdir/"motion.mp4"
    run_ffmpeg("-f","lavfi","-i","sine=duration=12",audio)
    run_ffmpeg("-f","lavfi","-i","color=s=64x64:r=25:d=7","-c:v","libx264",motion)
    class Engine:
        def render(self,*a,**kw):pytest.fail("No GPU work should happen before validation")
    monkeypatch.setattr(pipeline,"get_video",lambda name:Engine())
    with pytest.raises(ValueError,match="cobrir toda a fala"):
        pipeline._render_scenes(folder,jdir,audio,jdir/"out.mp4","motion","")
    assert not (jdir/"scenes").exists()


@pytest.mark.parametrize("origin",["https://evil.example","null","http://[bad"])
def test_cross_origin_local_post_denied_without_token(origin):
    client=TestClient(app,base_url="http://localhost")
    response=client.post("/jobs",data={"profile":"eu","text":"text"},headers={"Origin":origin})
    assert response.status_code==403


def test_dns_rebinding_host_denied_without_token():
    client=TestClient(app,base_url="http://attacker.example")
    assert client.get("/profiles").status_code==403


def test_non_ascii_token_returns_401_not_500(monkeypatch):
    monkeypatch.setattr(config,"ACCESS_TOKEN","private")
    client=TestClient(app,base_url="http://localhost")
    assert client.get("/profiles",headers={b"authorization":b"Bearer \xff"}).status_code==401


def test_same_origin_post_still_reaches_validation():
    client=TestClient(app,base_url="http://localhost")
    assert client.post("/jobs",headers={"Origin":"http://localhost"}).status_code==422


def test_env_autoload_preserves_exported_values(tmp_path):
    (tmp_path/".env").write_text('STUDIO_TTS=qwen3\nSTUDIO_VIDEO_SIZE="720"\n')
    env={**os.environ,"PYTHONPATH":str(Path(__file__).parents[1]),"STUDIO_TTS":"mock"}
    env.pop("STUDIO_VIDEO_SIZE",None)
    result=subprocess.run([sys.executable,"-c","from studio import config;print(config.TTS_ENGINE,config.VIDEO_SIZE)"],
                           cwd=tmp_path,env=env,capture_output=True,text=True,check=True)
    assert result.stdout.strip()=="mock 720"


def test_qwen_requested_model_must_match_installed_manifest(tmp_path):
    root=config.MODELS/"qwen3";root.mkdir(parents=True)
    (root/"config.json").write_text("{}")
    (root/"download.json").write_text(json.dumps({"repo":"Qwen/Qwen3-TTS-12Hz-0.6B-Base"}))
    ref=tmp_path/"voice.wav";ref.touch();ref.with_suffix(".txt").write_text("Reference")
    assert config.QWEN_MODEL!="Qwen/Qwen3-TTS-12Hz-0.6B-Base"
    with pytest.raises(ValueError,match="difere de STUDIO_QWEN_MODEL"):
        QwenTTS().validate_reference(ref)


def test_manual_weight_replacement_invalidates_cache(monkeypatch):
    profile();monkeypatch.setattr(config,"TTS_ENGINE","qwen3")
    root=config.MODELS/"qwen3";root.mkdir(parents=True)
    weights=root/"model.safetensors";weights.write_bytes(b"old-model")
    before=pipeline.speech_key("eu","text","pt")
    weights.write_bytes(b"new-model-same-size")
    assert pipeline.speech_key("eu","text","pt")!=before


def test_dirty_upstream_source_invalidates_cache(tmp_path,monkeypatch):
    profile();up=tmp_path/"upstreams";repo=up/"chatterbox";repo.mkdir(parents=True)
    subprocess.run(["git","init","-q",str(repo)],check=True)
    monkeypatch.setattr(config,"UPSTREAMS",up)
    source=repo/"worker.py";source.write_text("x=1")
    first=pipeline.speech_key("eu","text","pt")
    source.write_text("x=2")
    assert pipeline.speech_key("eu","text","pt")!=first


@pytest.mark.parametrize("engine,ram,gpu,expected",[("infinitetalk",29,16,False),("wan-animate",64,16,False),
                                                   ("infinitetalk",50,16,True),("wan-animate",66,25,True)])
def test_conservative_resource_budget(engine,ram,gpu,expected):
    report=resources.check(engine,{"available_ram_gb":ram,"gpus":[{"free_gb":gpu}]})
    assert report["ok"] is expected


def test_configuration_mismatch_is_not_retryable(monkeypatch):
    profile();jid=jobs.enqueue({"profile":"eu","text":"Text","lang":"pt"})
    jobs.drain_one()
    with jobs.database() as db:db.execute("UPDATE jobs SET status='error' WHERE id=?",(jid,))
    monkeypatch.setattr(config,"SEED",config.SEED+1)
    with pytest.raises(ValueError,match="novo trabalho"):jobs.retry(jid)


def test_signal_warnings_are_reported_for_saturation_and_long_pause(tmp_path):
    import wave,array
    audio=tmp_path/"clip.wav"
    values=array.array("h",[32767,-32768]*8000+[0]*32000+[500,-500]*8000)
    with wave.open(str(audio),"wb") as writer:
        writer.setnchannels(1);writer.setsampwidth(2);writer.setframerate(16000);writer.writeframes(values.tobytes())
    report=audio_quality.inspect(audio,"Text","pt")
    assert any("Saturação" in x for x in report["warnings"])
    assert report["longest_silence_seconds"]>=2
    assert any("pausas" in x for x in report["warnings"])


def test_black_and_static_video_is_flagged_as_manual_review(tmp_path):
    audio=tmp_path/"a.wav";video=tmp_path/"v.mp4"
    run_ffmpeg("-f","lavfi","-i","sine=duration=2",audio)
    run_ffmpeg("-f","lavfi","-i","color=c=black:s=64x64:r=25:d=2","-i",audio,"-c:v","libx264","-c:a","aac",video)
    report=quality.inspect(video,audio)
    assert report["scope"]=="integrity_duration_and_signal_only"
    assert report["warnings"]
    assert report["visual_review"]=="pending"


def test_cloud_ollama_model_is_rejected_before_network(monkeypatch):
    from studio import script_gen
    monkeypatch.setenv("STUDIO_OLLAMA_MODEL","gpt-oss:120b-cloud")
    monkeypatch.setattr(script_gen.urllib.request,"urlopen",lambda *a,**kw:pytest.fail("No cloud requests"))
    with pytest.raises(ValueError,match="cloud"):script_gen.draft_script("Topic")


def test_inference_child_keeps_gpu_lease_after_server_death(tmp_path):
    lockpath=tmp_path/"lease"; started=tmp_path/"started";done=tmp_path/"done"
    code='''import fcntl,sys
from studio.lease import worker_lease
from studio.runner import run_logged
lock=open(sys.argv[1],'a');fcntl.flock(lock,fcntl.LOCK_EX);worker_lease.set(lock.fileno())
child="import os,sys,time;from pathlib import Path;Path(sys.argv[1]).write_text(str(os.getpid()));time.sleep(1.5);Path(sys.argv[2]).touch()"
run_logged([sys.executable,'-c',child,sys.argv[2],sys.argv[3]])
'''
    parent=subprocess.Popen([sys.executable,"-c",code,str(lockpath),str(started),str(done)],
                            cwd=Path(__file__).parents[1],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        for _ in range(100):
            if started.exists():break
            time.sleep(.02)
        assert started.exists()
        parent.kill();parent.wait(timeout=5)
        with lockpath.open("a") as lock:
            with pytest.raises(BlockingIOError):fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            for _ in range(150):
                try:
                    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);break
                except BlockingIOError:time.sleep(.02)
            else:pytest.fail("Inference child did not release the lease")
            assert done.exists()
    finally:
        if parent.poll() is None:parent.kill();parent.wait()


def test_api_rejects_insufficient_hardware_before_enqueuing(monkeypatch):
    profile()
    def no_resources(engine):raise ValueError("Recursos insuficientes")
    monkeypatch.setattr(resources,"require",no_resources)
    client=TestClient(app,base_url="http://localhost")
    response=client.post("/jobs",data={"profile":"eu","text":"Text","mode":"avatar"})
    assert response.status_code==400
    assert jobs.list_all()==[]


def test_qwen_reference_transcription_can_be_checked_locally(tmp_path,monkeypatch):
    root=config.MODELS/"qwen3";root.mkdir(parents=True)
    (root/"config.json").write_text("{}")
    (root/"download.json").write_text(json.dumps({"repo":config.QWEN_MODEL}))
    (root/"speech_tokenizer").mkdir();(root/"speech_tokenizer/config.json").write_text("{}")
    voice=tmp_path/"voice.wav";voice.write_bytes(b"reference");voice.with_suffix(".txt").write_text("Texto informado")
    monkeypatch.setenv("STUDIO_TRANSCRIBE","1")
    monkeypatch.setattr(audio_quality,"inspect",lambda *a,**kw:{"word_error_rate":1,"transcript":"Outro texto"})
    with pytest.raises(ValueError,match="referência divergiu"):
        QwenTTS().validate_reference(voice)
    assert (tmp_path/"reference_quality.json").exists()


def test_download_budget_checks_whole_set_before_first_weight(tmp_path,monkeypatch):
    import types,importlib.util
    fake=types.ModuleType("huggingface_hub");metadata=[];downloads=[]
    class API:
        def model_info(self,repo,**kw):
            metadata.append(repo)
            return types.SimpleNamespace(sha="fixed",siblings=[types.SimpleNamespace(rfilename="single/weights.safetensors",size=8*1024**3)])
    fake.HfApi=API;fake.hf_hub_download=lambda *a,**kw:downloads.append(kw)
    fake.snapshot_download=lambda **kw:downloads.append(kw)
    monkeypatch.setitem(sys.modules,"huggingface_hub",fake)
    path=Path(__file__).parents[1]/"scripts/download_generative_weights.py"
    spec=importlib.util.spec_from_file_location("download_budget_test",path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.ROOT=tmp_path
    monkeypatch.setattr(module.shutil,"disk_usage",lambda p:types.SimpleNamespace(free=15*1024**3))
    with pytest.raises(SystemExit,match="conjunto completo"):
        module.download("infinitetalk")
    assert len(metadata)==3 and not downloads


def test_motion_pipeline_passes_whole_scene_policy_including_three_second_tail(tmp_path,monkeypatch):
    folder=profile();jdir=config.job_dir("motiontail");jdir.mkdir(parents=True)
    audio=jdir/"speech.wav";motion=jdir/"motion.mp4"
    run_ffmpeg("-f","lavfi","-i","sine=duration=18",audio)
    run_ffmpeg("-f","lavfi","-i","color=c=blue:s=64x64:r=30:d=18","-c:v","libx264",motion)
    monkeypatch.setattr(config,"SCENE_SECONDS",15)
    seen=[]
    class Motion:
        def render(self,identity,driving,speech,prompt,out,seed):
            seconds=media.duration(speech)
            run_ffmpeg("-f","lavfi","-i",f"color=c=blue:s=64x64:r=30:d={seconds}","-c:v","libx264",out)
    class Lip:
        def render(self,video,speech,out,*,preserve_motion=False):
            seen.append((media.duration(video),preserve_motion))
            run_ffmpeg("-i",video,"-i",speech,"-map","0:v","-map","1:a","-c:v","copy","-c:a","aac","-shortest",out)
    monkeypatch.setattr(pipeline,"get_video",lambda name:Motion())
    monkeypatch.setattr(pipeline,"get_lipsync",lambda name:Lip())
    pipeline._render_scenes(folder,jdir,audio,jdir/"output.mp4","motion","")
    assert len(seen)==2
    assert all(policy for duration,policy in seen)
    assert seen[0][0]==pytest.approx(15,abs=.05)
    assert seen[1][0]==pytest.approx(3,abs=.05)
    assert media.duration(jdir/"output.mp4")==pytest.approx(18,abs=.1)
