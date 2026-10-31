"""Verificações técnicas reais; identidade/anatomia exigem revisão visual explícita."""
from . import media


def inspect(video, audio) -> dict:
    info = media.probe(video)
    videos = [s for s in info["streams"] if s["codec_type"] == "video"]
    audios = [s for s in info["streams"] if s["codec_type"] == "audio"]
    if not videos or not audios:
        raise ValueError("O resultado não contém imagem e áudio válidos.")
    expected = media.duration(audio)
    actual = float(videos[0].get("duration") or info["format"]["duration"])
    if abs(expected - actual) > max(0.5, expected * 0.02):
        raise ValueError(f"Duração incompatível: fala {expected:.2f}s, imagem {actual:.2f}s.")
    # Decode the complete file; a valid header alone cannot detect truncation/corrupt frames.
    media._run(["ffmpeg", "-v", "error", "-xerror", "-i", str(video), "-f", "null", "-"])
    return {"technical": "passed", "width": videos[0]["width"], "height": videos[0]["height"],
            "seconds": actual, "visual_review": "pending",
            "identity": "not_measured", "anatomy": "not_measured", "lip_sync": "not_measured",
            "checklist": ["Rosto mantém identidade", "Boca e dentes sem deformação",
                          "Mãos e corpo coerentes", "Sem cintilação ou cortes estranhos",
                          "Voz natural e texto correto", "Lábios sincronizados com a fala"]}
