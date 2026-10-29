#!/usr/bin/env bash
# Uso: scripts/setup_upstreams.sh [musetalk|latentsync]   (padrão: musetalk, cabe em 16 GB do Kaggle)
# Cada projeto ganha um venv próprio em .venvs/ porque exigem versões de PyTorch incompatíveis.
# Cada etapa grava um marcador .ready; reexecutar após uma falha retoma de onde parou.
set -euo pipefail
cd "$(dirname "$0")/.."
LIPSYNC="${1:-musetalk}"
ROOT="$PWD"
command -v uv >/dev/null || pip install -q uv
export UV_LINK_MODE=copy

# Notebooks como o Kaggle limitam a pasta de trabalho (20 GB). Com STUDIO_HEAVY definido, ambientes e
# modelos vão para outro disco e ficam acessíveis por link simbólico (venvs funcionam via o mesmo caminho).
offload() {  # $1 = caminho no repositório, $2 = nome no destino
  [ -n "${STUDIO_HEAVY:-}" ] || return 0
  local src="$1" dst="$STUDIO_HEAVY/$2"
  [ -L "$src" ] && return 0
  mkdir -p "$STUDIO_HEAVY" "$(dirname "$src")"
  if [ -e "$src" ]; then rm -rf "$dst"; echo "Movendo $src para $dst ..."; mv "$src" "$dst"; else mkdir -p "$dst"; fi
  ln -s "$dst" "$src"
}
offload .venvs venvs
UPDIR=$([ "$LIPSYNC" = musetalk ] && echo MuseTalk || echo LatentSync)
git submodule update --init --depth 1 upstreams/chatterbox "upstreams/$UPDIR"

[ "$LIPSYNC" = musetalk ] && offload upstreams/MuseTalk/models musetalk_models

# --- Voz: Chatterbox (Python 3.11, torch 2.6) ---
if [ ! -f .venvs/chatterbox/.ready ]; then
  rm -rf .venvs/chatterbox
  uv venv --python 3.11 .venvs/chatterbox
  uv pip install --python .venvs/chatterbox/bin/python -e upstreams/chatterbox
  touch .venvs/chatterbox/.ready
fi

# --- Lip-sync ---
if [ "$LIPSYNC" = musetalk ]; then
  if [ ! -f .venvs/musetalk/.ready ]; then
    rm -rf .venvs/musetalk
    # Python 3.10 + torch 2.0.1/cu118, conforme o README do MuseTalk
    uv venv --python 3.10 .venvs/musetalk
    PY="$ROOT/.venvs/musetalk/bin/python"
    uv pip install --python "$PY" torch==2.0.1 torchvision==0.15.2 torchaudio==2.0.2 \
        --index-url https://download.pytorch.org/whl/cu118
    uv pip install --python "$PY" -r upstreams/MuseTalk/requirements.txt
    # setuptools>=81 removeu pkg_resources, exigido pelo mim e por builds antigos (chumpy)
    uv pip install --python "$PY" "setuptools<81" wheel pip openmim tomli
    uv pip install --python "$PY" --no-build-isolation chumpy
    export PATH="$ROOT/.venvs/musetalk/bin:$PATH"
    "$PY" -m mim install mmengine
    "$PY" -m mim install "mmcv==2.0.1"
    "$PY" -m mim install "mmdet==3.1.0"
    "$PY" -m mim install "mmpose==1.1.0"
    # o openmim/mmlab atualizam o numpy; MuseTalk exige exatamente 1.23.5
    uv pip install --python "$PY" numpy==1.23.5
    "$PY" -c "import mmengine, mmcv, mmcv.ops, mmdet, mmpose, torch, numpy; print('imports OK', torch.__version__, numpy.__version__)"
    touch .venvs/musetalk/.ready
  fi
  PY="$ROOT/.venvs/musetalk/bin/python"
  # huggingface_hub 0.30.2 é o que o transformers 4.39 aceita (o script oficial o atualizava e quebrava tudo)
  uv pip install --python "$PY" "huggingface_hub==0.30.2" gdown
  "$PY" scripts/download_musetalk_weights.py upstreams/MuseTalk/models
else
  # LatentSync 1.6 precisa de ~18 GB de VRAM: NÃO cabe no Kaggle gratuito
  if [ ! -f .venvs/latentsync/.ready ]; then
    rm -rf .venvs/latentsync
    uv venv --python 3.10 .venvs/latentsync
    uv pip install --python .venvs/latentsync/bin/python -r upstreams/LatentSync/requirements.txt "huggingface_hub"
    touch .venvs/latentsync/.ready
  fi
  .venvs/latentsync/bin/python -c "
from huggingface_hub import hf_hub_download as d
for f in ('latentsync_unet.pt', 'whisper/tiny.pt'):
    d('ByteDance/LatentSync-1.6', f, local_dir='upstreams/LatentSync/checkpoints')"
fi
echo "OK ($LIPSYNC). Os pesos do Chatterbox são baixados no primeiro uso."
