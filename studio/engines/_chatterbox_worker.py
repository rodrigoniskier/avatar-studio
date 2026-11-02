"""Roda DENTRO do venv do Chatterbox: lê JSON no stdin, carrega o modelo uma vez e sintetiza tudo."""
import json
import sys

import torchaudio as ta
import torch
from chatterbox.mtl_tts import ChatterboxMultilingualTTS

req = json.load(sys.stdin)
torch.manual_seed(req["seed"])
model = ChatterboxMultilingualTTS.from_pretrained(device=req["device"], t3_model="v3")
for text, out in zip(req["texts"], req["outs"]):
    # cfg_weight baixo reduz sotaque herdado quando idioma do texto != idioma da referência
    wav = model.generate(text, language_id=req["lang"], audio_prompt_path=req["ref"],
                         cfg_weight=req["cfg_weight"], exaggeration=req["exaggeration"])
    ta.save(out, wav, model.sr)
