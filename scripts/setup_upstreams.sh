#!/usr/bin/env bash
# Uso: scripts/setup_upstreams.sh [musetalk|latentsync]   (padrão: musetalk, cabe em 16 GB do Kaggle)
# Cada projeto ganha um venv próprio em .venvs/ porque exigem versões de PyTorch incompatíveis.
set -euo pipefail
cd "$(dirname "$0")/.."
LIPSYNC="${1:-musetalk}"
command -v uv >/dev/null || pip install -q uv
git submodule update --init --depth 1 upstreams/chatterbox "upstreams/$([ "$LIPSYNC" = musetalk ] && echo MuseTalk || echo LatentSync)"

# --- Voz: Chatterbox (Python 3.11, torch 2.6) ---
uv venv --python 3.11 .venvs/chatterbox
uv pip install --python .venvs/chatterbox/bin/python -e upstreams/chatterbox

# --- Lip-sync ---
if [ "$LIPSYNC" = musetalk ]; then
  # Python 3.10 + torch 2.0.1/cu118, conforme o README do MuseTalk
  uv venv --python 3.10 .venvs/musetalk
  PY=.venvs/musetalk/bin/python
  uv pip install --python $PY torch==2.0.1 torchvision==0.15.2 torchaudio==2.0.2 \
      --index-url https://download.pytorch.org/whl/cu118
  uv pip install --python $PY -r upstreams/MuseTalk/requirements.txt
  uv pip install --python $PY -U openmim
  (cd upstreams/MuseTalk && ../../$PY -m mim install mmengine && ../../$PY -m mim install "mmcv==2.0.1" \
     && ../../$PY -m mim install "mmdet==3.1.0" && ../../$PY -m mim install "mmpose==1.1.0")
  (cd upstreams/MuseTalk && PATH="$PWD/../../.venvs/musetalk/bin:$PATH" sh ./download_weights.sh)
else
  # LatentSync 1.6 precisa de ~18 GB de VRAM: NÃO cabe no Kaggle gratuito
  uv venv --python 3.10 .venvs/latentsync
  uv pip install --python .venvs/latentsync/bin/python -r upstreams/LatentSync/requirements.txt "huggingface_hub[cli]"
  .venvs/latentsync/bin/huggingface-cli download ByteDance/LatentSync-1.6 latentsync_unet.pt whisper/tiny.pt \
      --local-dir upstreams/LatentSync/checkpoints
fi
echo "OK ($LIPSYNC). Os pesos do Chatterbox são baixados no primeiro uso."
