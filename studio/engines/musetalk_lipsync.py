"""Lip-sync rápido com MuseTalk 1.5 (MIT). Funciona em GPUs pequenas (>=4 GB, fp16)."""
import subprocess
import tempfile
from pathlib import Path

from .. import config
from .base import LipSyncEngine


class MuseTalk(LipSyncEngine):
    def render(self, base_video, audio, out):
        repo = config.UPSTREAMS / "MuseTalk"
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "task.yaml"
            cfg.write_text(f"task_0:\n video_path: \"{base_video.resolve()}\"\n"
                           f" audio_path: \"{audio.resolve()}\"\n")
            subprocess.run([
                config.venv_python("musetalk"), "-m", "scripts.inference",
                "--inference_config", str(cfg),
                "--result_dir", tmp,
                "--unet_model_path", "models/musetalkV15/unet.pth",
                "--unet_config", "models/musetalkV15/musetalk.json",
                "--version", "v15", "--use_float16",
            ], cwd=repo, check=True)
            produced = next(f for f in sorted(Path(tmp).rglob("*.mp4")) if not f.name.startswith("temp"))
            out.write_bytes(produced.read_bytes())
        return out
