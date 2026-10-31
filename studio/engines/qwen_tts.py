"""Clonagem local com Qwen3-TTS Base; áudio e transcrição da mesma referência."""
import json
import shutil
from pathlib import Path

from .. import config
from ..runner import run_logged
from .base import TTSEngine


class QwenTTS(TTSEngine):
    def validate_reference(self, voice_ref, lang="pt"):
        model = config.MODELS / "qwen3"
        if not (model / "config.json").exists():
            raise FileNotFoundError("Instale o modelo local: bash scripts/setup_generative.sh qwen3")
        manifest = model / "download.json"
        if not manifest.exists() or json.loads(manifest.read_text()).get("repo") != config.QWEN_MODEL:
            raise ValueError("O Qwen instalado difere de STUDIO_QWEN_MODEL. Instale o modelo selecionado em uma pasta nova.")
        if not (model / "speech_tokenizer/config.json").exists():
            raise FileNotFoundError("O tokenizer de voz local está ausente. Complete o download do modelo Base.")
        transcript = voice_ref.with_suffix(".txt")
        if not transcript.exists() or not transcript.read_text().strip():
            raise ValueError("Qwen3 requer a transcrição exata do trecho de referência (voice.txt).")
        import os
        if os.getenv("STUDIO_TRANSCRIBE", "0") == "1":
            from .. import audio_quality
            from ..artifacts import write_json
            report = audio_quality.inspect(voice_ref, transcript.read_text(), lang)
            write_json(voice_ref.with_name("reference_quality.json"), report)
            if report.get("word_error_rate", 0) > 0.5:
                raise ValueError("A transcrição da referência divergiu do áudio. Confira voice.wav e voice.txt; o transcritor também pode errar.")

    def synthesize(self, text, voice_ref, out, lang="pt"):
        made = self.synthesize_batch([text], voice_ref, out.parent, lang)[0]
        if made != out:
            shutil.copyfile(made, out)
        return out

    def synthesize_batch(self, texts, voice_ref, out_dir, lang="pt"):
        self.validate_reference(voice_ref, lang)
        model = config.MODELS / "qwen3"
        transcript = voice_ref.with_suffix(".txt")
        outs = [out_dir / f"part{i}.wav" for i in range(len(texts))]
        request = {"texts": texts, "ref": str(voice_ref.resolve()),
                   "ref_text": transcript.read_text().strip(), "outs": [str(x.resolve()) for x in outs],
                   "lang": lang, "device": config.DEVICE, "model": str(model),
                   "seed": config.SEED}
        run_logged([config.venv_python("qwen3"), str(Path(__file__).with_name("_qwen_worker.py"))],
                   input_text=json.dumps(request))
        return outs
