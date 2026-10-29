# Hospedagem e operação com custo zero adicional

## O que as assinaturas cobrem (e o que não)
Claude, ChatGPT, Gemini e Copilot para docentes dão **acesso a assistentes**, não **GPU para rodar modelos**. Serviços de API (Anthropic, OpenAI, Gemini API) são cobrados à parte das assinaturas de chat — exceto a camada gratuita do Google AI Studio. Portanto, os modelos de voz/vídeo precisam rodar em GPU gratuita ou na sua máquina. Use os planos pagos como **ferramentas de desenvolvimento** (Claude Code/Copilot para evoluir o código, Gemini/ChatGPT para roteiros colados no app).

## Opções de execução (da mais estável à mais limitada)
| Opção | Custo | Prós | Contras |
|---|---|---|---|
| **A. Sua máquina com GPU NVIDIA ≥ 8 GB** (MuseTalk/LatentSync 1.5) ou ≥ 18 GB (LatentSync 1.6) | R$ 0 | Sem limites, privado | Depende do hardware que você já tem |
| **B. Kaggle Notebook (GPU T4/P100)** | R$ 0 | Cota semanal de GPU (reportada ~30 h/semana, sujeita a mudança); aceita internet | Sessões limitadas (~9–12 h); 16 GB de VRAM → use MuseTalk ou LatentSync 1.5, não 1.6; precisa reiniciar a cada uso |
| **C. Google Colab gratuito** | R$ 0 | Fácil | GPU e limites não garantidos; desconecta por inatividade |
| **D. Hugging Face Spaces (CPU) / GitHub Pages** | R$ 0 | Bom para a interface estática | Sem GPU gratuita contínua; ZeroGPU é para demos curtas e depende de plano |

**Decisão: Kaggle (opção B)**, com MuseTalk 1.5 como lip-sync padrão (cabe nos 16 GB).

## Passo a passo no Kaggle
1. Conta em kaggle.com (GPU e Internet podem exigir verificação de telefone). Crie um Notebook novo.
2. Painel direito → *Session options*: **Accelerator = GPU (T4 ou P100)** e **Internet = On**.
3. Cole o conteúdo de `scripts/kaggle_launch.py` numa célula e execute (repositório precisa ser público, ou ajuste o clone com token).
4. Primeira vez: ~10–20 min instalando. Ao final aparece `ABRA NO NAVEGADOR: https://....trycloudflare.com`.
5. Na página: crie o perfil (voz WAV + vídeo base + consentimento), escreva o texto, gere e **baixe o MP4**.
6. Ao terminar, pare a sessão (economiza cota). O disco é temporário: guarde `voice.wav` e `avatar.mp4` no seu Drive.

## Por que venvs separados
Chatterbox exige PyTorch 2.6 / Python 3.11; MuseTalk exige PyTorch 2.0.1 / Python 3.10. O `scripts/setup_upstreams.sh` cria `.venvs/chatterbox` e `.venvs/musetalk` (via `uv`), e o app chama cada engine por subprocesso. TTS e lip-sync rodam em sequência, nunca ao mesmo tempo na GPU.

> **Não validado em GPU ainda:** a instalação do MuseTalk (mmcv/mmpose) e a qualidade do pt-BR do Chatterbox devem ser testadas na primeira sessão. Se algo falhar, anote o erro e corrigimos o script.

## Operação
- **Segredos:** `.env` nunca vai ao Git. `GEMINI_API_KEY` só se usar roteiro automático (chave gratuita do AI Studio; a cota gratuita pode usar seus dados para treino — não envie conteúdo sensível).
- **Backup:** guarde `data/profiles/` (voz+vídeo base) no seu Google Drive; recriar o perfil em cada sessão Kaggle leva segundos.
- **CI:** GitHub Actions (gratuito em repositório público; limites no privado) roda os testes com engines mock.
- **Atualizações:** os upstreams ficam em commits fixados; para atualizar, `git submodule update --remote` e rode um vídeo de teste.

## Riscos a validar antes de confiar
1. Qualidade do pt-BR do Chatterbox com a sua voz (teste com 3 textos).
2. LatentSync 1.6 exige ~18 GB: **não cabe** na GPU gratuita do Kaggle (16 GB); validar MuseTalk/1.5.
3. Limites e regras de GPU gratuita mudam; confira a política atual do Kaggle/Colab.
