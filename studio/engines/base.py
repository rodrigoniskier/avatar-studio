from abc import ABC, abstractmethod
from pathlib import Path


class TTSEngine(ABC):
    @abstractmethod
    def synthesize(self, text: str, voice_ref: Path, out: Path, lang: str = "pt") -> Path:
        """Gera `out` (wav) com a voz de `voice_ref`."""


class LipSyncEngine(ABC):
    @abstractmethod
    def render(self, base_video: Path, audio: Path, out: Path) -> Path:
        """Gera `out` (mp4) com o rosto de `base_video` falando `audio`."""
