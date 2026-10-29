from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse

import tempfile

from . import config, consent, media, pipeline

app = FastAPI(title="Avatar Studio")
WEB = Path(__file__).resolve().parent.parent / "web" / "index.html"


@app.get("/", response_class=HTMLResponse)
def index():
    return WEB.read_text()


@app.get("/profiles")
def list_profiles():
    root = config.DATA_DIR / "profiles"
    ok = sorted(d.name for d in root.iterdir()
                if (d / "consent.json").exists() and (d / "voice.wav").exists()
                and (d / "avatar.mp4").exists()) if root.exists() else []
    return {"profiles": ok}


@app.post("/profiles/{name}")
async def create_profile(name: str, voice: UploadFile = File(...), video: UploadFile = File(...),
                         consent_ok: bool = Form(...)):
    if not name.isidentifier():
        raise HTTPException(400, "Nome de perfil inválido: use só letras, números e _ (sem espaços ou acentos)")
    if not consent_ok:
        raise HTTPException(400, "É necessário confirmar o consentimento")
    pdir = config.profile_dir(name)
    pdir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        v, a = Path(tmp) / "v", Path(tmp) / "a"
        v.write_bytes(await voice.read()); a.write_bytes(await video.read())
        try:
            media.prepare_voice(v, pdir / "voice.wav")
            media.prepare_video(a, pdir / "avatar.mp4")
        except ValueError as e:
            raise HTTPException(400, str(e))
    consent.register(pdir, name)  # só registra quando o perfil está completo
    return {"profile": name}


def _run(profile, text, lang, job_id):
    try:
        pipeline.generate(profile, text, lang, job_id)
    except Exception as e:  # registra falha para o front consultar
        (config.job_dir(job_id) / "error.txt").write_text(str(e))


@app.post("/jobs")
def create_job(bg: BackgroundTasks, profile: str = Form(...), text: str = Form(...),
               lang: str = Form("pt")):
    import uuid
    job_id = uuid.uuid4().hex[:12]
    config.job_dir(job_id).mkdir(parents=True, exist_ok=True)
    bg.add_task(_run, profile, text, lang, job_id)
    return {"job_id": job_id}


@app.get("/jobs")
def list_jobs():
    root = config.DATA_DIR / "jobs"
    done = sorted((d for d in root.iterdir() if (d / "output.mp4").exists()),
                  key=lambda d: (d / "output.mp4").stat().st_mtime, reverse=True) if root.exists() else []
    return {"jobs": [{"id": d.name, "url": f"/jobs/{d.name}/video"} for d in done]}


@app.get("/jobs/{job_id}")
def job_status(job_id: str):
    jdir = config.job_dir(job_id)
    if (jdir / "output.mp4").exists():
        return {"status": "done", "url": f"/jobs/{job_id}/video"}
    if (jdir / "error.txt").exists():
        return {"status": "error", "error": (jdir / "error.txt").read_text()}
    return {"status": "running"} if jdir.exists() else {"status": "unknown"}


@app.get("/jobs/{job_id}/video")
def job_video(job_id: str):
    f = config.job_dir(job_id) / "output.mp4"
    if not f.exists():
        raise HTTPException(404)
    return FileResponse(f, media_type="video/mp4")
