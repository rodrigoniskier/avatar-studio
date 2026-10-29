"""Executar numa célula de notebook Kaggle/Colab com GPU: sobe o app e abre URL pública gratuita."""
import os, re, subprocess, time

os.environ.update(STUDIO_TTS="chatterbox", STUDIO_LIPSYNC="latentsync", STUDIO_DATA="/kaggle/working/data")
subprocess.run("git clone https://github.com/rodrigoniskier/avatar-studio && cd avatar-studio && "
               "bash scripts/setup_upstreams.sh && pip install -e .", shell=True, check=True)
subprocess.run("curl -sL https://github.com/cloudflare/cloudflared/releases/latest/download/"
               "cloudflared-linux-amd64 -o /usr/local/bin/cloudflared && chmod +x /usr/local/bin/cloudflared",
               shell=True, check=True)
subprocess.Popen(["studio", "serve", "--port", "8000"], cwd="avatar-studio")
tun = subprocess.Popen(["cloudflared", "tunnel", "--url", "http://localhost:8000"],
                       stderr=subprocess.PIPE, text=True)
for line in tun.stderr:
    m = re.search(r"https://[-a-z0-9]+\.trycloudflare\.com", line)
    if m:
        print("ABRA:", m.group(0)); break
time.sleep(10**6)  # mantém a sessão viva até você parar
