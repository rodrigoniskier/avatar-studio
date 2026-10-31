"""Executado no ambiente isolado do Qwen; sem serviços externos de inferência."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import soundfile as sf
import torch
from qwen_tts import Qwen3TTSModel
from studio.engines.attention_compat import inference_dtype

req = json.load(sys.stdin)
torch.manual_seed(req["seed"])
languages = {"pt": "Portuguese", "en": "English", "es": "Spanish"}
model = Qwen3TTSModel.from_pretrained(
    req["model"], device_map=req["device"],
    dtype=inference_dtype(req["device"]),
    attn_implementation="sdpa")
prompt = model.create_voice_clone_prompt(ref_audio=req["ref"], ref_text=req["ref_text"],
                                       x_vector_only_mode=False)
for text, out in zip(req["texts"], req["outs"]):
    waves, sr = model.generate_voice_clone(text=text, language=languages[req["lang"]],
                                          voice_clone_prompt=prompt)
    sf.write(out, waves[0], sr)
