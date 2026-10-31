"""Baixa pesos públicos em uma revisão resolvida e registra a procedência. Não faz inferência remota."""
import argparse
import json
import os
import fnmatch
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("engine", choices=MODELS)
    args = parser.parse_args()
    if args.engine == "qwen3" and QWEN not in {"Qwen/Qwen3-TTS-12Hz-1.7B-Base", "Qwen/Qwen3-TTS-12Hz-0.6B-Base"}:
        raise SystemExit("Use um dos modelos Qwen3-TTS Base públicos 1.7B ou 0.6B.")
    for repo, subdir, patterns in MODELS[args.engine]:
        dest = ROOT / subdir
        manifest = dest / "download.json"
        old = json.loads(manifest.read_text()) if manifest.exists() else {}
        info = HfApi().model_info(repo, revision=old.get("revision"), files_metadata=True)
        revision = info.sha
        # FLUX is neither required nor downloaded by our animation route.
        excluded = ["process_checkpoint/FLUX.1-Kontext-dev/**"] if args.engine == "wan-animate" else None
        dest.mkdir(parents=True, exist_ok=True)
        required = 0
        for file in info.siblings:
            name = file.rfilename
            if patterns and not any(fnmatch.fnmatch(name, p) for p in patterns):
                continue
            if excluded and any(fnmatch.fnmatch(name, p) for p in excluded):
                continue
            local = dest / name
            required += max(0, (file.size or 0) - (local.stat().st_size if local.exists() else 0))
        free = shutil.disk_usage(dest).free
        print(f"Download estimado restante: {required / 1e9:.1f} GB; disco livre: {free / 1e9:.1f} GB")
        if required > free * 0.95:
            raise SystemExit("Espaço insuficiente. Use armazenamento gratuito já disponível; nenhum recurso será contratado.")
        snapshot_download(repo_id=repo, revision=revision, local_dir=dest,
                          allow_patterns=patterns, ignore_patterns=excluded)
        if repo == "TencentGameMate/chinese-wav2vec2-base":
            patch_revision = old.get("audio_encoder_revision") or HfApi().model_info(repo, revision="refs/pr/1").sha
            hf_hub_download(repo, "model.safetensors", revision=patch_revision, local_dir=dest)
            old["audio_encoder_revision"] = patch_revision
        manifest.write_text(json.dumps({**old, "repo": repo, "revision": revision}, indent=2))
        print(f"Pesos locais prontos: {dest} (revisão {revision})")


if __name__ == "__main__":
    main()
