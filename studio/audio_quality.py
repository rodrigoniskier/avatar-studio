"""Inspeção de sinal e transcrição opcional, sempre por modelos locais."""
import array
import json
import math
import os
import re
import subprocess
import sys
from pathlib import Path

from . import config
from .runner import run_logged


def word_error_rate(expected: str, actual: str) -> float:
    ref = re.findall(r"\w+", expected.casefold())
    hyp = re.findall(r"\w+", actual.casefold())
    previous = list(range(len(hyp) + 1))
    for i, word in enumerate(ref, 1):
        row = [i]
        for j, other in enumerate(hyp, 1):
            row.append(min(row[-1] + 1, previous[j] + 1, previous[j - 1] + (word != other)))
        previous = row
    return previous[-1] / max(1, len(ref))


def inspect(audio: Path, expected: str, lang: str) -> dict:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(audio), "-ac", "1", "-ar", "16000",
                          "-f", "s16le", "-"], check=True, capture_output=True).stdout
    samples = array.array("h")
    samples.frombytes(raw)
    if sys.byteorder != "little":
        samples.byteswap()
    if not samples:
        raise ValueError("A fala gerada está vazia.")
    rms = math.sqrt(sum(x * x for x in samples) / len(samples))
    report = {"seconds": len(samples) / 16000, "peak": max(abs(x) for x in samples) / 32768,
              "clipped_fraction": sum(abs(x) >= 32760 for x in samples) / len(samples),
              "rms_dbfs": round(20 * math.log10(max(rms, 1) / 32768), 2),
              "transcription": "not_requested", "voice_similarity": "not_measured"}
    if rms < 1:
        raise ValueError("A fala gerada está silenciosa.")
    if os.getenv("STUDIO_TRANSCRIBE", "0") == "1":
        result = audio.with_name("transcription.json")
        run_logged([config.venv_python("qa"), str(Path(__file__).with_name("_transcribe_worker.py")),
                    str(audio.resolve()), str(result.resolve()), lang])
        report.update(json.loads(result.read_text()))
        report["word_error_rate"] = word_error_rate(expected, report["transcript"])
        report["note"] = "Divergências também podem vir do transcritor. Confira o áudio; não é medida de timbre."
    return report
