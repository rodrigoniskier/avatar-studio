from abc import ABC, abstractmethod
from pathlib import Path


class TTSEngine(ABC):
    @abstractmethod
    def synthesize(self, text: str, voice_ref: Path, out: Path, lang: str = "pt") -> Path:
        """Gera `out` (wav) com a voz de `voice_ref`."""

    def synthesize_batch(self, texts: list[str], voice_ref: Path, out_dir: Path,
                         lang: str = "pt") -> list[Path]:
        """Gera um wav por texto; engines pesados sobrescrevem para carregar o modelo uma vez."""
        return [self.synthesize(t, voice_ref, out_dir / f"part{i}.wav", lang)
                for i, t in enumerate(texts)]


class LipSyncEngine(ABC):
    @abstractmethod
    def render(self, base_video: Path, audio: Path, out: Path) -> Path:
        """Gera `out` (mp4) com o rosto de `base_video` falando `audio`."""
