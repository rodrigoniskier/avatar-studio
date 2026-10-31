"""Planeja todo o download antes de transferir pesos; sem inferência remota."""
import argparse
import fcntl
import fnmatch
import json
import os
import shutil
from pathlib import Path

from huggingface_hub import HfApi, hf_hub_download, snapshot_download

ROOT = Path(os.getenv("STUDIO_MODELS", "models")).resolve()
QWEN = os.getenv("STUDIO_QWEN_MODEL", "Qwen/Qwen3-TTS-12Hz-1.7B-Base")
MODELS = {
    "qwen3": [(QWEN, "qwen3", None)],
    "infinitetalk": [
        ("Wan-AI/Wan2.1-I2V-14B-480P", "infinitetalk/Wan2.1-I2V-14B-480P", None),
        ("TencentGameMate/chinese-wav2vec2-base", "infinitetalk/chinese-wav2vec2-base", None),
        ("MeiGen-AI/InfiniteTalk", "infinitetalk/InfiniteTalk", ["single/*", "README.md", "LICENSE*"]),
    ],
    "wan-animate": [("Wan-AI/Wan2.2-Animate-14B", "wan-animate", None)],
}


def plan(engine):
    plans = []
    for repo, subdir, patterns in MODELS[engine]:
        dest = ROOT / subdir
        manifest = dest / "download.json"
        old = json.loads(manifest.read_text()) if manifest.exists() else {}
        if old.get("repo", repo) != repo:
            raise SystemExit("A pasta contém outro modelo. Use um novo STUDIO_MODELS para preservar a instalação anterior.")
        info = HfApi().model_info(repo, revision=old.get("revision"), files_metadata=True)
        excluded = ["process_checkpoint/FLUX.1-Kontext-dev/**"] if engine == "wan-animate" else None
        required = 0
        for file in info.siblings:
            name = file.rfilename
            if patterns and not any(fnmatch.fnmatch(name, p) for p in patterns):
                continue
            if excluded and any(fnmatch.fnmatch(name, p) for p in excluded):
                continue
            if file.size is None and name.endswith((".safetensors", ".pth", ".bin", ".onnx")):
                raise SystemExit("Tamanho dos pesos indisponível; não é seguro iniciar o download sem estimativa.")
            local = dest / name
            required += max(0, (file.size or 0) - (local.stat().st_size if local.exists() else 0))
        plans.append({"repo": repo, "dest": dest, "revision": info.sha, "patterns": patterns,
                      "excluded": excluded, "old": old, "required": required})
    return plans


def download(engine):
    plans = plan(engine)
    required = sum(item["required"] for item in plans)
    reserve = max(5 * 1024**3, int(required * .1))
    free = shutil.disk_usage(ROOT).free
    print(f"Plano completo: {required / 1e9:.1f} GB restantes + {reserve / 1e9:.1f} GB de reserva; livres {free / 1e9:.1f} GB")
    if required + reserve > free:
        raise SystemExit("Espaço insuficiente para o conjunto completo. Nenhum peso foi baixado; use armazenamento gratuito já disponível.")
    for item in plans:
        repo, dest, old = item["repo"], item["dest"], item["old"]
        snapshot_download(repo_id=repo, revision=item["revision"], local_dir=dest,
                          allow_patterns=item["patterns"], ignore_patterns=item["excluded"])
        if repo == "TencentGameMate/chinese-wav2vec2-base":
            patch_revision = old.get("audio_encoder_revision") or HfApi().model_info(repo, revision="refs/pr/1").sha
            hf_hub_download(repo, "model.safetensors", revision=patch_revision, local_dir=dest)
            old["audio_encoder_revision"] = patch_revision
        manifest = dest / "download.json"
        temp = manifest.with_suffix(".tmp")
        temp.write_text(json.dumps({**old, "repo": repo, "revision": item["revision"]}, indent=2))
        temp.replace(manifest)
        print(f"Pesos locais prontos: {dest} (revisão {item['revision']})")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("engine", choices=MODELS)
    args = parser.parse_args()
    if args.engine == "qwen3" and QWEN not in {"Qwen/Qwen3-TTS-12Hz-1.7B-Base", "Qwen/Qwen3-TTS-12Hz-0.6B-Base"}:
        raise SystemExit("Use um dos modelos Qwen3-TTS Base públicos 1.7B ou 0.6B.")
    ROOT.mkdir(parents=True, exist_ok=True)
    with (ROOT / ".download.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit("Outro download está em andamento. Aguarde; instalações pesadas são serializadas.")
        download(args.engine)


if __name__ == "__main__":
    main()
