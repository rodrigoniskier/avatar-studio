# Guia passo a passo (para quem nunca fez isso)

Você só precisa de: um computador com internet, o celular e uma conta Google. **Nada é pago.**
Os nomes de botões do Kaggle podem mudar um pouco; se algo estiver diferente, me mande um print.

## PARTE 1: Gravar seu material (no celular, ~10 min)
**Vídeo (a parte mais importante: a qualidade final depende dele)**
O programa **não cria um vídeo novo**: ele pega um trecho do seu vídeo e refaz só a região da boca/queixo para falar o novo texto (como o "avatar instantâneo" de ferramentas comerciais). Por isso:
1. **Use um apoio fixo** (tripé, livro ou pilha de livros). Aperte gravar, **afaste-se e fique parado 3 a 5 segundos** antes de falar; o programa escolhe sozinho o trecho mais estável, mas precisa de pelo menos 5 s assim.
2. **Enquadre do peito para cima**, com o rosto **no centro**, inteiro e bem grande (de preferência ocupando metade da largura da imagem ou mais). Quanto mais pixels de rosto, melhor a boca e a barba.
3. Grave **na vertical ou horizontal em qualidade máxima (1080p)** e **não envie pelo WhatsApp**, que reduz muito a resolução. Passe o arquivo por cabo, Google Drive (arquivo original) ou e-mail.
4. Luz de frente (janela), fundo simples, boca visível, sem mão na frente do rosto, **cabeça quase parada**, boca fechada no começo e no fim.
5. Fale naturalmente por **30 a 120 segundos** (pode ler um texto).
6. Se você tem barba, ela costuma ficar **suavizada ou borrada** no resultado, porque o modelo refaz a região do queixo em 256 pixels. Rosto maior no vídeo reduz o problema, mas não o elimina.

**Áudio da voz**
1. Em lugar silencioso (sem ventilador, TV, eco), com o celular a um palmo da boca, grave um áudio de **20 a 30 segundos** lendo um texto com voz natural, como se explicasse algo a um aluno.
2. Pode usar o gravador do celular. Não precisa converter o formato: o programa converte sozinho.

Passe os dois arquivos para o computador (e-mail para você mesmo ou Google Drive).

## PARTE 2: Criar a conta no Kaggle (uma vez, ~5 min)
1. Acesse **kaggle.com** → *Register* → entre com sua conta Google.
2. Vá em seu perfil (foto no canto) → *Settings* → **Phone Verification** e confirme seu celular por SMS. Sem isso, o Kaggle não libera GPU nem internet.

## PARTE 3: Abrir o programa (cada vez que for usar)
1. No Kaggle: **Create** (ou "+") → **New Notebook**.
2. Menu **File → Import Notebook** (ou *Upload*), e envie o arquivo `notebooks/avatar_studio_kaggle.ipynb`.
   Baixe-o aqui: https://github.com/rodrigoniskier/avatar-studio/blob/main/notebooks/avatar_studio_kaggle.ipynb (botão de download).
   *Alternativa sem importar:* num notebook novo, cole na primeira célula o conteúdo de `scripts/kaggle_launch.py` e rode.
3. No painel da **direita**, abra **Session options** (ou *Settings*) e configure:
   - **Accelerator** → escolha **GPU T4** (ou P100);
   - **Internet** → **On**.
4. Clique em **Run All**. Na primeira vez demora 10 a 20 minutos (ele instala tudo sozinho). Pode deixar a aba aberta e fazer outra coisa.
5. No final da saída da célula aparece: `ABRA NO NAVEGADOR: https://alguma-coisa.trycloudflare.com`. Clique nesse link.

## PARTE 4: Criar seu avatar e gerar vídeos
1. Na página que abriu, em **Perfil**: escolha um nome simples (ex.: `rodrigo`, sem espaços ou acentos), envie o áudio e o vídeo, marque a caixa de consentimento e clique **Criar perfil**.
2. Em **Gerar vídeo**: digite o mesmo nome do perfil, escreva o texto (comece com 2 ou 3 frases para testar), escolha *Português* e clique **Gerar**.
3. Espere. Para frases curtas leva alguns minutos. Quando terminar, o vídeo aparece na página: clique nos 3 pontinhos do player → **Baixar**.
4. Se não gostou da voz ou da boca, me diga o que viu/ouviu e eu ajusto o programa.

## PARTE 5: Ao terminar
1. No Kaggle, pare a sessão (botão de desligar/"Stop Session"): isso preserva sua cota semanal de GPU.
2. Tudo o que estava na sessão some. Guarde seu áudio e vídeo originais no Google Drive para recriar o perfil na próxima vez (leva 1 minuto; a instalação, porém, repete: 10 a 20 min).

## Se der erro
Copie a mensagem de erro (ou tire print) e me envie. Os erros mais prováveis na primeira vez são a instalação do MuseTalk e o sotaque da voz; ambos são ajustáveis.
