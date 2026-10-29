"""Converte qualquer áudio/vídeo (celular, .m4a, .mov...) para o formato que os engines esperam."""
import json
import os
import shutil
import subprocess
from pathlib import Path

NORMALIZE = os.getenv("STUDIO_NORMALIZE", "1") == "1"


def _run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        raise ValueError(f"Arquivo inválido ou ilegível ({cmd[0]}): {r.stderr.strip()[-300:]}")
    return r.stdout


def duration(path: Path) -> float:
    out = _run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)])
    return float(json.loads(out)["format"]["duration"])


def prepare_voice(src: Path, dst: Path) -> None:
    """WAV mono 24 kHz, recortado em 30 s (suficiente para clonar)."""
    if not NORMALIZE:
        shutil.copy(src, dst); return
    if duration(src) < 5:
        raise ValueError("O áudio da voz tem menos de 5 s. Grave de 10 a 30 s.")
    _run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-t", "30", "-ac", "1",
          "-ar", "24000", "-af", "loudnorm", str(dst)])


def prepare_video(src: Path, dst: Path) -> None:
    """MP4 H.264, 25 fps, até 720p, máx. 120 s (limita memória e tempo de GPU)."""
    if not NORMALIZE:
        shutil.copy(src, dst); return
    if duration(src) < 10:
        raise ValueError("O vídeo tem menos de 10 s. Grave de 30 a 120 s.")
    _run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-t", "120", "-r", "25",
          "-vf", "scale=-2:'min(720,ih)'", "-c:v", "libx264", "-pix_fmt", "yuv420p",
          "-c:a", "aac", str(dst)])
