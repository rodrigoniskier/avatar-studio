import os
from pathlib import Path

DATA_DIR = Path(os.getenv("STUDIO_DATA", "data")).resolve()
TTS_ENGINE = os.getenv("STUDIO_TTS", "chatterbox")
LIPSYNC_ENGINE = os.getenv("STUDIO_LIPSYNC", "musetalk")
UPSTREAMS = Path(os.getenv("STUDIO_UPSTREAMS", "upstreams")).resolve()
DEVICE = os.getenv("STUDIO_DEVICE", "cuda")


def profile_dir(name: str) -> Path:
    if not name.isidentifier() or len(name) > 80:
        raise ValueError("Nome de perfil inválido: use letras, números e _ (máximo 80).")
    return DATA_DIR / "profiles" / name


def job_dir(job_id: str) -> Path:
    if not job_id.isalnum() or len(job_id) > 64:
        raise ValueError("Identificador de trabalho inválido.")
    return DATA_DIR / "jobs" / job_id

VENVS = Path(os.getenv("STUDIO_VENVS", ".venvs")).resolve()


def venv_python(name: str) -> str:
    """Python do ambiente isolado de cada upstream (dependências incompatíveis entre si)."""
    p = VENVS / name / "bin" / "python"
    if not p.exists():
        raise RuntimeError(f"Ambiente {name} ausente. Execute o script de instalação correspondente.")
    return str(p)


# Apenas inferência local. Nenhum motor usa APIs comerciais ou créditos promocionais.
VIDEO_ENGINE = os.getenv("STUDIO_VIDEO", "infinitetalk")
MODELS = Path(os.getenv("STUDIO_MODELS", "models")).resolve()
QWEN_MODEL = os.getenv("STUDIO_QWEN_MODEL", "Qwen/Qwen3-TTS-12Hz-1.7B-Base")
TTS_REVISION = os.getenv("STUDIO_TTS_REVISION", "default")
VIDEO_SIZE = os.getenv("STUDIO_VIDEO_SIZE", "480")
SEED = int(os.getenv("STUDIO_SEED", "42"))
SCENE_SECONDS = int(os.getenv("STUDIO_SCENE_SECONDS", "15"))
MAX_UPLOAD_MB = int(os.getenv("STUDIO_MAX_UPLOAD_MB", "512"))
ACCESS_TOKEN = os.getenv("STUDIO_ACCESS_TOKEN", "")
CFG_WEIGHT = float(os.getenv("STUDIO_CFG_WEIGHT", "0.3"))
EXAGGERATION = float(os.getenv("STUDIO_EXAGGERATION", "0.5"))
LIPSYNC_STEPS = int(os.getenv("STUDIO_LIPSYNC_STEPS", "30"))
LIPSYNC_GUIDANCE = float(os.getenv("STUDIO_LIPSYNC_GUIDANCE", "1.5"))
