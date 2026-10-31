# Correções após duas revisões independentes

Revisões recebidas em 31/10/2026. Alvo corrigido: PR #1, inicialmente no commit `71eb4238115099faf66d6dff45f55ceec4b340d9`. O segundo parecer inspecionou principalmente a base `ada8972`, conforme sua própria delimitação; os achados foram confrontados com o código efetivo do PR.

| Achado | Tratamento e evidência |
|---|---|
| C1 / atenção sem FlashAttention | Overlay substitui `flash_attention` e `attention` chamadas diretamente nos dois upstreams. Atenção facial corrigida em BLHD e xformers direcionado a SDPA no caminho single-GPU. Regressões numéricas CPU com comprimentos variáveis, padding, máscaras, janelas e escala |
| C2 / recorte e inversão de cenas | `preserve_motion=True` no segundo estágio. Usa cena inteira; não chama seletor. Sequências do upstream não são invertidas; arredondamento de até dois quadros clona só o último quadro. Testes com 1,5/3/4,8/7/12/15s e pipeline 15+3s |
| H1 / limites de hardware e BF16 emulado | Escolha de dtype pela capacidade nativa da GPU. Pré-checagem conservadora bloqueia RAM/VRAM insuficiente antes da síntese/download. **Benchmark e inferência GPU continuam pendentes** |
| M1 / duração do movimento validada tarde | Compara toda a fala e todo o movimento antes de dividir ou renderizar a primeira cena |
| M2 / modelo Qwen e pesos no cache | Valida manifesto contra modelo configurado. Registra pesos locais por tamanho/mtime/ctime e fontes modificadas dos submódulos; cache de referência/texto continua por hash |
| M3 / prompt ignorado no modo motion | Interface oculta direção por texto nesse modo; API normaliza para vazio, CLI informa a limitação. O vídeo condutor é a direção efetiva |
| M4 / resolução | Interface/documentação distinguem originais preservados de saída nativa do modelo. Não se promete 1080p por ter referência 1080p |
| M5 / continuidade e recompressão | Intermediários com CRF 0 e montagem sem recompressão de vídeo compatível. As cenas ainda podem ter cortes de pose/identidade; **não há garantia de continuidade longa** nem condicionamento multivista novo |
| M6 / origem, host e token malformado | Origin diferente é bloqueado. Sem token, Host deve ser localhost/loopback. Token comparado como bytes; caracteres não ASCII não causam HTTP 500 |
| M7 / transcrição da referência | Qwen exige transcrição e tokenizer local. Com QA de transcrição ativada, compara também referência e `voice.txt`; divergência alta exige conferência |
| L1 / escopo da inspeção | Rotulagem explícita de integridade/duração/sinal. Alertas de saturação, silêncio prolongado, preto e congelamento; anatomia/identidade continuam sem medição automática |
| L2 / doctor | Confere arquivos auxiliares, orçamento RAM/VRAM e imports/microensaio CUDA do runtime. Não certifica o modelo inteiro |
| L3 / instalações | Núcleo de dependências limitado por engine; fontes fixadas. Plano completo de download com reserva e trava. cloudflared fixado com SHA-256 oficial. **Instaladores pesados ainda não foram executados integralmente em GPU** |
| L4 / operação | Ruff completo de erros F/E9 no CI; Ollama cloud bloqueado; retry de configuração incompatível impedido e ocultado na interface |
| Questões da base antiga | Atomicidade de perfil, originais, path traversal, texto vazio, nome de saída Chatterbox e simulação explícita já estavam corrigidos no PR; regressões mantidas. `.env` agora também é lido automaticamente |
| Processo órfão após queda do servidor | Trava de inferência herdada pelo filho; teste mata o processo pai e comprova que o novo consumidor não pode ocupar a GPU até o filho finalizar |

## Delimitações importantes

O `sample_fps` específico de Wan-Animate no SHA fixado é **30**, substituindo o valor **16** do config compartilhado. A hipótese de 16 fps nesse modelo não foi incorporada como fato. O adaptador mantém 30 fps no condutor e converte a saída para 25 fps por reamostragem, não por reinterpretar timestamps.

Não se ativou uma flag de quantização sem um conjunto completo e compatível de pesos. O upstream InfiniteTalk espera também pesos/mapa de T5 do tipo selecionado. Não se promete que um checkpoint quantizado isolado resolva RAM/disco/VRAM. Nenhum recurso pago foi contratado ou incluído como fallback.

Os limites 48/64 GiB de RAM disponível e 12/24 GiB de VRAM livre são **orçamentos conservadores escolhidos para a integração completa atual**, não mínimos universais publicados pelos autores. Podem bloquear sessões gratuitas comuns. Passar nessa verificação não garante sucesso, qualidade, precisão numérica ou desempenho.

## Fontes conferidas

- InfiniteTalk `50aa0a94184315407a991ae804d9b58d6d311ba8`, fontes de atenção e inferência.
- Wan2.2 `1ea34ff48f87168174e12956e200b1d908b1c5ff`, atenção facial, dtype e config `wan_animate_14B.py`.
- MuseTalk `0a89dec45a0192b824e3cf4daf96c239440c5ed8`, sequência de frames de `scripts/inference.py`.
- Qwen3-TTS `022e286b98fbec7e1e916cb940cdf532cd9f488e`, carregamento local do tokenizer e APIs de clonagem.
- [Pesos quantizados publicados pelo InfiniteTalk](https://huggingface.co/MeiGen-AI/InfiniteTalk/tree/main/quant_models).
- [Release oficial cloudflared 2026.10.7](https://github.com/cloudflare/cloudflared/releases/tag/2026.10.7), SHA-256 do asset linux-amd64 registrado no launcher.
