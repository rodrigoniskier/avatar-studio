"""Roteiro opcional com Gemini (chave gratuita do Google AI Studio, GEMINI_API_KEY)."""
import os


def draft_script(topic: str, seconds: int = 60, lang: str = "português do Brasil") -> str:
    from google import genai
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    prompt = (f"Escreva a fala de um vídeo de ~{seconds}s em {lang} sobre: {topic}. "
              "Apenas o texto falado, frases curtas, sem marcações ou emojis.")
    return client.models.generate_content(
        model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"), contents=prompt).text.strip()
