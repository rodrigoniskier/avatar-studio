"""Clonagem local com Qwen3-TTS Base; áudio e transcrição da mesma referência."""
import json
import shutil
from pathlib import Path

from .. import config
from ..runner import run_logged
from .base import TTSEngine


class QwenTTS(TTSEngine):
    def synthesize(self, text, voice_ref, out, lang="pt"):
        made = self.synthesize_batch([text], voice_ref, out.parent, lang)[0]
        if made != out:
            shutil.copyfile(made, out)
        return out

    def synthesize_batch(self, texts, voice_ref, out_dir, lang="pt"):
        model = config.MODELS / "qwen3"
        if not (model / "config.json").exists():
            raise FileNotFoundError("Instale o modelo local: bash scripts/setup_generative.sh qwen3")
        transcript = voice_ref.with_suffix(".txt")
        if not transcript.exists() or not transcript.read_text().strip():
            raise ValueError("Qwen3 requer a transcrição exata do trecho de referência (voice.txt).")
        outs = [out_dir / f"part{i}.wav" for i in range(len(texts))]
        request = {"texts": texts, "ref": str(voice_ref.resolve()),
                   "ref_text": transcript.read_text().strip(), "outs": [str(x.resolve()) for x in outs],
                   "lang": lang, "device": config.DEVICE, "model": str(model),
                   "seed": config.SEED}
        run_logged([config.venv_python("qwen3"), str(Path(__file__).with_name("_qwen_worker.py"))],
                   input_text=json.dumps(request))
        return outs
