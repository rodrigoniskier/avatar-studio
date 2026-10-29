"""Lip-sync com LatentSync 1.6 (Apache-2.0). Exige ~18 GB de VRAM (1.5: ~8 GB)."""
import subprocess
from pathlib import Path

from .. import config
from .base import LipSyncEngine


class LatentSync(LipSyncEngine):
    def render(self, base_video, audio, out):
        repo = config.UPSTREAMS / "LatentSync"
        subprocess.run([
            "python", "-m", "scripts.inference",
            "--unet_config_path", "configs/unet/stage2_512.yaml",
            "--inference_ckpt_path", "checkpoints/latentsync_unet.pt",
            "--inference_steps", "20", "--guidance_scale", "1.5", "--enable_deepcache",
            "--video_path", str(base_video.resolve()),
            "--audio_path", str(audio.resolve()),
            "--video_out_path", str(out.resolve()),
        ], cwd=repo, check=True)
        return out
