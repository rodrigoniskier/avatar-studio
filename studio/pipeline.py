"""Produção por etapas: fala, aprovação, cenas, inspeção e revisão visual."""
import json
import math
import re
import shutil
import subprocess
import uuid
from pathlib import Path

from . import config, consent, media, quality, audio_quality, provenance, resources
from .artifacts import digest, signature, write_json
from .engines import get_lipsync, get_tts, get_video


def split_text(text: str, limit: int = 300) -> list[str]:
    if not text.strip():
        raise ValueError("O texto está vazio.")
    if limit < 1:
        raise ValueError("Limite inválido.")
    chunks, cur = [], ""
    for sentence in re.split(r"(?<=[.!?…])\s+", text.strip()):
        while len(sentence) > limit:
            cut = sentence.rfind(" ", 0, limit + 1)
            cut = cut if cut > 0 else limit
            if cur:
                chunks.append(cur)
                cur = ""
            chunks.append(sentence[:cut].strip())
            sentence = sentence[cut:].strip()
        if cur and len(cur) + len(sentence) + 1 > limit:
            chunks.append(cur)
            cur = sentence
        else:
            cur = f"{cur} {sentence}".strip()
    return chunks + ([cur] if cur else [])


def _concat_wavs(parts: list[Path], out: Path) -> None:
    if len(parts) == 1:
        shutil.copyfile(parts[0], out)
        return
    listing = out.with_suffix(".txt")
    listing.write_text("".join("file '" + str(p.resolve()).replace("'", "'\\''") + "'\n" for p in parts))
    media._run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                "-i", str(listing), "-c:a", "pcm_s16le", str(out)])


def engine_versions() -> dict:
    root = Path(__file__).parent / "engines"
    versions = {p.name: digest(p) for p in root.glob("*.py")}
    for name in ("pipeline.py", "media.py", "quality.py"):
        versions[name] = digest(Path(__file__).with_name(name))
    for name in ("chatterbox", "Qwen3-TTS", "MuseTalk", "LatentSync", "InfiniteTalk", "Wan2.2"):
        path = config.UPSTREAMS / name
        if (path / ".git").exists():
            result = subprocess.run(["git", "-C", str(path), "rev-parse", "HEAD"], capture_output=True, text=True)
            versions[name] = result.stdout.strip()
            versions[name + ":source"] = signature(provenance.inventory(path, {".py", ".yaml", ".yml"}, content=True))
    for path in config.MODELS.glob("**/download.json"):
        versions[str(path.relative_to(config.MODELS))] = digest(path)
    versions["tts_weights"] = (provenance.weights(config.MODELS / "qwen3") if config.TTS_ENGINE == "qwen3"
                               else provenance.chatterbox_weights() if config.TTS_ENGINE == "chatterbox" else "mock")
    versions["video_weights"] = signature({
        "generative": provenance.weights(config.MODELS / config.VIDEO_ENGINE),
        "wan": provenance.weights(config.MODELS / "wan-animate"),
        "musetalk": provenance.weights(config.UPSTREAMS / "MuseTalk/models"),
        "latentsync": provenance.weights(config.UPSTREAMS / "LatentSync/checkpoints")})
    return versions


def settings() -> dict:
    return {"tts": config.TTS_ENGINE, "lipsync": config.LIPSYNC_ENGINE, "video": config.VIDEO_ENGINE,
            "qwen_model": config.QWEN_MODEL, "revision": config.TTS_REVISION, "seed": config.SEED,
            "cfg": config.CFG_WEIGHT, "exaggeration": config.EXAGGERATION,
            "size": config.VIDEO_SIZE, "scene_seconds": config.SCENE_SECONDS,
            "lipsync_steps": config.LIPSYNC_STEPS, "lipsync_guidance": config.LIPSYNC_GUIDANCE,
            "versions": engine_versions()}


def speech_key(profile: str, text: str, lang: str) -> str:
    voice = config.profile_dir(profile) / "voice.wav"
    transcript = voice.with_suffix(".txt")
    opts = settings()
    # Video settings must not force re-synthesis. TTS implementations and upstream versions do.
    voice_versions = {k: v for k, v in opts["versions"].items()
                      if k in {"base.py", "tts_weights", "chatterbox_tts.py", "_chatterbox_worker.py", "qwen_tts.py", "_qwen_worker.py"}
                      or "qwen3" in k or k.startswith(("chatterbox", "Qwen3-TTS"))
                      or (config.TTS_ENGINE == "qwen3" and k == "attention_compat.py")}
    return signature({"schema": 3, "profile": profile, "text": text, "lang": lang,
                      "reference": digest(voice), "transcript": digest(transcript) if transcript.exists() else None,
                      "engine": opts["tts"], "model": opts["qwen_model"], "revision": opts["revision"],
                      "seed": opts["seed"], "cfg": opts["cfg"], "exaggeration": opts["exaggeration"],
                      "versions": voice_versions})


def _cached_speech(profile: str, text: str, lang: str) -> Path | None:
    key = speech_key(profile, text, lang)
    root = config.DATA_DIR / "jobs"
    for path in sorted(root.glob("*/speech.json")) if root.exists() else []:
        try:
            meta = json.loads(path.read_text())
            audio = path.with_name("speech.wav")
            if meta["key"] == key and digest(audio) == meta["sha256"]:
                return audio
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return None


def generate(profile: str, text: str, lang: str = "pt", job_id: str | None = None,
             *, mode: str = "dub", prompt: str = "Natural speaking, restrained gestures, static camera.",
             audio_approved: bool = False) -> Path:
    if lang not in {"pt", "en", "es"}:
        raise ValueError("Idioma não suportado. Use pt, en ou es.")
    chunks = split_text(text)
    if mode not in {"dub", "avatar", "motion"}:
        raise ValueError("Modo desconhecido.")
    pdir = config.profile_dir(profile)
    consent.require(pdir)
    voice, video = pdir / "voice.wav", pdir / "avatar.mp4"
    for path in (voice, video):
        if not path.exists():
            raise FileNotFoundError(f"Falta {path.name} no perfil {profile}")
    tts = get_tts(config.TTS_ENGINE)
    tts.validate_reference(voice, lang)
    if mode in {"dub", "motion"}:
        get_lipsync(config.LIPSYNC_ENGINE)
    if mode != "dub":
        resources.require("wan-animate" if mode == "motion" else config.VIDEO_ENGINE)
        get_video("wan-animate" if mode == "motion" else config.VIDEO_ENGINE)
        if not (pdir / "identity.png").exists():
            raise ValueError("Falta identity.png. Crie um novo perfil com imagem de identidade.")
    job_id = job_id or uuid.uuid4().hex[:12]
    jdir = config.job_dir(job_id)
    jdir.mkdir(parents=True, exist_ok=True)
    request = {"profile": profile, "text": text, "lang": lang, "mode": mode, "prompt": prompt}
    if audio_approved:
        if json.loads((jdir / "job.json").read_text()) != request:
            raise ValueError("O pedido mudou após gerar o áudio.")
    else:
        write_json(jdir / "job.json", request)
    audio = jdir / "speech.wav"
    key = speech_key(profile, text, lang)
    if audio_approved:
        approval = json.loads((jdir / "approval.json").read_text())
        if approval != {"key": key, "sha256": digest(audio)}:
            raise ValueError("A voz, o modelo ou a fala mudou após a aprovação. Crie um novo trabalho.")
    else:
        previous = _cached_speech(profile, text, lang)
        if previous:
            if previous != audio:
                shutil.copyfile(previous, audio)
        else:
            parts = tts.synthesize_batch(chunks, voice, jdir, lang)
            _concat_wavs(parts, audio)
        write_json(jdir / "speech_quality.json", audio_quality.inspect(audio, text, lang))
        key = speech_key(profile, text, lang)  # first synthesis may populate the upstream's weight cache
        write_json(jdir / "speech.json", {"key": key, "sha256": digest(audio)})
        return audio
    output = jdir / "rendering.mp4"
    if mode == "dub":
        get_lipsync(config.LIPSYNC_ENGINE).render(video, audio, output)
    else:
        _render_scenes(pdir, jdir, audio, output, mode, prompt)
    if config.TTS_ENGINE == "mock" or (mode == "dub" and config.LIPSYNC_ENGINE == "mock"):
        report = {"technical": "simulation", "visual_review": "not_applicable"}
    else:
        report = quality.inspect(output, audio)
    write_json(jdir / "quality.json", report)
    output.replace(jdir / "output.mp4")
    return jdir / "output.mp4"


def _render_scenes(pdir, jdir, audio, output, mode, prompt):
    engine_name = "wan-animate" if mode == "motion" else config.VIDEO_ENGINE
    engine = get_video(engine_name)
    folder = jdir / "scenes"
    identity = pdir / "identity.png"
    movement = jdir / "motion.mp4" if mode == "motion" else None
    if movement and media.duration(movement) + 0.05 < media.duration(audio):
        raise ValueError("O vídeo de movimento deve cobrir toda a fala; não será repetido.")
    if mode == "motion" and prompt.strip():
        # This upstream transfers the driving performance; arbitrary text is ignored by its model.
        write_json(jdir / "motion_direction.json", {"text_direction_supported": False,
                   "source": "driving_video", "note": "Movimentos vêm do vídeo separado, sem controle textual."})
    parts = media.split_audio(audio, folder, config.SCENE_SECONDS)
    videos, offset = [], 0.0
    for i, part in enumerate(parts):
        scene = folder / f"scene{i:04d}.mp4"
        stamp = scene.with_suffix(".ready.json")
        key = signature({"speech": digest(part), "identity": digest(identity),
                         "motion": digest(movement) if movement else None, "offset": offset,
                         "prompt": prompt, "mode": mode, "settings": settings()})
        try:
            reusable = json.loads(stamp.read_text()) == {"key": key, "sha256": digest(scene)}
        except (OSError, ValueError):
            reusable = False
        seconds = media.duration(part)
        if not reusable:
            raw = folder / f"raw{i:04d}.mp4"
            driving = None
            if movement:
                driving = folder / f"motion{i:04d}.mp4"
                media._run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(offset), "-i", str(movement),
                            "-t", str(seconds), "-an", "-r", "30", "-c:v", "libx264", "-crf", "0", str(driving)])
            engine.render(identity, driving, part, prompt, raw, config.SEED + i)
            trimmed = folder / f"trim{i:04d}.mp4"
            media._run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(raw), "-t", str(seconds),
                        "-an", "-r", "25", "-frames:v", str(math.ceil(seconds * 25)),
                        "-c:v", "libx264", "-crf", "0", str(trimmed)])
            if mode == "motion":
                get_lipsync(config.LIPSYNC_ENGINE).render(trimmed, part, scene, preserve_motion=True)
            else:
                media._run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(trimmed), "-i", str(part),
                            "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-shortest", str(scene)])
            quality.inspect(scene, part)
            write_json(stamp, {"key": key, "sha256": digest(scene)})
        videos.append(scene)
        offset += seconds
    media.concat_videos(videos, audio, output)


def approve(job_id: str):
    jdir = config.job_dir(job_id)
    request = json.loads((jdir / "job.json").read_text())
    meta = json.loads((jdir / "speech.json").read_text())
    key = speech_key(request["profile"], request["text"], request["lang"])
    if key != meta["key"] or digest(jdir / "speech.wav") != meta["sha256"]:
        raise ValueError("A referência ou a fala mudou. Gere e ouça o áudio novamente.")
    write_json(jdir / "approval.json", meta)
