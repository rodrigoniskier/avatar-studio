import json
import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from studio import config, consent, jobs, media, pipeline, profiles, quality
from studio.api import app
from studio.engines import get_lipsync, get_tts, get_video
from studio.engines.mock import MockTTS


@pytest.fixture(autouse=True)
def isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(config, "MODELS", tmp_path / "models")
    monkeypatch.setattr(config, "ACCESS_TOKEN", "")
    monkeypatch.setattr(config, "TTS_ENGINE", "mock")
    monkeypatch.setattr(config, "LIPSYNC_ENGINE", "mock")
    monkeypatch.delenv("STUDIO_TRANSCRIBE", raising=False)


def profile():
    folder = config.profile_dir("eu")
    consent.register(folder, "eu")
    (folder / "voice.wav").write_bytes(b"reference-v1")
    (folder / "avatar.mp4").write_bytes(b"video")
    (folder / "identity.png").write_bytes(b"image")
    return folder


def request():
    return {"profile": "eu", "text": "Esta é a fala de teste.", "lang": "pt"}


@pytest.mark.parametrize("factory", [get_tts, get_lipsync, get_video])
def test_unknown_engine_never_simulates(factory):
    with pytest.raises(ValueError):
        factory("typo-or-paid-provider")


@pytest.mark.parametrize("text", ["x" * 601, " ".join(["palavra"] * 150)])
def test_split_bounds_even_without_punctuation(text):
    parts = pipeline.split_text(text)
    assert all(0 < len(x) <= 300 for x in parts)
    assert "".join(parts).replace(" ", "") == text.replace(" ", "")


@pytest.mark.parametrize("name", ["../private", "", "/tmp", "x" * 81])
def test_profile_paths_are_confined(name):
    with pytest.raises(ValueError):
        config.profile_dir(name)


def test_audio_cache_uses_reference_content_and_parameters(monkeypatch):
    folder = profile()
    pipeline.generate(**request())
    assert pipeline._cached_speech("eu", request()["text"], "pt")
    (folder / "voice.wav").write_bytes(b"new-voice")
    assert pipeline._cached_speech("eu", request()["text"], "pt") is None
    (folder / "voice.wav").write_bytes(b"reference-v1")
    monkeypatch.setattr(config, "CFG_WEIGHT", .9)
    assert pipeline._cached_speech("eu", request()["text"], "pt") is None


def test_corrupt_cached_audio_not_reused():
    profile()
    audio = pipeline.generate(**request())
    audio.write_bytes(b"truncated")
    assert pipeline._cached_speech("eu", request()["text"], "pt") is None


def test_reference_transcript_and_model_revision_invalidate_cache(monkeypatch):
    folder = profile()
    pipeline.generate(**request())
    (folder / "voice.txt").write_text("Outra referência")
    assert pipeline._cached_speech("eu", request()["text"], "pt") is None
    (folder / "voice.txt").unlink()
    monkeypatch.setattr(config, "TTS_REVISION", "other-weights")
    assert pipeline._cached_speech("eu", request()["text"], "pt") is None


def test_audio_approval_blocks_reference_mutation():
    folder = profile()
    jid = "approvaltest"
    pipeline.generate(**request(), job_id=jid)
    pipeline.approve(jid)
    (folder / "voice.wav").write_bytes(b"other-speaker")
    with pytest.raises(ValueError, match="mudou"):
        pipeline.generate(**request(), job_id=jid, audio_approved=True)


def test_audio_approval_blocks_text_mutation():
    profile()
    pipeline.generate(**request(), job_id="texttest")
    pipeline.approve("texttest")
    with pytest.raises(ValueError, match="pedido mudou"):
        pipeline.generate("eu", "Texto não aprovado", job_id="texttest", audio_approved=True)


def test_queued_work_survives_restart_and_waits_for_approval():
    profile()
    jid = jobs.enqueue(request())
    with jobs.database() as db:
        db.execute("UPDATE jobs SET status='running' WHERE id=?", (jid,))
    assert jobs.drain_one()
    assert jobs.get(jid)["status"] == "awaiting_audio"
    assert not jobs.drain_one()
    assert not (config.job_dir(jid) / "output.mp4").exists()
    jobs.approve_audio(jid)
    assert jobs.drain_one()
    assert jobs.get(jid)["status"] == "simulation"


def test_settings_change_is_explicit_error(monkeypatch):
    profile()
    jid = jobs.enqueue(request())
    monkeypatch.setattr(config, "SEED", config.SEED + 1)
    jobs.drain_one()
    assert jobs.get(jid)["status"] == "error"
    assert "configuração mudou" in jobs.get(jid)["error"]


def test_failed_render_retries_without_resynthesizing(monkeypatch):
    profile()
    jid = jobs.enqueue(request())
    jobs.drain_one()
    speech = (config.job_dir(jid) / "speech.wav").read_bytes()
    jobs.approve_audio(jid)
    class Broken:
        def render(self, *args):
            raise RuntimeError("GPU interrompida")
    monkeypatch.setattr(pipeline, "get_lipsync", lambda name: Broken())
    jobs.drain_one()
    assert jobs.get(jid)["status"] == "error"
    jobs.retry(jid)
    monkeypatch.setattr(pipeline, "get_lipsync", lambda name: get_lipsync("mock"))
    jobs.drain_one()
    assert jobs.get(jid)["status"] == "simulation"
    assert (config.job_dir(jid) / "speech.wav").read_bytes() == speech


def test_authentication_covers_files_and_queue(monkeypatch):
    monkeypatch.setattr(config, "ACCESS_TOKEN", "private-session")
    client = TestClient(app, base_url="http://localhost")
    assert client.get("/").status_code == 200
    assert client.get("/profiles").status_code == 401
    assert client.get("/jobs/any/audio").status_code == 401
    assert client.get("/profiles", headers={"Authorization": "Bearer private-session"}).status_code == 200


def test_profile_is_atomic_and_cannot_overwrite(tmp_path, monkeypatch):
    voice = tmp_path / "input.wav"; voice.write_bytes(b"original-audio")
    video = tmp_path / "input.mp4"; video.write_bytes(b"original-video")
    def fail(*args, **kwargs):
        raise ValueError("bad video")
    monkeypatch.setattr(media, "prepare_video", fail)
    with pytest.raises(ValueError):
        profiles.create("broken", voice, video)
    assert not config.profile_dir("broken").exists()
    monkeypatch.setattr(media, "prepare_video", lambda src, dst: shutil.copyfile(src, dst))
    made = profiles.create("eu", voice, video)
    assert (made / "originals/voice.wav").read_bytes() == b"original-audio"
    with pytest.raises(ValueError, match="já existe"):
        profiles.create("eu", voice, video)


def ffmpeg(*args):
    subprocess.run(["ffmpeg", "-y", "-v", "error", *map(str, args)], check=True)


def test_normalization_preserves_portrait_resolution(tmp_path, monkeypatch):
    monkeypatch.setattr(media, "NORMALIZE", True)
    src = tmp_path / "original.mp4"
    dst = tmp_path / "derivative.mp4"
    ffmpeg("-f", "lavfi", "-i", "color=c=blue:s=720x1280:r=1:d=10", "-c:v", "libx264", src)
    media.prepare_video(src, dst)
    stream = next(x for x in media.probe(dst)["streams"] if x["codec_type"] == "video")
    assert (stream["width"], stream["height"]) == (720, 1280)


def test_technical_qa_rejects_missing_audio_and_duration_mismatch(tmp_path):
    video = tmp_path / "v.mp4"
    audio = tmp_path / "a.wav"
    ffmpeg("-f", "lavfi", "-i", "color=s=64x64:r=25:d=1", "-c:v", "libx264", video)
    ffmpeg("-f", "lavfi", "-i", "sine=frequency=440:duration=3", audio)
    with pytest.raises(ValueError, match="imagem e áudio"):
        quality.inspect(video, audio)
    out = tmp_path / "out.mp4"
    ffmpeg("-i", video, "-i", audio, "-c:v", "copy", "-c:a", "aac", out)
    with pytest.raises(ValueError, match="Duração incompatível"):
        quality.inspect(out, audio)


def test_full_queue_with_real_media_requires_visual_review(tmp_path, monkeypatch):
    folder = profile()
    ffmpeg("-f", "lavfi", "-i", "color=s=64x64:r=25:d=10", "-c:v", "libx264", folder / "avatar.mp4")
    monkeypatch.setattr(config, "TTS_ENGINE", "chatterbox")
    monkeypatch.setattr(config, "LIPSYNC_ENGINE", "musetalk")
    monkeypatch.setattr(pipeline, "get_tts", lambda name: MockTTS())
    class Render:
        def render(self, video, audio, out):
            ffmpeg("-i", video, "-i", audio, "-map", "0:v", "-map", "1:a", "-c:v", "libx264",
                   "-c:a", "aac", "-shortest", out)
    monkeypatch.setattr(pipeline, "get_lipsync", lambda name: Render())
    jid = jobs.enqueue(request())
    jobs.drain_one()
    jobs.approve_audio(jid)
    jobs.drain_one()
    assert jobs.get(jid)["status"] == "review", jobs.get(jid)["error"]
    report = json.loads((config.job_dir(jid) / "quality.json").read_text())
    assert report["identity"] == "not_measured"
    assert report["visual_review"] == "pending"
    jobs.review(jid, accepted=True)
    assert jobs.get(jid)["status"] == "done"


def test_generative_scenes_resume_without_repeating_inference(tmp_path, monkeypatch):
    folder = profile()
    monkeypatch.setattr(config, "SCENE_SECONDS", 5)
    audio = tmp_path / "speech.wav"
    ffmpeg("-f", "lavfi", "-i", "sine=frequency=440:duration=7", audio)
    called = []
    class Engine:
        def render(self, identity, motion, speech, prompt, out, seed):
            called.append(seed)
            assert identity == folder / "identity.png" and motion is None
            seconds = media.duration(speech)
            ffmpeg("-f", "lavfi", "-i", f"color=s=64x64:r=25:d={seconds}", "-c:v", "libx264", out)
    monkeypatch.setattr(pipeline, "get_video", lambda name: Engine())
    jdir = config.job_dir("scenes"); jdir.mkdir(parents=True)
    pipeline._render_scenes(folder, jdir, audio, jdir / "a.mp4", "avatar", "Quiet gestures")
    assert len(called) == 2
    pipeline._render_scenes(folder, jdir, audio, jdir / "b.mp4", "avatar", "Quiet gestures")
    assert len(called) == 2
    pipeline._render_scenes(folder, jdir, audio, jdir / "c.mp4", "avatar", "Different gestures")
    assert len(called) == 4


def test_word_error_rate_is_comparison_not_timbre_score():
    from studio.audio_quality import word_error_rate
    assert word_error_rate("Olá, mundo!", "olá mundo") == 0
    assert word_error_rate("um dois três", "um quatro três") == pytest.approx(1/3)


def test_infinite_adapter_uses_image_audio_and_local_model_paths(tmp_path, monkeypatch):
    from studio.engines import generative
    monkeypatch.setattr(generative.resources, "require", lambda engine: {"ok": True})
    monkeypatch.setattr(config, "UPSTREAMS", tmp_path / "upstreams")
    monkeypatch.setattr(config, "venv_python", lambda name: "/local/isolated/python")
    repo = config.UPSTREAMS / "InfiniteTalk"
    repo.mkdir(parents=True)
    (repo / "generate_infinitetalk.py").touch()
    root = config.MODELS / "infinitetalk"
    (root / "Wan2.1-I2V-14B-480P").mkdir(parents=True)
    (root / "chinese-wav2vec2-base").mkdir()
    (root / "InfiniteTalk/single").mkdir(parents=True)
    (root / "InfiniteTalk/single/infinitetalk.safetensors").touch()
    image = tmp_path / "identity.png"; image.write_bytes(b"identity")
    audio = tmp_path / "speech.wav"; audio.write_bytes(b"speech")
    out = tmp_path / "new.mp4"
    seen = {}
    monkeypatch.setattr(media, "duration", lambda path: 12.0)
    def run(cmd, cwd=None):
        seen.update(cmd=cmd, cwd=cwd)
        out.write_bytes(b"render")
    monkeypatch.setattr(generative, "run_logged", run)
    generative.InfiniteTalk().render(image, None, audio, "New acting", out, 42)
    task = json.loads(out.with_suffix(".json").read_text())
    assert task["cond_video"] == str(image)
    assert task["cond_audio"] == {"person1": str(audio)}
    assert seen["cmd"][0] == "/local/isolated/python"
    assert "--num_persistent_param_in_dit" in seen["cmd"]
    assert "--lora_dir" not in seen["cmd"]


def test_qwen_adapter_requires_local_weights_and_exact_transcript(tmp_path, monkeypatch):
    from studio.engines import qwen_tts
    ref = tmp_path / "voice.wav"; ref.write_bytes(b"reference")
    dest = tmp_path / "speech.wav"
    with pytest.raises(FileNotFoundError):
        qwen_tts.QwenTTS().synthesize("Nova fala", ref, dest)
    (config.MODELS / "qwen3").mkdir(parents=True)
    (config.MODELS / "qwen3/config.json").write_text("{}")
    (config.MODELS / "qwen3/speech_tokenizer").mkdir()
    (config.MODELS / "qwen3/speech_tokenizer/config.json").write_text("{}")
    (config.MODELS / "qwen3/download.json").write_text(json.dumps({"repo": config.QWEN_MODEL}))
    with pytest.raises(ValueError, match="transcrição exata"):
        qwen_tts.QwenTTS().synthesize("Nova fala", ref, dest)
    ref.with_suffix(".txt").write_text("Texto da referência")
    monkeypatch.setattr(config, "venv_python", lambda name: "/local/python")
    seen = {}
    def run(cmd, input_text):
        data = json.loads(input_text)
        seen.update(data)
        Path(data["outs"][0]).write_bytes(b"made")
    monkeypatch.setattr(qwen_tts, "run_logged", run)
    qwen_tts.QwenTTS().synthesize("Nova fala", ref, dest)
    assert dest.read_bytes() == b"made"
    assert seen["ref_text"] == "Texto da referência"
    assert seen["model"] == str(config.MODELS / "qwen3")


def test_worker_lock_prevents_parallel_gpu_use():
    import fcntl
    profile()
    jid = jobs.enqueue(request())
    with (config.DATA_DIR / ".worker.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert not jobs.drain_one()
        assert jobs.get(jid)["status"] == "queued"
    assert jobs.drain_one()


def test_musetalk_rejects_bad_framing_in_real_render_mode(tmp_path, monkeypatch):
    from studio.engines import musetalk_lipsync as module
    monkeypatch.setattr(config, "venv_python", lambda name: "python")
    result = subprocess.CompletedProcess([], 0, stdout='{"found": false, "start": 0}')
    monkeypatch.setattr(module.subprocess, "run", lambda *a, **k: result)
    with pytest.raises(RuntimeError, match="rosto inteiro"):
        module.pick_segment(tmp_path / "base.mp4", strict=True)


def test_wan_adapter_transfers_motion_without_flux_or_paid_prompt_service(tmp_path, monkeypatch):
    from studio.engines import generative
    monkeypatch.setattr(generative.resources, "require", lambda engine: {"ok": True})
    monkeypatch.setattr(config, "UPSTREAMS", tmp_path / "upstreams")
    monkeypatch.setattr(config, "venv_python", lambda name: "/local/python")
    repo = config.UPSTREAMS / "Wan2.2"; repo.mkdir(parents=True)
    (repo / "generate.py").touch()
    (config.MODELS / "wan-animate/process_checkpoint/pose2d").mkdir(parents=True)
    (config.MODELS / "wan-animate/process_checkpoint/pose2d/vitpose_h_wholebody.onnx").touch()
    (config.MODELS / "wan-animate/process_checkpoint/det").mkdir()
    (config.MODELS / "wan-animate/process_checkpoint/det/yolov10m.onnx").touch()
    image = tmp_path / "image.png"; image.touch()
    motion = tmp_path / "other-motion.mp4"; motion.touch()
    out = tmp_path / "out.mp4"
    calls = []
    def run(cmd, cwd=None):
        calls.append(cmd)
        if "--task" in cmd:
            out.touch()
    monkeypatch.setattr(generative, "run_logged", run)
    generative.WanAnimate().render(image, motion, tmp_path / "audio.wav", "Gesture", out, 12)
    assert len(calls) == 2
    assert str(motion) in calls[0] and str(image) in calls[0]
    assert "--use_flux" not in calls[0]
    assert "--use_prompt_extend" not in calls[1]
    assert calls[0][calls[0].index("--fps") + 1] == "30"
