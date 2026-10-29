"""Voz clonada com Chatterbox (MIT, pt-BR suportado). Requer GPU ou CPU lenta."""
import sys
from pathlib import Path

from .. import config
from .base import TTSEngine


class ChatterboxTTS(TTSEngine):
    def __init__(self):
        sys.path.insert(0, str(config.UPSTREAMS / "chatterbox" / "src"))
        from chatterbox.mtl_tts import ChatterboxMultilingualTTS
        self.model = ChatterboxMultilingualTTS.from_pretrained(
            device=config.DEVICE, t3_model="v3")

    def synthesize(self, text, voice_ref, out, lang="pt"):
        import torchaudio as ta
        # cfg_weight=0 evita herdar sotaque quando idioma do texto != idioma da referência
        wav = self.model.generate(text, language_id=lang,
                                  audio_prompt_path=str(voice_ref), cfg_weight=0.3)
        ta.save(str(out), wav, self.model.sr)
        return out
