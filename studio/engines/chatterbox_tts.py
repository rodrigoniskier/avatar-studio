"""Voz clonada com Chatterbox (MIT, pt-BR suportado), em venv isolado (torch 2.6)."""
import json
from pathlib import Path

from .. import config
from ..runner import run_logged
from .base import TTSEngine

WORKER = Path(__file__).with_name("_chatterbox_worker.py")


class ChatterboxTTS(TTSEngine):
    def synthesize(self, text, voice_ref, out, lang="pt"):
        return self.synthesize_batch([text], voice_ref, out.parent, lang)[0]

    def synthesize_batch(self, texts, voice_ref, out_dir, lang="pt"):
        outs = [out_dir / f"part{i}.wav" for i in range(len(texts))]
        req = {"texts": texts, "ref": str(voice_ref.resolve()), "outs": [str(o) for o in outs],
               "lang": lang, "device": config.DEVICE}
        run_logged([config.venv_python("chatterbox"), str(WORKER)], input_text=json.dumps(req))
        return outs
