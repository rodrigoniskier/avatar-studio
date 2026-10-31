#!/usr/bin/env bash
# Instala motores locais gratuitos. Não aluga GPU nem exige assinatura ou crédito de API.
set -euo pipefail
cd "$(dirname "$0")/.."
ENGINE="${1:-qwen3}"
case "$ENGINE" in
  qwen3) UPSTREAM=Qwen3-TTS ;;
  infinitetalk) UPSTREAM=InfiniteTalk ;;
  wan-animate) UPSTREAM=Wan2.2 ;;
  qa) UPSTREAM=faster-whisper ;;
  *) echo "Uso: $0 qwen3|infinitetalk|wan-animate|qa" >&2; exit 2 ;;
esac
command -v uv >/dev/null || python -m pip install uv
export UV_LINK_MODE=copy
VENV_ROOT="${STUDIO_VENVS:-.venvs}"
UPSTREAM_ROOT="${STUDIO_UPSTREAMS:-upstreams}"
# gitlinks are intentionally pinned. No submodule update --remote.
git submodule update --init "upstreams/$UPSTREAM"
if [ "$UPSTREAM_ROOT" != upstreams ]; then
  echo "Este instalador usa upstreams/. Ajuste STUDIO_UPSTREAMS para esse diretório." >&2; exit 2
fi
uv venv --python 3.10 --allow-existing "$VENV_ROOT/$ENGINE"
PY="$VENV_ROOT/$ENGINE/bin/python"
if [ "$ENGINE" = qa ]; then
  uv pip install --python "$PY" -e "upstreams/$UPSTREAM"
  touch "$VENV_ROOT/$ENGINE/.ready"
  echo "Transcrição local pronta. Ative STUDIO_TRANSCRIBE=1 para conferir as falas."
  exit 0
elif [ "$ENGINE" = qwen3 ]; then
  uv pip install --python "$PY" -e "upstreams/$UPSTREAM" "huggingface_hub>=0.30,<1"
else
  uv pip install --python "$PY" torch==2.4.1 torchvision==0.19.1 torchaudio==2.4.1 --index-url https://download.pytorch.org/whl/cu121
  # The upstream supports SDPA fallback. FlashAttention remains optional, avoiding a T4-incompatible build.
  "$PY" -c 'from pathlib import Path; import sys; p=Path(sys.argv[1]); Path(sys.argv[2]).write_text("\n".join(s for s in p.read_text().splitlines() if not s.strip().startswith(("flash_attn", "torch", "torchaudio", "torchvision"))))' \
    "upstreams/$UPSTREAM/requirements.txt" "$VENV_ROOT/$ENGINE/requirements.filtered.txt"
  uv pip install --python "$PY" -r "$VENV_ROOT/$ENGINE/requirements.filtered.txt" "huggingface_hub>=0.30,<1"
  if [ "$ENGINE" = infinitetalk ]; then
    uv pip install --python "$PY" xformers==0.0.28 misaki\[en\] einops soundfile
  else
    uv pip install --python "$PY" -r upstreams/Wan2.2/requirements_animate.txt
  fi
fi
"$PY" scripts/download_generative_weights.py "$ENGINE"
touch "$VENV_ROOT/$ENGINE/.ready"
echo "Instalação concluída. Execute studio doctor e um teste curto; inferência GPU ainda precisa de validação."
