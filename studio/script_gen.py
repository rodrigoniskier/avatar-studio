"""Roteiro opcional via Ollama local. O texto também pode ser colado manualmente."""
import json
import os
import urllib.request


def draft_script(topic: str, seconds: int = 60, lang: str = "português do Brasil") -> str:
    model = os.getenv("STUDIO_OLLAMA_MODEL", "qwen2.5:1.5b")
    if "cloud" in model.casefold():
        raise ValueError("Use apenas um modelo Ollama local; modelos cloud não são permitidos.")
    with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=10) as response:
        available = json.load(response).get("models", [])
    match = next((entry for entry in available if entry.get("name") == model), None)
    if not match or match.get("remote_host") or match.get("remote_model"):
        raise ValueError("O modelo deve estar instalado localmente e não pode encaminhar inferência à nuvem.")
    data = json.dumps({"model": model, "stream": False,
                       "prompt": f"Escreva apenas a fala de um vídeo de {seconds}s em {lang} sobre: {topic}."}).encode()
    request = urllib.request.Request("http://127.0.0.1:11434/api/generate", data=data,
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=180) as response:
        return json.load(response)["response"].strip()
