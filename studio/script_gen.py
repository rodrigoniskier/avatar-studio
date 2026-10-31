"""Roteiro opcional via Ollama local. O texto também pode ser colado manualmente."""
import json
import os
import urllib.request


def draft_script(topic: str, seconds: int = 60, lang: str = "português do Brasil") -> str:
    data = json.dumps({"model": os.getenv("STUDIO_OLLAMA_MODEL", "qwen2.5:1.5b"), "stream": False,
                       "prompt": f"Escreva apenas a fala de um vídeo de {seconds}s em {lang} sobre: {topic}."}).encode()
    request = urllib.request.Request("http://127.0.0.1:11434/api/generate", data=data,
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=180) as response:
        return json.load(response)["response"].strip()
