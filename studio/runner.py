"""Executa engines em subprocesso mostrando o progresso e, se falhar, devolve o motivo real."""
import os
import subprocess
from collections import deque

# O Kaggle/Jupyter define MPLBACKEND com um módulo que não existe nos venvs isolados.
NOTABLE = ("quadro ignorado", "Quadros gravados", "Error", "error", "Traceback")
ENV = {"MPLBACKEND": "Agg", "PYTHONUNBUFFERED": "1"}


def run_logged(cmd, cwd=None, input_text=None, env=None):
    p = subprocess.Popen(cmd, cwd=cwd, env={**os.environ, **ENV, **(env or {})}, text=True,
                         stdin=subprocess.PIPE if input_text else None,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if input_text:
        p.stdin.write(input_text); p.stdin.close()
    tail = deque(maxlen=25)
    notes = deque(maxlen=15)  # linhas importantes (avisos do engine) mesmo que saiam do final do log
    for line in p.stdout:
        print(line, end="", flush=True)
        tail.append(line.rstrip())
        if any(k in line for k in NOTABLE):
            notes.append(line.rstrip()[:300])
    if p.wait():
        raise RuntimeError(f"{os.path.basename(str(cmd[0]))} falhou (código {p.returncode}):\n"
                           + "\n".join(tail))
    return list(notes)


def disk_report() -> str:
    """Espaço em disco dos locais usados (falha silenciosa por disco cheio é comum em notebooks)."""
    out = subprocess.run(["df", "-h", "/", "/tmp", os.getcwd()], capture_output=True, text=True)
    return out.stdout.strip()
