# Validação — 0.2.2

Data: 02/11/2026. Base desta continuação: PR #1 em `5131db1`, com 94 testes. Tratamento dos pareceres em INDEPENDENT_REVIEW_FIXES.md.

## Verificações executadas

- 120 testes CPU: PyTorch 2.4.1+cpu, checkpoints pequenos reais Torch/safetensors, FFmpeg e fontes dos upstreams nos SHAs fixados. Inferência neural de integração substituída.
- Atenção comparada numericamente com softmax explícito: padding, comprimentos variáveis, causalidade inferior direita, janelas, escala, layout facial e rejeição de valores não finitos.
- Carga de shards meta, cobertura de pesos, shapes, adaptador e T5 ZIP/mmap/legado. Saídas do modelo pequeno comparadas com carga integral.
- MuseTalk com cenas de 1,5/3/4,8/7/12/15s. Pipeline motion 15+3s. Caudas InfiniteTalk de 0,15/3/3,24s recebem derivado com silêncio; PCM aprovado permanece intacto.
- Continuidade pelo último quadro real: extração da imagem final, manutenção da identidade original, retomada e invalidação encadeada quando a cena anterior muda. O modelo neural foi substituído nesse ensaio.
- Imagem por trabalho, upload inválido sem pasta órfã, fila/aprovação/retomada, alterações de pesos/referências/fontes, Host/Origin/token, queda do processo pai e trava herdada; CLI e fila disputam a mesma trava.
- Plano FP8 inclui vídeo/T5/mapas e revisão separada do encoder; falha antes de download se o conjunto estiver incompleto. Metadados oficiais consultados sem transferir checkpoints completos.
- Telemetria de execução/falha e memória cgroup. O relatório mede memória livre do sistema, não pico por processo ou qualidade visual.
- **1 teste adicional de interface em Chromium 134 real**: Uvicorn/worker reais, cadastro com FFmpeg, autenticação, aprovação de fala, download de vídeo/relatório e controles de cena. Inferência explicitamente mock; apenas a resposta de capacidades foi substituída ao verificar controles generativos, sem enviar pedido GPU.
- Resolução de dependências Python 3.10 com uv para InfiniteTalk, Wan-Animate e Qwen. Ambiente InfiniteTalk instalado com Torch/vision/audio CPU e dependências da integração; imports do entry script passaram sem pesos, com três consultas de metadados GPU substituídas no ensaio CPU. Isso **não** comprova imports/operações CUDA ou instalação integral em GPU.
- Wheel 0.2.2 gerado e conferido: inclui `studio/web/index.html`. Ruff F/E9, compilação Python, sintaxe JS/Bash e git diff --check.

## Limites

Não há GPU neste ambiente; a RAM do container é de aproximadamente 4 GiB, com cerca de 3 GiB disponíveis durante a conferência. Nenhum checkpoint neural completo foi carregado. Não foram medidos timbre, identidade, anatomia, sincronização perceptual ou desempenho em T4/P100.

Atenção, carga de checkpoints pequenos e processamento FFmpeg são reais em CPU; inferências TTS/lip-sync/vídeo continuam substituídas nos testes de integração. FP8 e condicionamento temporal ainda exigem ensaio neural em GPU. Não se executaram integralmente os instaladores CUDA; resolução de dependências e imports CPU são evidência mais limitada.

O ensaio Chromium verifica o funcionamento da interface, não aprova a qualidade do avatar. Os orçamentos conservadores de hardware não foram reduzidos por suposição após adicionar FP8/carregamento otimizado.

## Ensaio pendente

Usar hardware próprio ou sessão gratuita compatível, sem contratar recursos. Instalar apenas o motor desejado; executar `studio doctor --mode avatar|motion`. Começar com uma fala aprovada de 10–15 s e registrar `performance.json`. Comparar rosto, meio corpo e corpo inteiro; depois testar uma cauda curta e duas cenas com/sem continuidade. Comparar FP8 ao caminho completo antes de adotá-lo. Registrar GPU, RAM, parâmetros, duração, tempo, falhas e descartes. A pessoa retratada precisa revisar o resultado antes de publicação.
