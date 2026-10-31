# Arquitetura

FastAPI + interface HTML, CLI, subprocessos isolados e fila SQLite. Apenas inferência local gratuita. Roteiro manual ou Ollama local opcional.

## Etapas

1. Perfil transacional: originais preservados, voz recortada explicitamente, transcrição opcional e imagem de identidade. Consentimento registrado só após sucesso.
2. Trabalho com configurações/revisões registradas. O worker mantém uma trava de SO por diretório de dados, serializando uso de GPU entre processos Linux/WSL.
3. TTS: Chatterbox multilíngue ou Qwen3 Base. Hashes e metadados validam o cache; arquivos corrompidos não são reutilizados.
4. Inspeção do sinal de áudio; faster-whisper opcional compara o texto. Aprovação humana da fala é obrigatória antes da renderização.
5. Dublagem direta ou cenas geradas. InfiniteTalk recebe imagem+fala+prompt. Wan-Animate recebe imagem+movimento, seguido de sincronização labial. Cenas têm assinaturas e marcadores escritos após inspeção.
6. FFmpeg verifica faixas, duração e decodificação completa. Escrita final é atômica; arquivo parcial não vira resultado pronto.
7. Revisão visual humana aprova ou rejeita identidade/anatomia/sincronização. Simulações são identificadas e não recebem aprovação como inferência real.

## Persistência

`queue.sqlite3` guarda pedidos, fase, configurações, estado e erro. `jobs/<id>/` guarda áudio, aprovação, cenas, vídeo e relatórios. Ao obter a trava exclusiva, o consumidor recupera trabalhos que ficaram em execução após queda. Referências e configurações alteradas invalidam aprovações/caches apropriados.

Estados: queued → running → awaiting_audio → queued/render → running → review → done/rejected. Falhas ficam em error e podem ser retomadas. Motores mock terminam em simulation.

## Limites explícitos

- A inspeção automática técnica não mede identidade, anatomia ou qualidade perceptual de sincronização.
- Cada cena recebe uma imagem; perfis adicionais permitem outros enquadramentos, sem condicionamento multivista conjunto.
- Cenas podem ter cortes perceptíveis. Não há garantia de plano longo contínuo.
- A fila persiste apenas enquanto o diretório de dados existir. Não é armazenamento remoto gratuito automático.
- `studio doctor` verifica instalação, não certifica memória/compatibilidade/qualidade de inferência.
- Downloads/modelos ficam fora do Git; revisão de pesos é registrada pelo instalador. Consulte THIRD_PARTY.md.

## Correções das revisões independentes

Atenção usa overlay completo (chamadas diretas, faces e dtype), sem alterar os gitlinks. MuseTalk distingue dublagem com seleção de trecho de sincronização de cena inteira. No modo motion, toda a duração do vídeo condutor é validada antes da geração. Uma trava de arquivo é herdada pelo subprocesso de inferência: se o servidor morrer, um novo consumidor aguarda o processo antigo liberar a GPU.

A pré-checagem de recursos é conservadora, não prova de inferência. O doctor testa imports e um microkernel CUDA quando há ambiente compatível. Novos alertas de sinal, escuridão e congelamento ajudam a revisão humana; o escopo automático continua limitado. Veja INDEPENDENT_REVIEW_FIXES.md.
