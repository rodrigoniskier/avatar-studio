import os
os.environ["STUDIO_NORMALIZE"] = "0"  # testes usam arquivos falsos, sem ffmpeg
os.environ["STUDIO_TTS"] = "mock"
os.environ["STUDIO_LIPSYNC"] = "mock"
