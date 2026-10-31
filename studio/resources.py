"""Pré-checagem conservadora de recursos. Não é benchmark nem garantia de cabimento."""
import json
import os
import shutil
import subprocess
from pathlib import Path

# Orçamentos de segurança para os checkpoints completos integrados, sem quantização.
BUDGETS = {"infinitetalk": {"ram_gb": 48, "vram_gb": 12},
           "wan-animate": {"ram_gb": 64, "vram_gb": 24}}


def snapshot():
    ram = None
    try:
        fields = dict(line.split(":", 1) for line in Path("/proc/meminfo").read_text().splitlines())
        ram = int(fields["MemAvailable"].split()[0]) * 1024 / 1024**3
    except (OSError, KeyError, ValueError):
        pass
    gpu = []
    visible = os.getenv("CUDA_VISIBLE_DEVICES")
    if shutil.which("nvidia-smi") and visible not in {"", "-1"}:
        command = ["nvidia-smi", "--query-gpu=name,memory.free", "--format=csv,noheader,nounits"]
        if visible:
            command += ["--id=" + visible.split(",")[0].strip()]
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=10)
        except (OSError, subprocess.TimeoutExpired):
            result = None
        if result is not None and result.returncode == 0:
            for line in result.stdout.splitlines():
                try:
                    name, memory = line.split(",")
                    gpu.append({"name": name.strip(), "free_gb": float(memory)/1024})
                except ValueError:
                    continue
    return {"available_ram_gb": ram, "gpus": gpu}


def check(engine: str, hardware=None):
    hardware = hardware or snapshot()
    budget = BUDGETS[engine]
    reasons = []
    ram = hardware["available_ram_gb"]
    if ram is None or ram < budget["ram_gb"]:
        reasons.append(f"Orçamento conservador: {budget['ram_gb']} GiB de RAM disponível para {engine}.")
    # The upstream uses device 0. Do not sum several cards or assume free memory on another GPU.
    gpus = hardware["gpus"]
    if not gpus or gpus[0]["free_gb"] < budget["vram_gb"]:
        reasons.append(f"Requer GPU 0 com pelo menos {budget['vram_gb']} GiB livres neste caminho experimental.")
    return {"ok": not reasons, "reasons": reasons, "budget": budget, "hardware": hardware,
            "note": "Pré-checagem conservadora, sem garantia de desempenho/qualidade. Nenhum recurso será contratado."}


def require(engine: str):
    report = check(engine)
    if not report["ok"]:
        raise ValueError("Recursos insuficientes para geração local: " + " ".join(report["reasons"]) +
                         " Use hardware próprio compatível ou aguarde uma sessão gratuita adequada. Não há fallback pago.")
    return report


if __name__ == "__main__":
    import sys
    report = check(sys.argv[1])
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["ok"] else 1)
