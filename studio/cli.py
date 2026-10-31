import argparse
import json
import uuid
from pathlib import Path

from . import config, consent, doctor, media, pipeline, profiles


def main():
    parser = argparse.ArgumentParser(prog="studio")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("profile", help="cria perfil preservando os originais")
    p.add_argument("name")
    p.add_argument("--voice", required=True, type=Path)
    p.add_argument("--video", required=True, type=Path)
    p.add_argument("--image", type=Path)
    p.add_argument("--transcript", default="", help="transcrição exata do trecho de referência")
    p.add_argument("--voice-start", type=float, default=0)
    p.add_argument("--voice-seconds", type=float, default=20)
    p.add_argument("--i-consent", action="store_true", help=consent.STATEMENT)
    g = sub.add_parser("generate", help="prepara áudio; ouça antes de aprovar")
    g.add_argument("profile")
    g.add_argument("text")
    g.add_argument("--lang", default="pt")
    g.add_argument("--mode", choices=["dub", "avatar", "motion"], default="dub")
    g.add_argument("--prompt", default="Natural speaking, restrained gestures, static camera.")
    g.add_argument("--motion", type=Path)
    a = sub.add_parser("approve-audio", help="aprova a fala e renderiza; pode retomar cenas prontas")
    a.add_argument("job_id")
    d = sub.add_parser("doctor", help="verifica o ambiente")
    d.add_argument("--mode", choices=["dub", "avatar", "motion"], default="dub")
    w = sub.add_parser("worker", help="processa a fila persistente sem abrir servidor")
    w.add_argument("--once", action="store_true")
    s = sub.add_parser("serve", help="abre a interface")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    if args.cmd == "profile":
        if not args.i_consent:
            parser.error("use --i-consent para confirmar a autorização")
        print(profiles.create(args.name, args.voice, args.video, image=args.image, transcript=args.transcript,
                              voice_start=args.voice_start, voice_seconds=args.voice_seconds))
    elif args.cmd == "generate":
        jid = uuid.uuid4().hex[:12]
        if args.mode == "motion":
            if not args.motion:
                parser.error("--mode motion requer --motion")
            folder = config.job_dir(jid)
            folder.mkdir(parents=True)
            media.prepare_video(args.motion, folder / "motion.mp4", min_seconds=0.1, max_seconds=None)
        print(pipeline.generate(args.profile, args.text, args.lang, jid, mode=args.mode, prompt=args.prompt))
        print(f"Ouça o áudio. Para aprovar: studio approve-audio {jid}")
    elif args.cmd == "approve-audio":
        pipeline.approve(args.job_id)
        request = json.loads((config.job_dir(args.job_id) / "job.json").read_text())
        print(pipeline.generate(**request, job_id=args.job_id, audio_approved=True))
        print("Confira quality.json e revise rosto, mãos, boca e sincronização antes de publicar.")
    elif args.cmd == "doctor":
        raise SystemExit(0 if doctor.run(args.mode) else 1)
    elif args.cmd == "worker":
        from .jobs import Worker, drain_one
        if args.once:
            drain_one()
        else:
            Worker().run()
    else:
        if args.host not in {"127.0.0.1", "localhost", "::1"} and not config.ACCESS_TOKEN:
            parser.error("Defina STUDIO_ACCESS_TOKEN antes de abrir acesso à rede.")
        import uvicorn
        uvicorn.run("studio.api:app", host=args.host, port=args.port)
