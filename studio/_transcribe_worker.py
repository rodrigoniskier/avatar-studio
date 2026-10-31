"""Executado no ambiente isolado qa; baixa apenas pesos públicos de transcrição."""
import json
import sys

from faster_whisper import WhisperModel

audio, output, language = sys.argv[1:]
model = WhisperModel("small", device="cpu", compute_type="int8")
segments, info = model.transcribe(audio, language=language, vad_filter=True)
with open(output, "w") as f:
    json.dump({"transcription": "completed", "transcript": " ".join(s.text.strip() for s in segments)}, f)
