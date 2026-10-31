import hmac
import json
import tempfile
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from starlette.concurrency import run_in_threadpool

from . import config, jobs, profiles, pipeline


@asynccontextmanager
async def lifespan(app):
    worker = jobs.Worker()
    worker.thread.start()
    yield
    worker.stop.set()
    worker.thread.join(timeout=2)


app = FastAPI(title="Avatar Studio", lifespan=lifespan)
WEB = Path(__file__).resolve().parent.parent / "web" / "index.html"


@app.middleware("http")
async def authorization(request: Request, call_next):
    host = request.headers.get("host", "").lower()
    origin = request.headers.get("origin")
    if origin:
        try:
            parsed = urlsplit(origin)
        except ValueError:
            return JSONResponse({"detail": "Origem inválida."}, status_code=403)
        if parsed.scheme not in {"http", "https"} or parsed.netloc.lower() != host:
            return JSONResponse({"detail": "Origem da requisição não autorizada."}, status_code=403)
    if not config.ACCESS_TOKEN and request.url.hostname not in {"localhost", "127.0.0.1", "::1"}:
        return JSONResponse({"detail": "Host não autorizado. Para rede, configure a chave de sessão."}, status_code=403)
    if config.ACCESS_TOKEN and request.url.path != "/":
        supplied = request.headers.get("authorization", "").removeprefix("Bearer ")
        if not hmac.compare_digest(supplied.encode("utf-8"), config.ACCESS_TOKEN.encode("utf-8")):
            return JSONResponse({"detail": "Informe a chave de acesso desta sessão."}, status_code=401)
    try:
        return await call_next(request)
    except (ValueError, PermissionError) as error:
        return JSONResponse({"detail": str(error)}, status_code=400)
    except FileNotFoundError as error:
        return JSONResponse({"detail": str(error)}, status_code=404)


@app.get("/", response_class=HTMLResponse)
def index():
    return WEB.read_text()


@app.get("/capabilities")
def capabilities():
    from . import resources
    hardware = resources.snapshot()
    return {"free_only": True, "tts": config.TTS_ENGINE, "lipsync": config.LIPSYNC_ENGINE,
            "video": config.VIDEO_ENGINE, "simulation": "mock" in {config.TTS_ENGINE, config.LIPSYNC_ENGINE},
            "modes": ["dub", "avatar", "motion"],
            "generative_resources": {name: resources.check(name, hardware) for name in ("infinitetalk", "wan-animate")},
            "motion_text_direction": False}


@app.get("/profiles")
def list_profiles():
    root = config.DATA_DIR / "profiles"
    return {"profiles": sorted(d.name for d in root.iterdir() if (d / "consent.json").exists()
                                and (d / "voice.wav").exists() and (d / "avatar.mp4").exists()) if root.exists() else []}


async def save_upload(upload: UploadFile, folder: Path, label: str) -> Path:
    suffix = Path(upload.filename or "").suffix.lower()
    if len(suffix) > 10 or not suffix[1:].isalnum():
        suffix = ".bin"
    path = folder / (label + suffix)
    total = 0
    with path.open("wb") as target:
        while block := await upload.read(1024 * 1024):
            total += len(block)
            if total > config.MAX_UPLOAD_MB * 1024 * 1024:
                raise HTTPException(413, f"Arquivo excede {config.MAX_UPLOAD_MB} MB.")
            target.write(block)
    return path


@app.post("/profiles/{name}")
async def create_profile(name: str, voice: UploadFile = File(...), video: UploadFile = File(...),
                         consent_ok: bool = Form(...), image: UploadFile | None = File(None),
                         transcript: str = Form(""), voice_start: float = Form(0), voice_seconds: float = Form(30)):
    if not consent_ok:
        raise HTTPException(400, "É necessário confirmar o consentimento.")
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        v = await save_upload(voice, folder, "voice")
        a = await save_upload(video, folder, "video")
        i = await save_upload(image, folder, "image") if image else None
        await run_in_threadpool(profiles.create, name, v, a, image=i, transcript=transcript,
                                voice_start=voice_start, voice_seconds=voice_seconds)
    return {"profile": name}


@app.get("/profiles/{name}/voice")
def reference_voice(name: str):
    path = config.profile_dir(name) / "voice.wav"
    if not path.exists():
        raise HTTPException(404)
    return FileResponse(path, media_type="audio/wav")


@app.post("/jobs")
async def create_job(profile: str = Form(...), text: str = Form(...), lang: str = Form("pt"),
                     mode: str = Form("dub"), prompt: str = Form("Natural speaking, restrained gestures, static camera."),
                     motion: UploadFile | None = File(None)):
    from . import consent, pipeline, media, resources
    consent.require(config.profile_dir(profile))
    pipeline.split_text(text)
    if len(text) > 50000 or len(prompt) > 4000 or mode not in {"dub", "avatar", "motion"} or lang not in {"pt", "en", "es"}:
        raise HTTPException(400, "Texto, idioma, direção ou modo inválido.")
    if mode == "motion" and motion is None:
        raise HTTPException(400, "Envie o vídeo de movimento.")
    if mode != "dub":
        await run_in_threadpool(resources.require, "wan-animate" if mode == "motion" else config.VIDEO_ENGINE)
    if mode == "motion":
        prompt = ""  # the driving video controls the action, not this field
    jid = uuid.uuid4().hex[:12]
    folder = config.job_dir(jid)
    folder.mkdir(parents=True)
    if motion:
        src = await save_upload(motion, folder, "motion_original")
        await run_in_threadpool(media.prepare_video, src, folder / "motion.mp4", min_seconds=0.1,
                                max_seconds=None, fps=None, lossless=True)
    jobs.enqueue({"profile": profile, "text": text, "lang": lang, "mode": mode, "prompt": prompt}, jid)
    return {"job_id": jid}


@app.get("/jobs")
def list_jobs():
    return {"jobs": [{"id": r["id"], "status": r["status"], "url": f"/jobs/{r['id']}/video"} for r in jobs.list_all()]}


@app.get("/jobs/{job_id}")
def job_status(job_id: str):
    row = jobs.get(job_id)
    result = {"status": row["status"], "error": row["error"], "phase": row["phase"],
              "retryable": row["status"] == "error" and json.loads(row["settings"]) == pipeline.settings(),
              "scenes_completed": len(list((config.job_dir(job_id) / "scenes").glob("*.ready.json"))),
              "audio_url": f"/jobs/{job_id}/audio", "url": f"/jobs/{job_id}/video"}
    report = config.job_dir(job_id) / "quality.json"
    if report.exists():
        result["quality"] = json.loads(report.read_text())
    speech_report = config.job_dir(job_id) / "speech_quality.json"
    if speech_report.exists():
        result["speech_quality"] = json.loads(speech_report.read_text())
    return result


@app.get("/jobs/{job_id}/audio")
def job_audio(job_id: str):
    path = config.job_dir(job_id) / "speech.wav"
    if not path.exists():
        raise HTTPException(404)
    return FileResponse(path, media_type="audio/wav")


@app.post("/jobs/{job_id}/approve-audio")
def approve_audio(job_id: str):
    jobs.approve_audio(job_id)
    return {"status": "queued"}


@app.post("/jobs/{job_id}/retry")
def retry(job_id: str):
    jobs.retry(job_id)
    return {"status": "queued"}


@app.post("/jobs/{job_id}/review")
def review(job_id: str, accepted: bool = Form(...)):
    jobs.review(job_id, accepted)
    return {"status": "done" if accepted else "rejected"}


@app.get("/jobs/{job_id}/video")
def job_video(job_id: str):
    row = jobs.get(job_id)
    path = config.job_dir(job_id) / "output.mp4"
    if row["status"] not in {"review", "done", "rejected", "simulation"} or not path.exists():
        raise HTTPException(404)
    return FileResponse(path, media_type="video/mp4")
