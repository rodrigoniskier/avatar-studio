"""Engines falsos: permitem testar toda a aplicação sem GPU."""
import math
import shutil
import struct
import wave

from .base import LipSyncEngine, TTSEngine


class MockTTS(TTSEngine):
    def synthesize(self, text, voice_ref, out, lang="pt"):
        sr, secs = 16000, max(1.0, len(text) / 15)
        with wave.open(str(out), "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
            w.writeframes(b"".join(
                struct.pack("<h", int(3000 * math.sin(2 * math.pi * 220 * i / sr)))
                for i in range(int(sr * secs))))
        return out


class MockLipSync(LipSyncEngine):
    def render(self, base_video, audio, out, *, preserve_motion=False):
        shutil.copy(base_video, out)
        return out
