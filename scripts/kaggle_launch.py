"""Cole numa célula de um Notebook Kaggle (GPU ligada + Internet ligada) e execute.

Sobe o app e imprime uma URL pública temporária (Cloudflare Quick Tunnel, sem conta).
Primeira execução: ~10-20 min (instala ambientes e baixa modelos). Baixe o MP4 antes de encerrar.
"""
import os, re, subprocess, time

REPO = "https://github.com/rodrigoniskier/avatar-studio"
os.environ.update(STUDIO_TTS="chatterbox", STUDIO_LIPSYNC="musetalk",
                  STUDIO_DATA="/kaggle/working/data", STUDIO_DEVICE="cuda")

if not os.path.isdir("avatar-studio"):
    subprocess.run(f"git clone {REPO}", shell=True, check=True)
os.chdir("avatar-studio")
if not os.path.exists(".venvs/musetalk/.ready"):
    subprocess.run("bash scripts/setup_upstreams.sh musetalk", shell=True, check=True)
subprocess.run("pip install -q -e .", shell=True, check=True)
if subprocess.run(["studio", "doctor"]).returncode:
    raise SystemExit("Corrija os itens [FALTA] acima (provavelmente GPU/Internet desligadas) e rode de novo.")
subprocess.run("curl -sL https://github.com/cloudflare/cloudflared/releases/latest/download/"
               "cloudflared-linux-amd64 -o /tmp/cloudflared && chmod +x /tmp/cloudflared",
               shell=True, check=True)

subprocess.Popen(["studio", "serve", "--host", "0.0.0.0", "--port", "8000"])
tun = subprocess.Popen(["/tmp/cloudflared", "tunnel", "--url", "http://localhost:8000"],
                       stderr=subprocess.PIPE, text=True)
for line in tun.stderr:
    m = re.search(r"https://[-a-z0-9]+\.trycloudflare\.com", line)
    if m:
        print("ABRA NO NAVEGADOR:", m.group(0), flush=True)
        break
time.sleep(10**6)  # mantém a sessão viva; pare o notebook quando terminar
