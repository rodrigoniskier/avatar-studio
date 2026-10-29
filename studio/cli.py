import argparse
import shutil
from pathlib import Path

from . import config, consent, pipeline


def main():
    p = argparse.ArgumentParser(prog="studio")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("profile", help="cria perfil (voz + vídeo base) com consentimento")
    a.add_argument("name"); a.add_argument("--voice", required=True, type=Path)
    a.add_argument("--video", required=True, type=Path)
    a.add_argument("--i-consent", action="store_true", help=consent.STATEMENT)

    g = sub.add_parser("generate", help="gera vídeo a partir de texto")
    g.add_argument("profile"); g.add_argument("text"); g.add_argument("--lang", default="pt")

    s = sub.add_parser("serve", help="sobe a API + interface web")
    s.add_argument("--host", default="127.0.0.1"); s.add_argument("--port", type=int, default=8000)

    args = p.parse_args()
    if args.cmd == "profile":
        if not args.i_consent:
            p.error("use --i-consent para confirmar: " + consent.STATEMENT)
        pdir = config.profile_dir(args.name)
        consent.register(pdir, args.name)
        shutil.copy(args.voice, pdir / "voice.wav"); shutil.copy(args.video, pdir / "avatar.mp4")
        print(f"Perfil criado em {pdir}")
    elif args.cmd == "generate":
        print(pipeline.generate(args.profile, args.text, args.lang))
    else:
        import uvicorn
        uvicorn.run("studio.api:app", host=args.host, port=args.port)
