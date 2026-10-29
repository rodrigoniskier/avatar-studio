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


HELPER = """
def _save_png(path, img):
    img = np.ascontiguousarray(img)
    if not cv2.imwrite(path, img):  # o cv2 falha em silêncio; tenta de novo com PIL
        from PIL import Image as _Image
        _Image.fromarray(img[:, :, ::-1]).save(path)

"""
# (trecho original, substituto): o inference.py do MuseTalk engole erros; aqui eles aparecem no log
PATCHES = [
    ("def fast_check_ffmpeg():", HELPER + "def fast_check_ffmpeg():"),
    ('cv2.imwrite(f"{result_img_save_path}/{str(i).zfill(8)}.png", combine_frame)',
     '_save_png(f"{result_img_save_path}/{str(i).zfill(8)}.png", combine_frame)'),
    # tipos numpy/negativos no dsize do cv2.resize eram descartados em silêncio pelo except
    ("res_frame = cv2.resize(res_frame.astype(np.uint8), (x2-x1, y2-y1))",
     "res_frame = cv2.resize(np.ascontiguousarray(res_frame, dtype=np.uint8), (int(x2-x1), int(y2-y1)))"),
    ("                except:\n                    continue",
     # sem rosto detectado (bbox 0,0,0,0) o quadro original é mantido: a sequência de PNG fica
     # completa (o ffmpeg exige começar em 0) e o áudio continua sincronizado
     "                except Exception as _e:\n"
     "                    print('quadro ignorado:', i, bbox, repr(_e), flush=True)\n"
     "                    _save_png(f\"{result_img_save_path}/{str(i).zfill(8)}.png\", ori_frame)\n"
     "                    continue"),
    ('            print("Video generation command:", cmd_img2video)',
     '            print("Quadros gravados:", len(os.listdir(result_img_save_path)), "em", result_img_save_path, flush=True)\n'
     '            print("Video generation command:", cmd_img2video)'),
]


def patched_inference(repo: Path, dest: Path) -> Path:
    src = (repo / "scripts" / "inference.py").read_text()
    for old, new in PATCHES:
        if old not in src:
            raise RuntimeError(f"MuseTalk mudou: trecho não encontrado: {old[:60]!r}")
        src = src.replace(old, new, 1)
    dest.write_text(src)
    return dest


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
            script = patched_inference(repo, tmp / "inference_patched.py")
            notes = run_logged([
                config.venv_python("musetalk"), str(script),
                "--inference_config", str(cfg),
                "--result_dir", str(tmp / "res"),
                "--unet_model_path", "models/musetalkV15/unet.pth",
                "--unet_config", "models/musetalkV15/musetalk.json",
                "--version", "v15", "--use_float16",
            ], cwd=repo, env={"PYTHONPATH": str(repo)})
            made = [f for f in sorted((tmp / "res").rglob("*.mp4")) if not f.name.startswith("temp")]
            if not made:
                # o MuseTalk não avisa quando falha ao gravar os quadros/vídeo
                raise RuntimeError("O MuseTalk terminou sem gerar o vídeo (provável falta de espaço em disco "
                                   "ou falha do ffmpeg). Avisos do MuseTalk:\n" + "\n".join(notes)
                                   + f"\n{disk_report()}")
            shutil.copy(made[0], out)
        return out
