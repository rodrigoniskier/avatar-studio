"""`studio doctor`: diz em português o que está pronto e o que falta."""
import shutil
import subprocess

from . import config


def run() -> bool:
    ok = True

    def line(good, msg, fix=""):
        nonlocal ok
        ok &= bool(good)
        print(("[OK]   " if good else "[FALTA] ") + msg + ("" if good else f"  -> {fix}"))

    line(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg instalado", "instale o ffmpeg")
    if config.TTS_ENGINE != "mock" or config.LIPSYNC_ENGINE != "mock":
        gpu = shutil.which("nvidia-smi") and subprocess.run(
            ["nvidia-smi", "-L"], capture_output=True).returncode == 0
        line(gpu, "GPU NVIDIA detectada", "no Kaggle: Session options -> Accelerator -> GPU")
    for name, engine in (("chatterbox", config.TTS_ENGINE), ("musetalk", config.LIPSYNC_ENGINE),
                         ("latentsync", config.LIPSYNC_ENGINE)):
        if engine == name:
            line((config.VENVS / name / ".ready").exists(), f"ambiente do {name}",
                 "rode: bash scripts/setup_upstreams.sh " + (name if name != "chatterbox" else "musetalk"))
    if config.LIPSYNC_ENGINE == "musetalk":
        line((config.UPSTREAMS / "MuseTalk/models/musetalkV15/unet.pth").exists(),
             "pesos do MuseTalk baixados", "rode: bash scripts/setup_upstreams.sh musetalk")
    print("\nTudo pronto!" if ok else "\nCorrija os itens [FALTA] acima.")
    return ok
