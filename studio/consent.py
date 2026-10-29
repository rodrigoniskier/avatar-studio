"""Só gera mídia de pessoas que consentiram. Cada perfil exige consent.json."""
import json
from datetime import datetime, timezone
from pathlib import Path

STATEMENT = (
    "Declaro que sou a pessoa retratada nos arquivos de voz e vídeo deste perfil "
    "(ou tenho autorização escrita dela) e autorizo a geração de mídia sintética."
)


def register(profile: Path, name: str) -> None:
    profile.mkdir(parents=True, exist_ok=True)
    (profile / "consent.json").write_text(json.dumps({
        "name": name,
        "statement": STATEMENT,
        "accepted_at": datetime.now(timezone.utc).isoformat(),
    }, ensure_ascii=False, indent=2))


def require(profile: Path) -> None:
    if not (profile / "consent.json").exists():
        raise PermissionError(f"Perfil sem consentimento registrado: {profile.name}")
