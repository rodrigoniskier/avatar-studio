# Produção totalmente gratuita

## Regra do projeto

Inferência local: nenhum adaptador faz chamadas de geração para OpenAI, Gemini, Kling, Seedance, OmniHuman, Runway ou outro serviço comercial. Não existe fallback pago. Downloads de pacotes/pesos públicos são necessários durante a instalação. Não alugue GPU para seguir este guia.

O roteiro pode ser escrito manualmente ou solicitado ao Ollama instalado localmente. `studio.script_gen.draft_script` usa exclusivamente `127.0.0.1:11434` e um modelo já disponível no Ollama; não usa chave de API.

## Escolha conforme os recursos disponíveis

| Caminho | Modelos | Considerações |
|---|---|---|
| Dublagem econômica | Chatterbox + MuseTalk 1.5 | Mantém a gravação; não gera outra atuação. Caminho inicial do launcher Kaggle |
| Voz alternativa | Qwen3-TTS 1.7B Base | Requer o texto exato do áudio de referência; comparar pt-BR por escuta |
| Nova atuação | InfiniteTalk + Wan2.1 I2V 14B | O adaptador usa offload (`num_persistent_param_in_dit=0`), 480p e cenas de 15s. Exige bastante RAM/disco; compatibilidade e velocidade em T4/P100 não foram medidas |
| Transferência de movimento | Wan2.2-Animate 14B + lip-sync | Mais pesado; requer pré-processadores de pose. Não assume que uma GPU gratuita de 16 GB seja suficiente |
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

Os ambientes ficam em `.venvs/` e os pesos em `models/`. O instalador resolve uma revisão dos pesos, salva `download.json` e reutiliza essa revisão em novas execuções. Para trocar deliberadamente a revisão, preserve o manifesto anterior e reinstale no diretório apropriado. Submódulos têm commits fixados; não use `git submodule update --remote` sem testar.

O instalador dispensa FlashAttention e usa o fallback disponível nos upstreams; isso não comprova suporte de todas as operações em GPUs antigas. Quantização e kernels alternativos não são ativados sem benchmark. Não aplicamos FusionX automaticamente: a documentação do InfiniteTalk alerta para pior preservação de identidade e mudanças de cor em vídeos longos.

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

O resultado técnico fica aguardando revisão visual. Confira rosto, barba/bigode, dentes, mãos, movimento, estabilidade e sincronização. Uma inspeção técnica aprovada não certifica anatomia ou identidade. Não aplicamos restauração facial ou upscaling agressivo automaticamente.

## Retomada e cache

A fila fica em `data/queue.sqlite3`; preserve todo `STUDIO_DATA`, incluindo perfis e trabalhos. Reiniciar o servidor retoma a etapa interrompida e cenas já concluídas. Se perder o disco temporário, a fila também será perdida.

O cache valida hashes do áudio de referência, transcrição, texto, idioma, parâmetros, implementação e revisões disponíveis. Áudio alterado/corrompido não é reutilizado. Se trocar pesos do Chatterbox manualmente, altere `STUDIO_TTS_REVISION`; os pesos carregados internamente por ele não são todos re-hasheados em cada trabalho.

Mudança de configuração durante um trabalho causa erro explícito: crie um novo trabalho com a configuração atual. Aprovação de áudio não autoriza outra voz ou outro texto.

## Transcrição opcional

```bash
bash scripts/setup_generative.sh qa
export STUDIO_TRANSCRIBE=1
```

A primeira transcrição baixa os pesos públicos do Whisper small. `speech_quality.json` registra saturação, volume e, quando ativada, transcrição e taxa de divergência de palavras. A taxa pode refletir erro do transcritor em termos médicos e teológicos; ouça a fala. Timbre é avaliado por comparação auditiva com a gravação original.

## O que foi verificado

Testes CPU: fluxo API/fila, autorização, aprovação de áudio, alteração de referências/modelos, retomada, preservação de resolução, decodificação/duração reais com FFmpeg e montagem de cenas. Inferência neural é substituída por dublês nos testes de integração.

Pendências de hardware: instalar os ambientes em GPU compatível, testar sua voz em português e comparar três cenas (rosto falando, meio corpo gesticulando, corpo inteiro em movimento). Registrar GPU, RAM, resolução, tempo, tentativas descartadas e resultado aprovado. Não houve benchmark GPU nem comprovação de equivalência a modelos comerciais.

## Fontes primárias

- [InfiniteTalk, revisão integrada](https://github.com/MeiGen-AI/InfiniteTalk/tree/50aa0a94184315407a991ae804d9b58d6d311ba8)
- [Wan2.2, revisão integrada](https://github.com/Wan-Video/Wan2.2/tree/1ea34ff48f87168174e12956e200b1d908b1c5ff)
- [Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS)
- [MuseTalk: limitações](https://github.com/TMElyralab/MuseTalk#limitations)
- [LatentSync: VRAM e orientação de inferência](https://github.com/bytedance/LatentSync)
