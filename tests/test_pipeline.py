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
    assert c.post("/profiles/eu", files=files, data={"consent_ok": "false"}).status_code == 400
    assert c.post("/profiles/eu", files=files, data={"consent_ok": "true"}).status_code == 200
    jid = c.post("/jobs", data={"profile": "eu", "text": "Olá mundo."}).json()["job_id"]
    st = c.get(f"/jobs/{jid}").json()
    assert st["status"] == "done"
    assert c.get(st["url"]).content == b"fake"


def test_media_rejects_garbage(tmp_path, monkeypatch):
    from studio import media
    monkeypatch.setattr(media, "NORMALIZE", True)
    bad = tmp_path / "x"; bad.write_bytes(b"nao e audio")
    with pytest.raises((ValueError, FileNotFoundError)):
        media.prepare_voice(bad, tmp_path / "o.wav")
