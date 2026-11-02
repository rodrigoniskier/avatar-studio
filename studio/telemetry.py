"""Medições reais da execução; não atribui notas de identidade ou anatomia."""
import threading
import time
from contextlib import contextmanager

from . import resources
from .artifacts import write_json


@contextmanager
def measure(path, metadata):
    started = time.perf_counter()
    stop = threading.Event()
    samples = []
    def sample():
        try:
            samples.append(resources.snapshot())
        except (OSError, ValueError):
            pass  # Monitoring must not cause an otherwise valid render to fail.
    def monitor():
        while not stop.wait(2):
            sample()
    sample()
    thread = threading.Thread(target=monitor, daemon=True, name="avatar-telemetry")
    thread.start()
    state, error = "completed", None
    try:
        yield
    except BaseException as exc:
        state, error = "failed", type(exc).__name__ + ": " + str(exc)[-1000:]
        raise
    finally:
        stop.set()
        thread.join(timeout=11)
        sample()
        ram = [s["available_ram_gb"] for s in samples if s.get("available_ram_gb") is not None]
        vram = [s["gpus"][0]["free_gb"] for s in samples if s.get("gpus")]
        write_json(path, {"state": state, "error": error, "elapsed_seconds": round(time.perf_counter()-started, 3),
                         "metadata": metadata, "hardware_start": samples[0] if samples else None,
                         "samples": len(samples), "min_available_ram_gib": min(ram) if ram else None,
                         "min_free_vram_gib": min(vram) if vram else None,
                         "scope": "System free memory sampled every 2s; not process peak or a quality benchmark."})
