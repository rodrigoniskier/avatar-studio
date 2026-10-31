# Execução sem serviços pagos

Use Linux/WSL, Python 3.10+, FFmpeg e uma GPU já disponível ou uma sessão gratuita com recursos compatíveis. Assinaturas de assistentes não fornecem computação para os modelos. O aplicativo não contrata serviços, não usa APIs comerciais e não precisa de cartão ou chave de geração.

## Local

Instale conforme README/FREE_GENERATION.md. Carregue `.env` explicitamente no Bash (`set -a`, `source .env`, `set +a`) e execute `studio serve`. Acesso padrão: http://127.0.0.1:8000.

A fila usa SQLite e trava de arquivo Linux/WSL. Todos os processos precisam apontar para o mesmo `STUDIO_DATA`. O servidor inicia um consumidor; `studio worker` também pode consumir a fila sem servidor.

## Kaggle

O launcher existente continua usando Chatterbox/MuseTalk. Cole `scripts/kaggle_launch.py` em um notebook com GPU e internet habilitadas. Ele imprime uma URL temporária e uma chave de acesso; digite a chave em “Acesso à sessão”. Não compartilhe a chave nem os logs que a contêm.

As cotas, disponibilidade de GPU e regras do provedor podem mudar; confira as condições exibidas na sua conta. Não assumimos que os modelos generativos 14B caibam na GPU/disco/RAM da sessão. Instale-os separadamente apenas depois de conferir recursos, conforme FREE_GENERATION.md. Não existe fallback para aluguel de GPU.

O disco da sessão pode ser temporário. Baixe o resultado e preserve `STUDIO_DATA` inteiro antes de encerrar: perfis, originais, trabalhos e `queue.sqlite3`. A persistência SQLite não protege contra perda do disco. Não há upload automático para Drive nesta versão.

## Acesso em rede

Defina `STUDIO_ACCESS_TOKEN` com uma chave aleatória antes de `studio serve --host 0.0.0.0`. A interface guarda a chave apenas no sessionStorage. APIs e arquivos exigem Bearer token; a página inicial contém apenas a interface. Em túnel, use a URL HTTPS. Uploads têm limite configurável por arquivo (`STUDIO_MAX_UPLOAD_MB`, padrão 512).

## Verificação

`studio doctor --mode dub|avatar|motion` verifica componentes para o caminho escolhido. Uma execução em GPU com referência real continua necessária. A CI usa CPU, FFmpeg e inferências substituídas; não baixa pesos nem gasta cotas de GPU.
