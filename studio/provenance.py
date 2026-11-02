"""Proveniência de código e pesos reais, incluindo substituições manuais."""
import os
from pathlib import Path

from .artifacts import digest, signature

WEIGHTS = {".safetensors", ".pth", ".pt", ".bin", ".onnx", ".ckpt"}


def inventory(root: Path, suffixes=None, content=False):
    records = {}
    if not root.exists():
        return records
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if any(part in {".git", ".cache", "__pycache__", ".venvs", ".venv"} for part in rel.parts):
            continue
        if path.is_file() and (suffixes is None or path.suffix in suffixes):
            stat = path.stat()
            records[rel.as_posix()] = {"size": stat.st_size, "mtime_ns": stat.st_mtime_ns,
                                      "ctime_ns": stat.st_ctime_ns}
            if content:
                records[rel.as_posix()]["sha256"] = digest(path)
    return records


def weights(root: Path):
    # Do not read tens of GB per poll. Size/mtime/ctime detect normal replacements;
    # this is cache invalidation, not an adversarial integrity certificate.
    return signature(inventory(root, WEIGHTS | {".json", ".yaml", ".yml"}))


def chatterbox_weights():
    hub = Path(os.getenv("HF_HUB_CACHE", str(Path(os.getenv("HF_HOME", str(Path.home()/".cache/huggingface"))) / "hub")))
    return signature({p.name: weights(p) for p in hub.glob("models--*") if "chatterbox" in p.name.casefold()})
