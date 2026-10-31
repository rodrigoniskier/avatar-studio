"""Converte qualquer áudio/vídeo (celular, .m4a, .mov...) para o formato que os engines esperam."""
import json
import os
import shutil
import subprocess
import wave
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


def prepare_voice(src: Path, dst: Path, start: float = 0, seconds: float = 30) -> None:
    """WAV mono 24 kHz, recortado em 30 s (suficiente para clonar)."""
    if start < 0 or not 5 <= seconds <= 30:
        raise ValueError("Selecione um início válido e duração de 5 a 30 segundos.")
    if not NORMALIZE:
        shutil.copy(src, dst); return
    if start < 0 or not 5 <= seconds <= 30 or duration(src) - start < 5:
        raise ValueError("O áudio da voz tem menos de 5 s. Grave de 10 a 30 s.")
    _run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(start), "-i", str(src), "-t", str(seconds), "-ac", "1",
          "-ar", "24000", "-af", "loudnorm", str(dst)])


def prepare_video(src: Path, dst: Path, min_seconds: float = 10, max_seconds: float | None = 120,
                  fps: int | None = 25, lossless: bool = False) -> None:
    """Derivado H.264/25 fps até 120 s, preservando resolução; o original fica no perfil."""
    if not NORMALIZE:
        shutil.copy(src, dst); return
    if duration(src) < min_seconds:
        raise ValueError("O vídeo tem menos de 10 s. Grave de 30 a 120 s.")
    limit = ["-t", str(max_seconds)] if max_seconds is not None else []
    rate = ["-r", str(fps)] if fps else []
    _run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), *limit, *rate,
          "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2", "-c:v", "libx264", "-crf", "0" if lossless else "17", "-pix_fmt", "yuv420p",
          "-c:a", "aac", str(dst)])


def prepare_image(src: Path, dst: Path, from_video: bool = False) -> None:
    if not NORMALIZE:
        shutil.copyfile(src, dst)
        return
    args = ["ffmpeg", "-y", "-loglevel", "error"]
    if from_video:
        args += ["-ss", "1"]
    _run(args + ["-i", str(src), "-frames:v", "1", str(dst)])


def probe(path: Path) -> dict:
    return json.loads(_run(["ffprobe", "-v", "error", "-show_streams", "-show_format",
                            "-of", "json", str(path)]))


def split_audio(src: Path, folder: Path, seconds: int) -> list[Path]:
    if not 5 <= seconds <= 30:
        raise ValueError("As cenas devem durar entre 5 e 30 segundos.")
    folder.mkdir(parents=True, exist_ok=True)
    # The segment muxer splits on packet boundaries, which vary by FFmpeg version.
    # Decode once and split exact PCM samples. Keep the approved master untouched.
    pcm = folder / "source_pcm.wav"
    _run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-map", "0:a:0",
          "-c:a", "pcm_s16le", str(pcm)])
    parts = []
    try:
        with wave.open(str(pcm), "rb") as source:
            frames = source.getframerate() * seconds
            while block := source.readframes(frames):
                path = folder / f"scene{len(parts):04d}.wav"
                with wave.open(str(path), "wb") as out:
                    out.setparams(source.getparams())
                    out.writeframes(block)
                parts.append(path)
    finally:
        pcm.unlink(missing_ok=True)
    return parts


def concat_videos(parts: list[Path], audio: Path, out: Path) -> None:
    fields = ("codec_name", "width", "height", "pix_fmt", "r_frame_rate", "time_base", "profile")
    descriptions = []
    for part in parts:
        stream = next(s for s in probe(part)["streams"] if s["codec_type"] == "video")
        descriptions.append(tuple(stream.get(key) for key in fields))
    if len(set(descriptions)) != 1:
        raise ValueError("As cenas têm formatos incompatíveis para montagem sem recompressão.")
    # Paths are app-generated; escape apostrophes for the concat demuxer.
    listing = out.with_suffix(".concat.txt")
    listing.write_text("".join("file '" + str(p.resolve()).replace("'", "'\\''") + "'\n" for p in parts))
    _run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(listing),
          "-i", str(audio), "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy",
          "-c:a", "aac", "-shortest", "-movflags", "+faststart", str(out)])
