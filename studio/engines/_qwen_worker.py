"""Executado no ambiente isolado do Qwen; sem serviços externos de inferência."""
import json
import sys

import soundfile as sf
import torch
from qwen_tts import Qwen3TTSModel

req = json.load(sys.stdin)
torch.manual_seed(req["seed"])
languages = {"pt": "Portuguese", "en": "English", "es": "Spanish"}
model = Qwen3TTSModel.from_pretrained(
    req["model"], device_map=req["device"],
    dtype=(torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16)
    if req["device"].startswith("cuda") else torch.float32,
    attn_implementation="sdpa")
prompt = model.create_voice_clone_prompt(ref_audio=req["ref"], ref_text=req["ref_text"],
                                       x_vector_only_mode=False)
for text, out in zip(req["texts"], req["outs"]):
    waves, sr = model.generate_voice_clone(text=text, language=languages[req["lang"]],
                                          voice_clone_prompt=prompt)
    sf.write(out, waves[0], sr)
