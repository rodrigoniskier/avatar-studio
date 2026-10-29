"""Lip-sync rápido com MuseTalk 1.5 (MIT). Funciona em GPUs pequenas (>=4 GB, fp16)."""
import shutil
import subprocess
import tempfile
from pathlib import Path

from .. import config
from ..runner import disk_report, run_logged
from .base import LipSyncEngine

# O MuseTalk analisa TODOS os quadros do vídeo base a cada geração (~11 quadros/s) e repete o
# trecho em vai-e-volta se a fala for mais longa. 20 s bastam e economizam minutos, RAM e disco.
BASE_SECONDS = 20
MIN_FREE_GB = 3


class MuseTalk(LipSyncEngine):
    def render(self, base_video, audio, out):
        repo = config.UPSTREAMS / "MuseTalk"
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            free_gb = shutil.disk_usage(tmp).free / 1e9
            if free_gb < MIN_FREE_GB:
                raise RuntimeError(f"Pouco espaço em disco ({free_gb:.1f} GB livres). "
                                   f"O MuseTalk precisa de pelo menos {MIN_FREE_GB} GB.\n{disk_report()}")
            short = tmp / "base.mp4"
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(base_video.resolve()),
                            "-t", str(BASE_SECONDS), "-an", "-c:v", "libx264", "-preset", "veryfast",
                            "-crf", "17", "-pix_fmt", "yuv420p", str(short)], check=True)
            cfg = tmp / "task.yaml"
            cfg.write_text(f"task_0:\n video_path: \"{short}\"\n"
                           f" audio_path: \"{audio.resolve()}\"\n")
            run_logged([
                config.venv_python("musetalk"), "-m", "scripts.inference",
                "--inference_config", str(cfg),
                "--result_dir", str(tmp / "res"),
                "--unet_model_path", "models/musetalkV15/unet.pth",
                "--unet_config", "models/musetalkV15/musetalk.json",
                "--version", "v15", "--use_float16",
            ], cwd=repo)
            made = [f for f in sorted((tmp / "res").rglob("*.mp4")) if not f.name.startswith("temp")]
            if not made:
                # o MuseTalk não avisa quando falha ao gravar os quadros/vídeo
                raise RuntimeError("O MuseTalk terminou sem gerar o vídeo (provável falta de espaço em disco "
                                   f"ou falha do ffmpeg). Veja as últimas linhas do log.\n{disk_report()}")
            shutil.copy(made[0], out)
        return out
