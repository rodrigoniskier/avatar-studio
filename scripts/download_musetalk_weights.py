"""Baixa os pesos do MuseTalk 1.5 (substitui o download_weights.sh oficial, que está quebrado:
usa o `huggingface-cli` descontinuado e atualiza o huggingface_hub, o que quebra o transformers).
Uso (dentro do venv do musetalk): python download_musetalk_weights.py <pasta models>"""
import sys
import urllib.request
from pathlib import Path

from huggingface_hub import hf_hub_download

models = Path(sys.argv[1])
HF = [  # (repo, arquivo, subpasta)
    ("TMElyralab/MuseTalk", "musetalkV15/musetalk.json", "."),
    ("TMElyralab/MuseTalk", "musetalkV15/unet.pth", "."),
    ("stabilityai/sd-vae-ft-mse", "config.json", "sd-vae"),
    ("stabilityai/sd-vae-ft-mse", "diffusion_pytorch_model.bin", "sd-vae"),
    ("openai/whisper-tiny", "config.json", "whisper"),
    ("openai/whisper-tiny", "pytorch_model.bin", "whisper"),
    ("openai/whisper-tiny", "preprocessor_config.json", "whisper"),
    ("yzd-v/DWPose", "dw-ll_ucoco_384.pth", "dwpose"),
    ("ByteDance/LatentSync", "latentsync_syncnet.pt", "syncnet"),
]
for repo, fname, sub in HF:
    dest = models / sub / fname
    if dest.exists() and dest.stat().st_size > 0:
        continue
    print(f"baixando {repo}/{fname}", flush=True)
    hf_hub_download(repo, fname, local_dir=str(models / sub))

fp = models / "face-parse-bisent"
fp.mkdir(parents=True, exist_ok=True)
if not (fp / "79999_iter.pth").exists():
    import gdown
    print("baixando face-parse (Google Drive)", flush=True)
    gdown.download(id="154JgKpzCPW82qINcVieuPH3fZ2e0P812", output=str(fp / "79999_iter.pth"), quiet=False)
if not (fp / "resnet18-5c106cde.pth").exists():
    urllib.request.urlretrieve("https://download.pytorch.org/models/resnet18-5c106cde.pth",
                               fp / "resnet18-5c106cde.pth")

required = [models / "musetalkV15/unet.pth", models / "musetalkV15/musetalk.json",
            models / "sd-vae/diffusion_pytorch_model.bin", models / "whisper/pytorch_model.bin",
            models / "dwpose/dw-ll_ucoco_384.pth", models / "syncnet/latentsync_syncnet.pt",
            fp / "79999_iter.pth", fp / "resnet18-5c106cde.pth"]
missing = [str(f) for f in required if not f.exists() or f.stat().st_size == 0]
if missing:
    sys.exit("FALTAM pesos:\n" + "\n".join(missing))
print("Pesos do MuseTalk OK")
