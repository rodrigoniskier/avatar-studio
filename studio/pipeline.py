import json
import re
import shutil
import subprocess
import uuid
from pathlib import Path

from . import config, consent
from .engines import get_lipsync, get_tts


def split_text(text: str, limit: int = 300) -> list[str]:
    """Quebra por frases, agrupando até `limit` caracteres (TTS degrada em textos longos)."""
    chunks, cur = [], ""
    for s in re.split(r"(?<=[.!?…])\s+", text.strip()):
        if cur and len(cur) + len(s) > limit:
            chunks.append(cur); cur = s
        else:
            cur = f"{cur} {s}".strip()
    return chunks + ([cur] if cur else [])


def _concat_wavs(parts: list[Path], out: Path) -> None:
    if len(parts) == 1:
        shutil.copy(parts[0], out); return
    lst = out.with_suffix(".txt")
    lst.write_text("".join(f"file '{p.resolve()}'\n" for p in parts))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                    "-i", str(lst), "-c", "copy", str(out)], check=True)


def _cached_speech(profile: str, text: str, lang: str) -> Path | None:
    """Reaproveita a fala (etapa mais demorada) de uma execução anterior com mesmos dados,
    útil quando só o lip-sync falhou."""
    root = config.DATA_DIR / "jobs"
    for d in sorted(root.glob("*"), key=lambda d: d.stat().st_mtime, reverse=True) if root.exists() else []:
        try:
            meta = json.loads((d / "job.json").read_text())
        except (OSError, ValueError):
            continue
        if meta == {"profile": profile, "text": text, "lang": lang} and (d / "speech.wav").exists():
            return d / "speech.wav"
    return None


def generate(profile: str, text: str, lang: str = "pt", job_id: str | None = None) -> Path:
    pdir = config.profile_dir(profile)
    consent.require(pdir)
    voice, video = pdir / "voice.wav", pdir / "avatar.mp4"
    for f in (voice, video):
        if not f.exists():
            raise FileNotFoundError(f"Falta {f.name} no perfil {profile}")

    job_id = job_id or uuid.uuid4().hex[:12]
    jdir = config.job_dir(job_id); jdir.mkdir(parents=True, exist_ok=True)
    previous = _cached_speech(profile, text, lang)
    (jdir / "job.json").write_text(json.dumps(
        {"profile": profile, "text": text, "lang": lang}, ensure_ascii=False))

    audio = jdir / "speech.wav"
    if previous:
        print(f"Reaproveitando a fala já gerada em {previous}", flush=True)
        shutil.copy(previous, audio)
    else:
        parts = get_tts(config.TTS_ENGINE).synthesize_batch(split_text(text), voice, jdir, lang)
        _concat_wavs(parts, audio)
    lipsync = get_lipsync(config.LIPSYNC_ENGINE)
    return lipsync.render(video, audio, jdir / "output.mp4")
