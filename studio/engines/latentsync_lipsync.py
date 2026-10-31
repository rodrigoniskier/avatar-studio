"""Lip-sync com LatentSync 1.6 (Apache-2.0). Exige ~18 GB de VRAM (1.5: ~8 GB)."""
from pathlib import Path

from .. import config
from ..runner import run_logged
from .base import LipSyncEngine


class LatentSync(LipSyncEngine):
    def render(self, base_video, audio, out):
        if not 20 <= config.LIPSYNC_STEPS <= 50 or not 1 <= config.LIPSYNC_GUIDANCE <= 3:
            raise ValueError("LatentSync requer 20–50 passos e guidance de 1 a 3.")
        repo = config.UPSTREAMS / "LatentSync"
        run_logged([
            config.venv_python("latentsync"), "-m", "scripts.inference",
            "--unet_config_path", "configs/unet/stage2_512.yaml",
            "--inference_ckpt_path", "checkpoints/latentsync_unet.pt",
            "--inference_steps", str(config.LIPSYNC_STEPS), "--guidance_scale", str(config.LIPSYNC_GUIDANCE),
            "--seed", str(config.SEED), "--enable_deepcache",
            "--video_path", str(base_video.resolve()),
            "--audio_path", str(audio.resolve()),
            "--video_out_path", str(out.resolve()),
        ], cwd=repo)
        return out
