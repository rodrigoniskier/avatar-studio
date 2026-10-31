"""`studio doctor`: diz em português o que está pronto e o que falta."""
import shutil
import subprocess

from . import config


def run(mode: str = "dub") -> bool:
    ok = True

    def line(good, msg, fix=""):
        nonlocal ok
        ok &= bool(good)
        print(("[OK]   " if good else "[FALTA] ") + msg + ("" if good else f"  -> {fix}"))

    line(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg instalado", "instale o ffmpeg")
    from .engines import get_tts, get_lipsync, get_video
    try:
        get_tts(config.TTS_ENGINE)
        if mode in {"dub", "motion"}:
            get_lipsync(config.LIPSYNC_ENGINE)
        if mode != "dub":
            get_video("wan-animate" if mode == "motion" else config.VIDEO_ENGINE)
    except ValueError as error:
        line(False, str(error))
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
        line((config.UPSTREAMS / "MuseTalk/models/face-parse-bisent/79999_iter.pth").exists(),
             "pesos auxiliares (face-parse) baixados", "rode: bash scripts/setup_upstreams.sh musetalk")
    if config.TTS_ENGINE == "qwen3":
        line((config.VENVS / "qwen3/.ready").exists() and (config.MODELS / "qwen3/config.json").exists(),
             "Qwen3 e pesos locais", "bash scripts/setup_generative.sh qwen3")
    if mode != "dub":
        engine = "wan-animate" if mode == "motion" else config.VIDEO_ENGINE
        line((config.VENVS / engine / ".ready").exists(), f"ambiente de {engine}",
             f"bash scripts/setup_generative.sh {engine}")
        marker = config.MODELS / ("wan-animate/download.json" if engine == "wan-animate"
                                  else "infinitetalk/InfiniteTalk/download.json")
        line(marker.exists(), "pesos de vídeo locais", f"bash scripts/setup_generative.sh {engine}")
        print("[INFO] Modelos de vídeo 14B: uso de memória e compatibilidade dependem da GPU e RAM. "
              "A instalação não comprova capacidade de inferência. Não existe fallback pago.")
    print("\nTudo pronto!" if ok else "\nCorrija os itens [FALTA] acima.")
    return ok
