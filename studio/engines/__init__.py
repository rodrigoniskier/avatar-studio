from .base import LipSyncEngine, TTSEngine


def get_tts(name: str) -> TTSEngine:
    if name == "chatterbox":
        from .chatterbox_tts import ChatterboxTTS
        return ChatterboxTTS()
    from .mock import MockTTS
    return MockTTS()


def get_lipsync(name: str) -> LipSyncEngine:
    if name == "latentsync":
        from .latentsync_lipsync import LatentSync
        return LatentSync()
    if name == "musetalk":
        from .musetalk_lipsync import MuseTalk
        return MuseTalk()
    from .mock import MockLipSync
    return MockLipSync()
