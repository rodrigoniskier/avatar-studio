#!/usr/bin/env bash
# Baixa os projetos upstream nos commits fixados e os pesos dos modelos (gratuitos, Hugging Face).
set -euo pipefail
cd "$(dirname "$0")/.."
git submodule update --init --depth 1 upstreams/chatterbox upstreams/LatentSync upstreams/MuseTalk
pip install -e upstreams/chatterbox
pip install -r upstreams/LatentSync/requirements.txt
pip install -U "huggingface_hub[cli]"
# LatentSync 1.6 (18 GB VRAM). Para GPUs menores, use STUDIO_LIPSYNC=musetalk (ver docs/ARCHITECTURE.md).
huggingface-cli download ByteDance/LatentSync-1.6 latentsync_unet.pt whisper/tiny.pt \
  --local-dir upstreams/LatentSync/checkpoints
echo "OK. Chatterbox baixa seus pesos no primeiro uso."
