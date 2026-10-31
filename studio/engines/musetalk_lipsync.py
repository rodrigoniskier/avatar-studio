"""Lip-sync rápido com MuseTalk 1.5 (MIT). Funciona em GPUs pequenas (>=4 GB, fp16)."""
import json
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
PICK = Path(__file__).with_name("_pick_segment.py")
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


def pick_segment(base_video: Path, strict: bool = False) -> dict:
    """Início do trecho mais estável do vídeo base (rosto inteiro, parado). 0 se não der para decidir."""
    try:
        r = subprocess.run([config.venv_python("musetalk"), str(PICK), str(base_video), str(BASE_SECONDS)],
                           capture_output=True, text=True, timeout=600, check=True)
        info = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception as e:  # sem OpenCV/venv ou vídeo ilegível: comportamento antigo
        if strict:
            raise RuntimeError(f"Não foi possível avaliar o enquadramento do rosto: {e}") from e
        print(f"Não foi possível escolher o trecho do vídeo base ({e}); usando o início.", flush=True)
        return {"start": 0.0, "window_s": BASE_SECONDS}
    if strict and (not info.get("found") or info.get("score", 0) > 0.5):
        raise RuntimeError("Nenhum trecho com rosto inteiro e estável foi encontrado. "
                           "Use uma referência com câmera parada e rosto visível.")
    if info.get("found"):
        print(f"Trecho estável do vídeo base: começa em {info['start']} s "
              f"(janela de {info.get('window_s')} s, rosto ocupa {info.get('face_width_ratio')} da largura).",
              flush=True)
    else:
        print("Nenhum trecho estável com rosto inteiro foi encontrado no vídeo base; usando o início. "
              "Regrave com o rosto centralizado e a câmera parada.", flush=True)
    return {"start": float(info.get("start", 0.0)),
            "window_s": float(info.get("window_s", BASE_SECONDS))}


def pick_start(base_video: Path) -> float:
    return pick_segment(base_video)["start"]


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
            selected = pick_segment(base_video.resolve(), strict=True)
            start = selected["start"]
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(start), "-i", str(base_video.resolve()),
                            "-t", str(selected["window_s"]), "-an", "-c:v", "libx264", "-preset", "veryfast",
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
            if any("quadro ignorado:" in note for note in notes):
                raise RuntimeError("MuseTalk não conseguiu sincronizar todos os quadros. "
                                   "O resultado precisa de outra referência ou ajuste de enquadramento.\n"
                                   + "\n".join(notes))
            shutil.copy(made[0], out)
        return out
