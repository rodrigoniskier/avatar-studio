"""`studio doctor`: diz em português o que está pronto e o que falta."""
import shutil
import subprocess
from pathlib import Path

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
    if config.TTS_ENGINE != "mock" or (mode in {"dub", "motion"} and config.LIPSYNC_ENGINE != "mock") or mode != "dub":
        gpu = shutil.which("nvidia-smi") and subprocess.run(
            ["nvidia-smi", "-L"], capture_output=True).returncode == 0
        line(gpu, "GPU NVIDIA detectada", "no Kaggle: Session options -> Accelerator -> GPU")
    lipsync = config.LIPSYNC_ENGINE if mode in {"dub", "motion"} else None
    for name, engine in (("chatterbox", config.TTS_ENGINE), ("musetalk", lipsync),
                         ("latentsync", lipsync)):
        if engine == name:
            line((config.VENVS / name / ".ready").exists(), f"ambiente do {name}",
                 "rode: bash scripts/setup_upstreams.sh " + (name if name != "chatterbox" else "musetalk"))
    if lipsync == "musetalk":
        line((config.UPSTREAMS / "MuseTalk/models/musetalkV15/unet.pth").exists(),
             "pesos do MuseTalk baixados", "rode: bash scripts/setup_upstreams.sh musetalk")
        line((config.UPSTREAMS / "MuseTalk/models/face-parse-bisent/79999_iter.pth").exists(),
             "pesos auxiliares (face-parse) baixados", "rode: bash scripts/setup_upstreams.sh musetalk")
    if config.TTS_ENGINE == "qwen3":
        line((config.VENVS / "qwen3/.ready").exists() and (config.MODELS / "qwen3/config.json").exists(),
             "Qwen3 e pesos locais", "bash scripts/setup_generative.sh qwen3")
    if mode != "dub":
        from . import resources
        engine = "wan-animate" if mode == "motion" else config.VIDEO_ENGINE
        line((config.VENVS / engine / ".ready").exists(), f"ambiente de {engine}",
             f"bash scripts/setup_generative.sh {engine}")
        marker = config.MODELS / ("wan-animate/download.json" if engine == "wan-animate"
                                  else "infinitetalk/InfiniteTalk/download.json")
        line(marker.exists(), "pesos de vídeo locais", f"bash scripts/setup_generative.sh {engine}")
        if engine == "wan-animate":
            for name in ("pose2d/vitpose_h_wholebody.onnx", "det/yolov10m.onnx"):
                line((config.MODELS / "wan-animate/process_checkpoint" / name).exists(), "Pré-processador " + name)
        elif engine == "infinitetalk":
            for name in ("chinese-wav2vec2-base/model.safetensors", "Wan2.1-I2V-14B-480P/config.json",
                         "InfiniteTalk/single/infinitetalk.safetensors"):
                line((config.MODELS / "infinitetalk" / name).exists(), "Arquivo de modelo " + name)
        report = resources.check(engine)
        line(report["ok"], "Orçamento conservador de RAM/VRAM", " ".join(report["reasons"]))
        if (config.VENVS / engine / ".ready").exists():
            repo = config.UPSTREAMS / ("Wan2.2" if engine == "wan-animate" else "InfiniteTalk")
            try:
                check = subprocess.run([config.venv_python(engine), str(Path(__file__).parent / "engines/_video_worker.py"),
                                        engine, "--check-only"], cwd=repo, capture_output=True, text=True, timeout=60)
                line(check.returncode == 0, "Importação e microensaio CUDA/SDPA", check.stderr[-500:])
            except (OSError, subprocess.TimeoutExpired) as error:
                line(False, "Microensaio de atenção indisponível", str(error))
    print("\nPré-checagens passaram; valide inferência e qualidade com seus arquivos." if ok else "\nCorrija os itens [FALTA] acima.")
    return ok
