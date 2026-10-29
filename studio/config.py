import os
from pathlib import Path

DATA_DIR = Path(os.getenv("STUDIO_DATA", "data")).resolve()
TTS_ENGINE = os.getenv("STUDIO_TTS", "mock")        # mock | chatterbox
LIPSYNC_ENGINE = os.getenv("STUDIO_LIPSYNC", "mock")  # mock | latentsync | musetalk
UPSTREAMS = Path(os.getenv("STUDIO_UPSTREAMS", "upstreams")).resolve()
DEVICE = os.getenv("STUDIO_DEVICE", "cuda")


def profile_dir(name: str) -> Path:
    return DATA_DIR / "profiles" / name


def job_dir(job_id: str) -> Path:
    return DATA_DIR / "jobs" / job_id
