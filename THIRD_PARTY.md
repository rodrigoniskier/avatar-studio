# Terceiros e licenças

O aplicativo usa código MIT. Isso não altera as licenças dos modelos, pesos ou dependências. Não há cobrança de licença ou serviço de inferência imposta pelo aplicativo.

| Componente | Origem | Licença declarada pelo projeto principal |
|---|---|---|
| Chatterbox | resemble-ai/chatterbox | MIT; áudio inclui marca PerTh |
| Qwen3-TTS | QwenLM/Qwen3-TTS | Apache-2.0 |
| MuseTalk | TMElyralab/MuseTalk | MIT |
| LatentSync | bytedance/LatentSync | Apache-2.0 |
| InfiniteTalk | MeiGen-AI/InfiniteTalk | Apache-2.0 para os modelos conforme README |
| Wan2.2 / Wan-Animate | Wan-Video/Wan2.2 | Apache-2.0 no repositório principal |
| faster-whisper | SYSTRAN/faster-whisper | MIT |

Os submódulos têm commits fixados no Git. O instalador dos novos motores registra a revisão dos pesos em `download.json`. Consulte os respectivos model cards, avisos e licenças de dependências antes de distribuir código/pesos ou realizar uso comercial.

Wan-Animate utiliza pré-processadores e checkpoints de terceiros (detector YOLO, estimador de pose, SAM2 em dependências). Eles podem ter termos diferentes do modelo Wan. O instalador desta integração exclui o checkpoint FLUX.1-Kontext-dev e não ativa `--use_flux`. Não presumimos que todo checkpoint auxiliar herde Apache-2.0 nem que gratuidade equivalha a ausência de obrigações de licença.

Somente crie perfis da própria pessoa ou com autorização. Informe quando o conteúdo for sintético. A revisão visual e o consentimento registrado pelo aplicativo não substituem obrigações de licença ou autorização do titular.
