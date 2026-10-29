from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse

from . import config, consent, pipeline

app = FastAPI(title="Avatar Studio")
WEB = Path(__file__).resolve().parent.parent / "web" / "index.html"


@app.get("/", response_class=HTMLResponse)
def index():
    return WEB.read_text()


@app.post("/profiles/{name}")
async def create_profile(name: str, voice: UploadFile = File(...), video: UploadFile = File(...),
                         consent_ok: bool = Form(...)):
    if not name.isidentifier():
        raise HTTPException(400, "Nome de perfil inválido")
    if not consent_ok:
        raise HTTPException(400, "É necessário confirmar o consentimento")
    pdir = config.profile_dir(name)
    consent.register(pdir, name)
    (pdir / "voice.wav").write_bytes(await voice.read())
    (pdir / "avatar.mp4").write_bytes(await video.read())
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
