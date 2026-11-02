"""Criação transacional de perfis, originais e referências independentes."""
import json
import shutil
import tempfile
from pathlib import Path

from . import config, consent, media


def create(name: str, voice: Path, video: Path, *, image: Path | None = None,
           transcript: str = "", voice_start: float = 0, voice_seconds: float = 30):
    target = config.profile_dir(name)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise ValueError("O perfil já existe. Use outro nome para manter o original e o histórico.")
    with tempfile.TemporaryDirectory(dir=target.parent) as tmp:
        staging = Path(tmp) / "profile"
        originals = staging / "originals"
        originals.mkdir(parents=True)
        for label, src in (("voice", voice), ("video", video), ("image", image)):
            if src:
                shutil.copyfile(src, originals / (label + src.suffix.lower()))
        media.prepare_voice(voice, staging / "voice.wav", voice_start, voice_seconds)
        media.prepare_video(video, staging / "avatar.mp4")
        media.prepare_image(image or video, staging / "identity.png", from_video=image is None)
        if transcript.strip():
            (staging / "voice.txt").write_text(transcript.strip())
        (staging / "reference.json").write_text(json.dumps({
            "voice_start": voice_start, "voice_seconds": voice_seconds,
            "identity_source": "uploaded_image" if image else "video_frame_at_1s",
            "note": "A transcrição deve corresponder exatamente ao trecho voice.wav."}, ensure_ascii=False))
        consent.register(staging, name)
        staging.rename(target)
    return target
