"""Fila SQLite persistente, um consumidor GPU por diretório de dados (Linux/WSL)."""
import fcntl
import json
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager

from . import config, pipeline
from .artifacts import write_json
from .lease import worker_lease


@contextmanager
def database():
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.DATA_DIR / "queue.sqlite3", timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("""CREATE TABLE IF NOT EXISTS jobs (
        id TEXT PRIMARY KEY, request TEXT NOT NULL, settings TEXT NOT NULL,
        status TEXT NOT NULL, phase TEXT NOT NULL, error TEXT, created REAL NOT NULL)""")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def enqueue(request: dict, job_id: str | None = None) -> str:
    jid = job_id or uuid.uuid4().hex[:12]
    config.job_dir(jid).mkdir(parents=True, exist_ok=True)
    with database() as db:
        db.execute("INSERT INTO jobs VALUES (?,?,?,?,?,?,?)", (
            jid, json.dumps(request), json.dumps(pipeline.settings(), sort_keys=True),
            "queued", "audio", None, time.time()))
    return jid


def get(jid: str) -> dict:
    config.job_dir(jid)
    with database() as db:
        row = db.execute("SELECT * FROM jobs WHERE id=?", (jid,)).fetchone()
    if not row:
        raise FileNotFoundError("Trabalho não encontrado.")
    return dict(row)


def list_all():
    with database() as db:
        return [dict(r) for r in db.execute("SELECT * FROM jobs ORDER BY created DESC")]


def approve_audio(jid: str):
    row = get(jid)
    if row["status"] != "awaiting_audio":
        raise ValueError("O trabalho não está aguardando aprovação de áudio.")
    pipeline.approve(jid)
    with database() as db:
        db.execute("UPDATE jobs SET status='queued', phase='render' WHERE id=? AND status='awaiting_audio'", (jid,))


def retry(jid: str):
    row = get(jid)
    if json.loads(row["settings"]) != pipeline.settings():
        raise ValueError("A configuração mudou. Crie um novo trabalho; retomar não pode trocar os modelos aprovados.")
    with database() as db:
        changed = db.execute("UPDATE jobs SET status='queued', error=NULL WHERE id=? AND status='error'", (jid,))
        if not changed.rowcount:
            raise ValueError("Somente trabalhos com erro podem ser retomados.")


def review(jid: str, accepted: bool):
    row = get(jid)
    if row["status"] != "review":
        raise ValueError("O trabalho não está aguardando revisão visual.")
    path = config.job_dir(jid) / "quality.json"
    report = json.loads(path.read_text())
    report["visual_review"] = "approved" if accepted else "rejected"
    write_json(path, report)
    with database() as db:
        db.execute("UPDATE jobs SET status=? WHERE id=? AND status='review'", ("done" if accepted else "rejected", jid))


def drain_one() -> bool:
    """A trava de SO é liberada mesmo após morte do processo; retoma etapas interrompidas."""
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    with (config.DATA_DIR / ".worker.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return False
        with database() as db:
            db.execute("UPDATE jobs SET status='queued' WHERE status='running'")
            row = db.execute("SELECT * FROM jobs WHERE status='queued' ORDER BY created LIMIT 1").fetchone()
            if row is None:
                return False
            row = dict(row)
            db.execute("UPDATE jobs SET status='running', error=NULL WHERE id=?", (row["id"],))
        try:
            if json.loads(row["settings"]) != pipeline.settings():
                raise ValueError("A configuração mudou desde a criação. Crie um novo trabalho com os modelos atuais.")
            token = worker_lease.set(lock.fileno())
            try:
                pipeline.generate(**json.loads(row["request"]), job_id=row["id"], audio_approved=row["phase"] == "render")
            finally:
                worker_lease.reset(token)
            status = "awaiting_audio"
            if row["phase"] == "render":
                report = json.loads((config.job_dir(row["id"]) / "quality.json").read_text())
                status = "simulation" if report["technical"] == "simulation" else "review"
            with database() as db:
                db.execute("UPDATE jobs SET status=?, settings=? WHERE id=?",
                           (status, json.dumps(pipeline.settings(), sort_keys=True), row["id"]))
        except Exception as error:
            with database() as db:
                db.execute("UPDATE jobs SET status='error', error=? WHERE id=?", (str(error), row["id"]))
        return True


class Worker:
    def __init__(self):
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self.run, daemon=True, name="avatar-worker")

    def run(self):
        while not self.stop.is_set():
            if not drain_one():
                self.stop.wait(1)
