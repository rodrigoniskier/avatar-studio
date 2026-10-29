# Arquitetura

## Projetos escolhidos (licenças conferidas nos repositórios em 29/10/2026)
| Função | Projeto | Licença do código | Papel | Observação |
|---|---|---|---|---|
| Voz clonada | [resemble-ai/chatterbox](https://github.com/resemble-ai/chatterbox) | MIT | **Principal** | Multilíngue V3 com `pt`; há finetune dedicado pt-BR; clona com ~10 s de áudio; marca d'água PerTh |
| Voz (alternativa) | [QwenLM/Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS) | Apache-2.0 | Reserva (adapter ainda não escrito) | Clone em 3 s, português suportado; modelos 0.6B/1.7B |
| Lip-sync (qualidade) | [bytedance/LatentSync](https://github.com/bytedance/LatentSync) | Apache-2.0 | **Principal** | v1.6 (512px) ≈ 18 GB VRAM; v1.5 ≈ 8 GB |
| Lip-sync (leve/rápido) | [TMElyralab/MuseTalk](https://github.com/TMElyralab/MuseTalk) | MIT | Alternativa | Roda em ~4 GB (fp16); mais lento nessa placa, qualidade menor |
| Transcrição (legendas/QA) | [SYSTRAN/faster-whisper](https://github.com/SYSTRAN/faster-whisper) | MIT | Futuro | Legendas automáticas e checagem da fala gerada |
| Roteiro | Gemini via Google AI Studio | — | Opcional | Chave gratuita (limites do plano gratuito da API) |

> Licença do **código** ≠ licença dos **pesos/dependências**. Verifique os model cards antes de qualquer uso comercial. Para uso pessoal/educacional não há impedimento conhecido.

## Descartados (e por quê)
- **F5-TTS**: código MIT, mas pesos pré-treinados CC-BY-NC (não comercial).
- **Coqui XTTS-v2**: licença CPML não comercial.
- **Fish Speech**: licença "Community License" própria (revisada em 13/10/2026) — exige leitura jurídica.
- **Wav2Lip / SadTalker**: qualidade inferior aos atuais e licenças restritivas.

## Fluxo
1. `POST /profiles/{nome}`: voz + vídeo base + consentimento → `data/profiles/{nome}/`
2. `POST /jobs`: texto dividido em frases (~300 caracteres) → TTS por trecho → concatenação (ffmpeg) → lip-sync → `output.mp4`
3. `GET /jobs/{id}`: polling; `GET /jobs/{id}/video`: download.

## Próximos passos (backlog)
1. Adapter Qwen3-TTS; 2. legendas com faster-whisper; 3. fila persistente para múltiplas execuções; 4. troca de fundo / b-roll; 5. fine-tune da voz pt-BR com mais áudio.
