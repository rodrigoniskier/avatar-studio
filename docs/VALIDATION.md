# Validação da versão 0.2.0

Data: 31/10/2026. Base: main `ada89721463f7f974ea4f5c71905af2acce3d370`.

## Verificações executadas

- 40 testes CPU, com pytest: aprovação de áudio, fila persistente, trava contra consumidores concorrentes, retomada após falha, rejeição de referências alteradas, cache por conteúdo/revisão/parâmetros, simulação explícita e autenticação.
- Processamento real com FFmpeg: preservação de vídeo vertical de 1280 pixels de altura, inspeção de faixas/duração, decodificação completa e montagem/retomada de cenas.
- Contratos dos adaptadores: imagem+áudio no InfiniteTalk, identidade+movimento separado no Wan-Animate, Qwen local com transcrição, sem ativação de FLUX ou extensão paga de prompt.
- HTTP real com servidor Uvicorn e consumidor automático: autorização, upload, fala, aprovação e download. Inferência neural substituída pelos motores mock.
- Ruff para erros de sintaxe/nomes indefinidos; compilação Python, sintaxe JavaScript com Node, `bash -n` e `git diff --check`.

## Limites

Não foram instalados nem executados modelos neurais em GPU. Não há medição de semelhança vocal/facial, qualidade de mãos/corpo, sincronização perceptual ou desempenho em T4/P100. Os adaptadores têm testes de contrato, não validação de inferência real.

A verificação visual no navegador não foi concluída: Chromium não estava instalado e o download do binário falhou neste ambiente. A sintaxe do JavaScript e o fluxo HTTP foram verificados; não apresentamos isso como aprovação visual da interface.

## Primeiro ensaio GPU

Usar apenas hardware próprio ou uma sessão gratuita compatível, sem contratar computação. Instalar um caminho por vez, começando por 10–15s. Comparar voz original/gerada em português, depois rosto falando, meio corpo gesticulando e corpo inteiro em movimento. Registrar GPU, RAM, disco, resolução, duração, tempo e tentativas descartadas. O resultado só deve ser publicado após revisão da pessoa retratada.
