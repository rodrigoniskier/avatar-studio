from .base import LipSyncEngine, TTSEngine


def get_tts(name: str) -> TTSEngine:
    if name == "chatterbox":
        from .chatterbox_tts import ChatterboxTTS
        return ChatterboxTTS()
    if name == "qwen3":
        from .qwen_tts import QwenTTS
        return QwenTTS()
    if name == "mock":
        from .mock import MockTTS
        return MockTTS()
    raise ValueError(f"Motor de voz desconhecido: {name}")


def get_lipsync(name: str) -> LipSyncEngine:
    if name == "latentsync":
        from .latentsync_lipsync import LatentSync
        return LatentSync()
    if name == "musetalk":
        from .musetalk_lipsync import MuseTalk
        return MuseTalk()
    if name == "mock":
        from .mock import MockLipSync
        return MockLipSync()
    raise ValueError(f"Motor de sincronização desconhecido: {name}")


def get_video(name: str):
    if name == "infinitetalk":
        from .generative import InfiniteTalk
        return InfiniteTalk()
    if name == "wan-animate":
        from .generative import WanAnimate
        return WanAnimate()
    raise ValueError(f"Motor de geração desconhecido: {name}")
