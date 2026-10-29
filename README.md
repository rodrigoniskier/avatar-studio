# Avatar Studio

Estúdio pessoal, estilo HeyGen, para gerar vídeos do **seu próprio avatar com a sua própria voz** a partir de texto — montado só com projetos open source e sem custo adicional.

```
texto (ou tema → roteiro Gemini) → voz clonada (Chatterbox) → lip-sync no seu vídeo base (LatentSync / MuseTalk) → MP4
```

## Como funciona o "avatar"
Como no *Instant Avatar* do HeyGen: você grava **uma vez** um vídeo de 30–120 s olhando para a câmera (boa luz, boca visível, sem mão na frente do rosto) e um áudio limpo de 10–30 s. O app regrava a boca do vídeo para falar qualquer texto, na sua voz.

## Uso rápido (sem GPU, engines falsos para testar)
```bash
pip install -e ".[dev]" && pytest -q
studio serve            # http://127.0.0.1:8000
```

## Uso real (GPU)
Veja [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) — local com GPU NVIDIA ou **gratuito via Kaggle** (`scripts/kaggle_launch.py`).
```bash
git clone --recurse-submodules <este repo> && cd avatar-studio
bash scripts/setup_upstreams.sh musetalk   # ou: latentsync (>=18 GB VRAM)
cp .env.example .env   # STUDIO_TTS=chatterbox, STUDIO_LIPSYNC=musetalk
studio profile eu --voice minha_voz.wav --video meu_video.mp4 --i-consent
studio generate eu "Olá! Este é o meu avatar falando." --lang pt
```

> Primeira vez e sem experiência? Siga o [guia passo a passo](docs/GUIA_PASSO_A_PASSO.md).

## Estrutura
| Pasta | Conteúdo |
|---|---|
| `studio/` | App próprio: API FastAPI, CLI, pipeline, engines plugáveis, consentimento |
| `web/` | Interface web (arquivo único) |
| `upstreams/` | Projetos de terceiros como submódulos, em commits fixados |
| `scripts/` | Instalação dos upstreams e launcher Kaggle/Colab |
| `docs/` | Arquitetura, hospedagem, licenças |

## Uso responsável
Só crie perfis da **sua** voz/imagem (ou de quem autorizou por escrito). O app exige consentimento registrado por perfil; o Chatterbox já embute marca d'água de áudio (PerTh). Informe o público quando o conteúdo for sintético.
