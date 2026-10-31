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
# Read the same .env as the app without executing shell code from it.
mapfile -t STUDIO_INSTALL_VALUES < <(python -c 'from studio import config; print(config.VENVS); print(config.UPSTREAMS); print(config.MODELS); print(config.QWEN_MODEL)')
export STUDIO_VENVS="${STUDIO_INSTALL_VALUES[0]:?Instale o aplicativo primeiro: pip install -e .}"
export STUDIO_UPSTREAMS="${STUDIO_INSTALL_VALUES[1]}"
export STUDIO_MODELS="${STUDIO_INSTALL_VALUES[2]}"
export STUDIO_QWEN_MODEL="${STUDIO_INSTALL_VALUES[3]}"
if [ "$ENGINE" = infinitetalk ] || [ "$ENGINE" = wan-animate ]; then
  python -m studio.resources "$ENGINE"
fi
command -v uv >/dev/null || python -m pip install uv
export UV_LINK_MODE=copy
VENV_ROOT="${STUDIO_VENVS:-.venvs}"
UPSTREAM_ROOT="${STUDIO_UPSTREAMS:-upstreams}"
# gitlinks are intentionally pinned. No submodule update --remote.
git submodule update --init "upstreams/$UPSTREAM"
if [ "$UPSTREAM_ROOT" != "$PWD/upstreams" ]; then
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
  uv pip install --python "$PY" torch==2.6.0 torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/cu124
  uv pip install --python "$PY" -c requirements/qwen3.txt -e "upstreams/$UPSTREAM" huggingface_hub
else
  if [ "$ENGINE" = infinitetalk ]; then
    uv pip install --python "$PY" torch==2.4.1 torchvision==0.19.1 torchaudio==2.4.1 --index-url https://download.pytorch.org/whl/cu121
  else
    uv pip install --python "$PY" torch==2.6.0 torchvision==0.21.0 torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/cu124
  fi
  # _video_worker installs our complete SDPA overlay, including direct calls and face attention.
  "$PY" -c 'from pathlib import Path; import sys; p=Path(sys.argv[1]); Path(sys.argv[2]).write_text("\n".join(s for s in p.read_text().splitlines() if not s.strip().startswith(("flash_attn", "torch", "torchaudio", "torchvision"))))' \
    "upstreams/$UPSTREAM/requirements.txt" "$VENV_ROOT/$ENGINE/requirements.filtered.txt"
  uv pip install --python "$PY" -c "requirements/$ENGINE.txt" -r "$VENV_ROOT/$ENGINE/requirements.filtered.txt" huggingface_hub
  if [ "$ENGINE" = infinitetalk ]; then
    uv pip install --python "$PY" -c requirements/infinitetalk.txt xformers==0.0.28 misaki\[en\] einops soundfile
  else
    uv pip install --python "$PY" -c requirements/wan-animate.txt -r upstreams/Wan2.2/requirements_animate.txt
  fi
fi
if [ "$ENGINE" = infinitetalk ] || [ "$ENGINE" = wan-animate ]; then
  APP_WORKER="$PWD/studio/engines/_video_worker.py"
  (cd "upstreams/$UPSTREAM" && "$PY" "$APP_WORKER" "$ENGINE" --check-only)
fi
"$PY" scripts/download_generative_weights.py "$ENGINE"
touch "$VENV_ROOT/$ENGINE/.ready"
echo "Instalação concluída. Execute studio doctor e um teste curto; inferência GPU ainda precisa de validação."
