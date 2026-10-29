"""Cole numa célula de um Notebook Kaggle (GPU ligada + Internet ligada) e execute.

Sobe o app e imprime uma URL pública temporária (Cloudflare Quick Tunnel, sem conta).
Primeira execução: ~10-20 min (instala ambientes e baixa modelos). Baixe o MP4 antes de encerrar.
"""
import os, re, subprocess, time

REPO = "https://github.com/rodrigoniskier/avatar-studio"
os.environ.update(STUDIO_TTS="chatterbox", STUDIO_LIPSYNC="musetalk",
                  STUDIO_DATA="/kaggle/working/data", STUDIO_DEVICE="cuda", STUDIO_HEAVY="/root/studio_heavy")

if not os.path.isdir("avatar-studio"):
    subprocess.run(f"git clone {REPO}", shell=True, check=True)
os.chdir("avatar-studio")
# o setup é idempotente: etapas já prontas são puladas (rápido), as faltantes são feitas
# grava o log completo e, se falhar, repete só o trecho final (onde está o motivo do erro)
r = subprocess.run("bash scripts/setup_upstreams.sh musetalk 2>&1 | tee /kaggle/working/setup.log; "
                   "exit ${PIPESTATUS[0]}", shell=True, executable="/bin/bash")
if r.returncode:
    tail = open("/kaggle/working/setup.log", errors="replace").read().splitlines()[-40:]
    raise SystemExit("\n\n===== A INSTALAÇÃO FALHOU. COPIE DAQUI PARA BAIXO E ENVIE =====\n"
                     + "\n".join(tail))
# libera caches do instalador (centenas de MB a vários GB) e mostra o espaço disponível
subprocess.run("rm -rf /root/.cache/uv /root/.cache/pip; df -h / /tmp /kaggle/working", shell=True)
subprocess.run("pip install -q -e .", shell=True, check=True)
if subprocess.run(["studio", "doctor"]).returncode:
    raise SystemExit("Corrija os itens [FALTA] acima (provavelmente GPU/Internet desligadas) e rode de novo.")
subprocess.run("curl -sL https://github.com/cloudflare/cloudflared/releases/latest/download/"
               "cloudflared-linux-amd64 -o /tmp/cloudflared && chmod +x /tmp/cloudflared",
               shell=True, check=True)

# encerra execuções anteriores (a célula antiga pode ter deixado o servidor ligado na porta 8000)
subprocess.run("pkill -f 'studio serve'; pkill -f cloudflared", shell=True)
time.sleep(2)
subprocess.Popen(["studio", "serve", "--host", "0.0.0.0", "--port", "8000"])
tun = subprocess.Popen(["/tmp/cloudflared", "tunnel", "--url", "http://localhost:8000"],
                       stderr=subprocess.PIPE, text=True)
for line in tun.stderr:
    m = re.search(r"https://[-a-z0-9]+\.trycloudflare\.com", line)
    if m:
        print("ABRA NO NAVEGADOR:", m.group(0), flush=True)
        break
time.sleep(10**6)  # mantém a sessão viva; pare o notebook quando terminar
