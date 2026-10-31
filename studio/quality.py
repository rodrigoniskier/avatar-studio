"""Verificações técnicas reais; identidade/anatomia exigem revisão visual explícita."""
from . import media
import subprocess


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
    if audios[0].get("duration") is not None:
        if abs(float(audios[0]["duration"]) - expected) > max(0.5, expected * .02):
            raise ValueError("A faixa de áudio do resultado não cobre a fala aprovada.")
    # Decode the complete file; a valid header alone cannot detect truncation/corrupt frames.
    decoded = subprocess.run(["ffmpeg", "-v", "info", "-xerror", "-i", str(video),
                              "-vf", "blackdetect=d=0.2:pix_th=0.1,freezedetect=n=-60dB:d=1",
                              "-an", "-f", "null", "-"], capture_output=True, text=True)
    if decoded.returncode:
        raise ValueError("Erro de decodificação do resultado: " + decoded.stderr[-300:])
    warnings = []
    if "black_start:" in decoded.stderr:
        warnings.append("Há trechos muito escuros/pretos; confira se a imagem foi gerada corretamente.")
    if "freeze_start:" in decoded.stderr:
        warnings.append("Há imagem estática por pelo menos 1 s; confira a atuação.")
    return {"technical": "passed", "width": videos[0]["width"], "height": videos[0]["height"],
            "scope": "integrity_duration_and_signal_only", "warnings": warnings,
            "seconds": actual, "visual_review": "pending",
            "identity": "not_measured", "anatomy": "not_measured", "lip_sync": "not_measured",
            "checklist": ["Rosto mantém identidade", "Boca e dentes sem deformação",
                          "Mãos e corpo coerentes", "Sem cintilação ou cortes estranhos",
                          "Voz natural e texto correto", "Lábios sincronizados com a fala"]}
