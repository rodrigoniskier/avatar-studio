"""O processo de inferência mantém a trava mesmo se o servidor for encerrado."""
from contextvars import ContextVar

worker_lease = ContextVar("worker_lease", default=None)
