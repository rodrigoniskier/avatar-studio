"""O processo de inferência mantém a trava mesmo se o servidor for encerrado."""
import fcntl
from contextlib import contextmanager
from contextvars import ContextVar

worker_lease = ContextVar("worker_lease", default=None)


@contextmanager
def inference_lease():
    """CLI e fila disputam a mesma trava, herdada pelos subprocessos."""
    from . import config
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    with (config.DATA_DIR / ".worker.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError("Outro trabalho está usando a inferência. Aguarde sua conclusão.") from None
        token = worker_lease.set(lock.fileno())
        try:
            yield
        finally:
            worker_lease.reset(token)
