# Produção totalmente gratuita

## Regra do projeto

Inferência local: nenhum adaptador faz chamadas de geração para OpenAI, Gemini, Kling, Seedance, OmniHuman, Runway ou outro serviço comercial. Não existe fallback pago. Downloads de pacotes/pesos públicos são necessários durante a instalação. Não alugue GPU para seguir este guia.

O roteiro pode ser escrito manualmente ou solicitado ao Ollama instalado localmente. `studio.script_gen.draft_script` usa exclusivamente `127.0.0.1:11434` e um modelo já disponível no Ollama; não usa chave de API.

## Escolha conforme os recursos disponíveis

| Caminho | Modelos | Considerações |
|---|---|---|
| Dublagem econômica | Chatterbox + MuseTalk 1.5 | Mantém a gravação; não gera outra atuação. Caminho inicial do launcher Kaggle |
| Voz alternativa | Qwen3-TTS 1.7B Base | Requer o texto exato do áudio de referência; comparar pt-BR por escuta |
| Nova atuação | InfiniteTalk + Wan2.1 I2V 14B | O adaptador usa offload (`num_persistent_param_in_dit=0`), 480p e cenas de 15s. Pré-checagem: 48 GiB de RAM disponível e 12 GiB de VRAM livre; não representa mínimo universal nem benchmark |
| Transferência de movimento | Wan2.2-Animate 14B + lip-sync | Mais pesado; requer pré-processadores de pose. Pré-checagem: 64 GiB de RAM disponível e 24 GiB de VRAM livre; não representa mínimo universal nem benchmark |
| Transcrição | faster-whisper small em CPU/int8 | Opcional; compara palavras. Não mede semelhança vocal |

Gratuidade de licença não significa GPU gratuita garantida. Se a sessão não tiver recursos suficientes, encerre/reduza o trabalho e retome quando houver uma sessão gratuita compatível. O aplicativo não contratará computação. Duas GPUs de 16 GB não viram automaticamente uma GPU de 32 GB.

## Instalar apenas o necessário

```bash
# Aplicativo e motores originais
pip install -e '.[dev]'
bash scripts/setup_upstreams.sh musetalk

# Voz alternativa, opcional
bash scripts/setup_generative.sh qwen3
export STUDIO_TTS=qwen3

# Novas atuações
bash scripts/setup_generative.sh infinitetalk
export STUDIO_VIDEO=infinitetalk
export STUDIO_VIDEO_SIZE=480
export STUDIO_SCENE_SECONDS=15
studio doctor --mode avatar

# Movimentos de uma gravação separada
bash scripts/setup_generative.sh wan-animate
studio doctor --mode motion
```

Os instaladores usam versões centrais limitadas em `requirements/`; dependências transitivas e instaladores pesados ainda precisam de ensaio completo. Os ambientes ficam em `.venvs/` e os pesos em `models/`. O instalador planeja o conjunto completo e exige reserva de disco antes da primeira transferência; uma trava impede downloads pesados simultâneos. Ele resolve uma revisão dos pesos, salva `download.json` e reutiliza essa revisão em novas execuções. Para trocar deliberadamente a revisão, preserve o manifesto anterior e reinstale no diretório apropriado. Submódulos têm commits fixados; não use `git submodule update --remote` sem testar.

O runtime cria um overlay temporário das fontes fixadas. Ele substitui **as funções chamadas diretamente** de atenção por SDPA, incluindo o caminho facial e as chamadas xformers do InfiniteTalk. Preserva comprimentos válidos de Q/K e padding, máscaras causais/janelas e o layout BLHD. Em GPUs pré-Ampere, converte os caminhos bfloat16 para float16; suporte bf16 emulado não é confundido com suporte nativo. Blocos de queries limitam memória temporária (`STUDIO_ATTENTION_CHUNK=128`). Valores não finitos fora de linhas matematicamente vazias causam erro.

Os cálculos foram comparados numericamente em PyTorch CPU 2.4.1; isso não valida estabilidade dos modelos inteiros em GPU. Na instalação e no `doctor`, `--check-only` importa o upstream e executa um microensaio CUDA/SDPA antes de carregar pesos. Ainda não é um ensaio de inferência 14B. Não ativamos quantização automaticamente. O layout publicado deve corresponder a todos os arquivos exigidos pelo upstream, incluindo encoder de texto; somente escolher uma flag int8/fp8 não torna esse conjunto válido. O script usa os checkpoints completos e guarda recursos antes de baixar. Sessões gratuitas comuns com 16 GB de VRAM e pouca RAM podem ser bloqueadas. Não existe fallback pago. Não aplicamos FusionX automaticamente: a documentação do InfiniteTalk alerta para pior preservação de identidade e mudanças de cor em vídeos longos.

## Cadastrar sua identidade e voz

- Grave áudio limpo, com uma pessoa, sem música, saturação ou reverberação forte. Preserve a gravação completa.
- Na interface, selecione início/duração de uma passagem limpa de 5–30s. Após criar o perfil, ouça a referência extraída.
- Para Qwen3, transcreva **apenas essa passagem**, exatamente como foi falada. Uma transcrição do arquivo completo não serve se ele foi recortado.
- Escolha uma imagem nítida com o enquadramento final: rosto, meio corpo ou corpo inteiro. Sem imagem enviada, usa-se um quadro a 1s do vídeo; confira a escolha e use uma foto dedicada se necessário.
- Para outros ângulos/enquadramentos, crie perfis adicionais com as referências desejadas. Os motores desta versão recebem uma imagem por cena; não há condicionamento multivista conjunto.
- Perfis não são sobrescritos: um novo nome preserva arquivos e histórico. `originals/` conserva voz/vídeo/imagem recebidos; `avatar.mp4` é um derivado de até 120s com resolução preservada.

## Produzir

Na interface, escolha `avatar` para gerar atuação ou `motion` para transferir movimentos. Em `motion`, envie uma gravação diferente da referência de identidade, cobrindo toda a duração da fala. Ela não é repetida nem limitada a 120s. Wan-Animate faz a animação e o motor de lip-sync sincroniza a boca depois.

Em `avatar`, a imagem continua sendo uma forte condição visual. Descrever outro cenário não garante substituir o fundo ou acertar qualquer ação; para controlar melhor, use uma imagem de identidade já preparada no cenário desejado e revise a semelhança antes da animação. Não há um gerador de imagens embutido nesta versão.

Comece com 10–15s, câmera estática e gestos discretos. Aprove o áudio antes do vídeo. Só depois tente uma aula longa. A fala é dividida em cenas e remontada usando o áudio aprovado; pode haver mudanças perceptíveis entre cenas. Não há promessa de um plano contínuo de 5–10 minutos sem deriva.

Em `motion`, direção textual não é suportada pelo upstream integrado; a interface oculta esse campo e os movimentos vêm da gravação enviada. A duração do movimento é validada contra toda a fala antes da primeira cena. O segundo estágio MuseTalk recebe a cena inteira, inclusive caudas abaixo de 5 s, sem escolher trecho nem inverter movimentos. Até dois quadros adicionais podem repetir somente a última imagem para arredondamento audiovisual.

Os intermediários usam H.264 sem perdas adicionais de compressão e a montagem copia os fluxos compatíveis; conversão de taxa de quadros ainda pode duplicar/descartar quadros. Wan-Animate usa os **30 fps** do seu config específico fixado, com `frame_num=77`; o config compartilhado de 16 fps não é o config final desse modelo. InfiniteTalk usa `frame_num=81`; ambos obedecem a 4n+1. A saída entregue ao MuseTalk é reamostrada para 25 fps preservando a duração.

O resultado técnico fica aguardando revisão visual. Confira rosto, barba/bigode, dentes, mãos, movimento, estabilidade e sincronização. Uma inspeção técnica aprovada não certifica anatomia ou identidade. Silêncios longos, saturação, trechos pretos e congelamento geram alertas para revisão, não notas de qualidade perceptual. Não aplicamos restauração facial ou upscaling agressivo automaticamente.

## Retomada e cache

A fila fica em `data/queue.sqlite3`; preserve todo `STUDIO_DATA`, incluindo perfis e trabalhos. Reiniciar o servidor retoma a etapa interrompida e cenas já concluídas. Se perder o disco temporário, a fila também será perdida.

O cache valida hashes do áudio de referência, transcrição, texto, idioma, parâmetros, implementação, alterações nas fontes dos submódulos e revisões disponíveis. Os pesos locais são rastreados por caminho, tamanho, mtime e ctime, inclusive MuseTalk/LatentSync e cache Chatterbox; esse rastreamento invalida o cache, mas não é certificação criptográfica contra adulteração deliberada. Áudio alterado/corrompido não é reutilizado. A tag `STUDIO_TTS_REVISION` continua disponível como invalidação adicional. O manifesto Qwen precisa coincidir com `STUDIO_QWEN_MODEL`; trocar a variável sem instalar o modelo correspondente causa erro antes do cache.

Mudança de configuração durante um trabalho causa erro explícito: crie um novo trabalho com a configuração atual. Aprovação de áudio não autoriza outra voz ou outro texto.

## Transcrição opcional

```bash
bash scripts/setup_generative.sh qa
export STUDIO_TRANSCRIBE=1
```

A primeira transcrição baixa os pesos públicos do Whisper small. `speech_quality.json` registra saturação, volume e, quando ativada, transcrição e taxa de divergência de palavras. No Qwen, a transcrição da própria referência também é conferida quando essa opção está ativa. Divergência acima de 50% bloqueia a síntese para conferência manual; a taxa pode refletir erro do transcritor em termos médicos e teológicos; ouça a fala. Timbre é avaliado por comparação auditiva com a gravação original.

## O que foi verificado

Testes CPU: fluxo API/fila, autorização, aprovação de áudio, alteração de referências/modelos, retomada, preservação de resolução, decodificação/duração reais com FFmpeg e montagem de cenas. Inferência neural é substituída por dublês nos testes de integração.

Pendências de hardware: instalar os ambientes em GPU compatível, testar sua voz em português e comparar três cenas (rosto falando, meio corpo gesticulando, corpo inteiro em movimento). Registrar GPU, RAM, resolução, tempo, tentativas descartadas e resultado aprovado. Não houve benchmark GPU nem comprovação de equivalência a modelos comerciais.

## Fontes primárias

- [InfiniteTalk, revisão integrada](https://github.com/MeiGen-AI/InfiniteTalk/tree/50aa0a94184315407a991ae804d9b58d6d311ba8)
- [Wan2.2, revisão integrada](https://github.com/Wan-Video/Wan2.2/tree/1ea34ff48f87168174e12956e200b1d908b1c5ff)
- [Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS)
- [MuseTalk: limitações](https://github.com/TMElyralab/MuseTalk#limitations)
- [LatentSync: VRAM e orientação de inferência](https://github.com/bytedance/LatentSync)
