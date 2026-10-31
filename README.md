# Avatar Studio

Estúdio pessoal de voz e vídeo sintéticos, com **inferência local e modelos gratuitos**. Não usa API comercial, assinatura, créditos promocionais nem aluguel automático de GPU.

O software é gratuito; execução depende do hardware já disponível ou das cotas e regras de um ambiente gratuito. Não existe garantia de GPU contínua, compatibilidade com toda placa, ausência de deformações ou qualidade equivalente a modelos comerciais.

## Modalidades

| Modo | Entrada visual | Resultado |
|---|---|---|
| `dub` | Seu vídeo original | Nova fala sincronizada na gravação; conserva movimentos/cenário e pode repetir o trecho |
| `avatar` | Uma imagem sua + direção de atuação | InfiniteTalk gera novos movimentos a partir da imagem e do áudio |
| `motion` | Sua imagem + outro vídeo de movimento | Wan-Animate transfere atuação; MuseTalk/LatentSync sincroniza a nova fala |

Cada perfil preserva os originais. A imagem e o vídeo de movimento são referências independentes; corpo inteiro exige uma imagem com corpo inteiro. Os motores de vídeo generativo são **experimentais até validação GPU com seus arquivos**.

## Fluxo

1. Cadastre voz, vídeo e imagem opcional, com autorização.
2. Selecione o trecho de referência (início e duração) e confira o áudio. Qwen3 exige a transcrição exata desse trecho.
3. Prepare a fala, ouça e aprove antes de renderizar.
4. A fila SQLite salva o progresso. Cenas concluídas são reutilizadas após interrupção quando entradas/configuração continuam iguais.
5. O arquivo passa por inspeção de áudio, duração e decodificação. Revise identidade, anatomia e sincronização antes de aprovar o vídeo.

## Instalação do aplicativo

Linux/WSL, Python 3.10+, FFmpeg e FFprobe:

```bash
pip install -e '.[dev]'
pytest -q
cp .env.example .env
# Edite .env; carregue as variáveis no mesmo terminal:
set -a
source .env
set +a
```

Instale os motores conforme [FREE_GENERATION.md](docs/FREE_GENERATION.md). Sem variável de ambiente, os motores padrão são **Chatterbox e MuseTalk reais**. Nomes inválidos causam erro; simulação só é ativada explicitamente.

```bash
bash scripts/setup_upstreams.sh musetalk
studio doctor
studio serve
```

Abra http://127.0.0.1:8000. Para acesso em rede, defina `STUDIO_ACCESS_TOKEN`; a interface pede essa chave. O launcher Kaggle gera uma chave por sessão.

## Motores opcionais

```bash
bash scripts/setup_generative.sh qwen3
bash scripts/setup_generative.sh infinitetalk
bash scripts/setup_generative.sh wan-animate
# Opcional: transcrição local para comparar a fala ao texto
bash scripts/setup_generative.sh qa
```

`STUDIO_TTS=qwen3`, `STUDIO_VIDEO=infinitetalk`, `STUDIO_TRANSCRIBE=1` ativam as opções correspondentes. As instalações são separadas: não é necessário baixar todos os modelos.

## CLI

```bash
studio profile eu --voice voz.wav --video original.mp4 --image retrato.png --voice-seconds 20 --i-consent
studio generate eu 'Olá! Esta é a minha nova fala.' --mode avatar
# Ouça speech.wav no caminho informado; então:
studio approve-audio ID_DO_TRABALHO
```

A CLI gera arquivos no diretório do trabalho. A interface usa a fila SQLite e disponibiliza aprovação visual. `studio worker --once` processa uma etapa da fila sem servidor.

## Verificação sem GPU

```bash
STUDIO_TTS=mock STUDIO_LIPSYNC=mock studio serve
```

A interface marca o resultado como **simulação**. Os testes exercitam API, autorização, fila, aprovações, cache e processamento real com FFmpeg, substituindo as inferências dos modelos. Isso não valida qualidade de clonagem ou capacidade GPU.

Leia [arquitetura](docs/ARCHITECTURE.md), [operação gratuita](docs/DEPLOYMENT.md), [guia](docs/GUIA_PASSO_A_PASSO.md) e [licenças de terceiros](THIRD_PARTY.md).
