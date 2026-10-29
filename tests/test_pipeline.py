import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def data_dir(tmp_path, monkeypatch):
    from studio import config
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)


def test_split_text():
    from studio.pipeline import split_text
    assert split_text("Oi. Tudo bem? Sim!", limit=10) == ["Oi.", "Tudo bem?", "Sim!"]


def test_requires_consent():
    from studio import pipeline
    with pytest.raises(PermissionError):
        pipeline.generate("ninguem", "oi")


def test_end_to_end_api():
    from studio.api import app
    c = TestClient(app)
    files = {"voice": ("v.wav", b"RIFF"), "video": ("a.mp4", b"fake")}
    assert c.get("/profiles").json() == {"profiles": []}
    assert c.post("/profiles/eu", files=files, data={"consent_ok": "false"}).status_code == 400
    assert c.get("/profiles").json() == {"profiles": []}
    assert c.post("/profiles/eu", files=files, data={"consent_ok": "true"}).status_code == 200
    assert c.get("/profiles").json() == {"profiles": ["eu"]}
    jid = c.post("/jobs", data={"profile": "eu", "text": "Olá mundo."}).json()["job_id"]
    st = c.get(f"/jobs/{jid}").json()
    assert st["status"] == "done"
    assert c.get(st["url"]).content == b"fake"
    assert c.get("/jobs").json()["jobs"][0]["id"] == jid


def test_media_rejects_garbage(tmp_path, monkeypatch):
    from studio import media
    monkeypatch.setattr(media, "NORMALIZE", True)
    bad = tmp_path / "x"; bad.write_bytes(b"nao e audio")
    with pytest.raises((ValueError, FileNotFoundError)):
        media.prepare_voice(bad, tmp_path / "o.wav")


def test_runner_reports_real_error():
    import sys
    from studio.runner import run_logged
    with pytest.raises(RuntimeError, match="MOTIVO_REAL"):
        run_logged([sys.executable, "-c", "import sys; print('MOTIVO_REAL', file=sys.stderr); sys.exit(1)"])


def test_speech_reused_when_only_lipsync_failed(monkeypatch):
    from studio import pipeline, config, consent
    pdir = config.profile_dir("eu"); consent.register(pdir, "eu")
    (pdir / "voice.wav").write_bytes(b"x"); (pdir / "avatar.mp4").write_bytes(b"v")
    calls = []
    real = pipeline.get_tts
    monkeypatch.setattr(pipeline, "get_tts", lambda n: (calls.append(1), real(n))[1])
    pipeline.generate("eu", "Frase um. Frase dois.")
    pipeline.generate("eu", "Frase um. Frase dois.")
    assert len(calls) == 1  # segunda execução reaproveita a fala


def test_musetalk_reports_missing_output(tmp_path, monkeypatch):
    import shutil, subprocess
    if not shutil.which("ffmpeg"):
        pytest.skip("sem ffmpeg")
    from studio import config
    from studio.engines import musetalk_lipsync as m
    base = tmp_path / "b.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=320x240:rate=25:duration=30",
                    "-pix_fmt", "yuv420p", str(base)], check=True)
    seen = {}
    monkeypatch.setattr(m, "run_logged", lambda cmd, cwd=None, **k: seen.update(cmd=cmd))  # engine "falha em silêncio"
    with pytest.raises(RuntimeError, match="sem gerar o vídeo"):
        m.MuseTalk().render(base, tmp_path / "a.wav", tmp_path / "o.mp4")
    assert seen["cmd"][-1] == "--use_float16"
