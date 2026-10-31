# Validação após revisões independentes — 0.2.1

Data: 31/10/2026. Revisão anterior: PR #1 em `71eb4238115099faf66d6dff45f55ceec4b340d9`, com 40 testes. Alterações corretivas descritas em INDEPENDENT_REVIEW_FIXES.md.

## Verificações executadas

- 93 testes CPU com pytest, incluindo cálculos reais PyTorch 2.4.1+cpu, arquivos reais FFmpeg e código dos upstreams nos SHAs fixados.
- Comparação de atenção com softmax explícito independente: padding, comprimentos variáveis, causalidade inferior direita, janelas, escala, layout facial e rejeição de valores não finitos. As funções efetivas dos upstreams são extraídas dos overlays e executadas sem FlashAttention.
- Regressão MuseTalk com cenas de 1,5/3/4,8/7/12/15s, preservando todos os frames; código real do adaptador e do script MuseTalk, com inferência neural substituída.
- Pipeline motion com cenas 15+3s, FFmpeg real, política de cena inteira e montagem sem recompressão. Inferência neural substituída.
- Fila, aprovação, retomada, alteração de referência/pesos/fontes, Host/Origin, token malformado, pré-checagem de recursos e plano de download integral antes de transferir pesos.
- Queda real do processo pai, com subprocesso de inferência mantendo a trava até terminar; sem GPU, usando processo de teste.
- Ruff F/E9, compilação Python, sintaxe JavaScript/Node, Bash e git diff --check. O CI instala Torch CPU e inicializa os submódulos necessários para repetir os contratos.

## Limites

Nenhum checkpoint neural foi carregado nem executado em GPU. Os cálculos de atenção são reais em CPU; as inferências TTS/lip-sync/vídeo continuam substituídas nos testes de integração. Não há medição de semelhança vocal/facial, mãos/corpo, sincronização perceptual ou desempenho em T4/P100.

Não se executaram integralmente os instaladores pesados. O microensaio CUDA adicionado ao instalador/doctor é um diagnóstico para o ambiente do usuário, ainda não executado neste ambiente CPU. Não comprova inferência 14B. Pesos não foram baixados nesta correção.

O primeiro parecer independente executou o fluxo da interface em Chromium na revisão anterior. As alterações atuais tiveram sintaxe JavaScript e rotas verificadas, sem nova aprovação visual no navegador neste ambiente.

## Ensaio pendente

Usar apenas hardware próprio ou sessão gratuita compatível, sem contratar recursos. Conferir RAM/VRAM/disco; executar `studio doctor --mode avatar|motion` e o microensaio antes de uma cena curta. Só depois comparar voz pt-BR, rosto, meio corpo e corpo inteiro. Registrar hardware, parâmetros, duração, tempo e descartes. O resultado exige revisão da pessoa retratada antes de publicação.
