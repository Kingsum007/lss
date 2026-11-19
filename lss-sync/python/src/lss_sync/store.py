"""SQLite encrypted outbox and process-lifetime sender exclusion."""
from __future__ import annotations

from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
import os

STATES = ("PENDING", "IN_FLIGHT", "ACKNOWLEDGED", "BLOCKED")


class Store:
    def __init__(self, path):
        self.path = Path(path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript('''
              CREATE TABLE IF NOT EXISTS config (name TEXT PRIMARY KEY, value TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS nonces (key_version TEXT NOT NULL, iv TEXT NOT NULL, PRIMARY KEY(key_version,iv));
              CREATE TABLE IF NOT EXISTS records (id TEXT PRIMARY KEY, schema INTEGER NOT NULL, key_version TEXT NOT NULL, iv TEXT NOT NULL, ciphertext BLOB NOT NULL, created_at TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS outbox (seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT NOT NULL UNIQUE REFERENCES records(id), state TEXT NOT NULL, retries INTEGER NOT NULL DEFAULT 0, due_time REAL NOT NULL DEFAULT 0, byte_length INTEGER NOT NULL, created_at TEXT NOT NULL, error TEXT, acknowledged_at TEXT);
              CREATE INDEX IF NOT EXISTS queue_state_seq ON outbox(state,seq);
              CREATE INDEX IF NOT EXISTS queue_state_due ON outbox(state,due_time);
            ''')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA synchronous=FULL")
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def get_config(self, name="vault"):
        with self.connect() as db:
            row = db.execute("SELECT value FROM config WHERE name=?", (name,)).fetchone()
            return json.loads(row[0]) if row else None

    def put_config(self, value):
        with self.connect() as db:
            db.execute("INSERT OR REPLACE INTO config VALUES (?,?)", (value["name"], json.dumps(value)))

    def create_vault(self, config):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("INSERT INTO config VALUES ('vault',?)", (json.dumps(config),))
            db.execute("INSERT INTO nonces VALUES (?,?)", (config["keyVersion"], config["checkIv"]))

    def save(self, record, byte_length):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("INSERT INTO nonces VALUES (?,?)", (record["keyVersion"], record["iv"]))
            db.execute("INSERT INTO records VALUES (?,?,?,?,?,?)", (record["id"], record["schema"], record["keyVersion"], record["iv"], record["ciphertext"], record["createdAt"]))
            db.execute("INSERT INTO outbox(id,state,byte_length,created_at) VALUES (?,'PENDING',?,?)", (record["id"], byte_length, record["createdAt"]))

    def get_record(self, operation_id):
        with self.connect() as db:
            row = db.execute("SELECT * FROM records WHERE id=?", (operation_id,)).fetchone()
            if not row:
                return None
            return {"id": row["id"], "schema": row["schema"], "keyVersion": row["key_version"], "iv": row["iv"], "ciphertext": row["ciphertext"], "createdAt": row["created_at"]}

    def next_due(self, after_seq, now_ms):
        with self.connect() as db:
            row = db.execute("SELECT * FROM outbox WHERE state='PENDING' AND seq>? AND due_time<=? ORDER BY seq LIMIT 1", (after_seq, now_ms)).fetchone()
            return dict(row) if row else None

    def earliest_due(self):
        with self.connect() as db:
            row = db.execute("SELECT MIN(due_time) FROM outbox WHERE state='PENDING'").fetchone()
            return row[0]

    def transition(self, ids, change):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            for operation_id in ids:
                row = db.execute("SELECT * FROM outbox WHERE id=?", (operation_id,)).fetchone()
                if row is None:
                    raise RuntimeError("Missing outbox identity")
                updated = change(dict(row))
                if updated["state"] not in STATES:
                    raise ValueError("Invalid queue state")
                db.execute("UPDATE outbox SET state=?,retries=?,due_time=?,error=?,acknowledged_at=? WHERE id=?", (updated["state"], updated["retries"], updated["due_time"], updated.get("error"), updated.get("acknowledged_at"), operation_id))

    def recover(self):
        with self.connect() as db:
            db.execute("UPDATE outbox SET state='PENDING' WHERE state='IN_FLIGHT'")

    def summary(self, limit=50):
        with self.connect() as db:
            counts = dict.fromkeys(STATES, 0)
            for row in db.execute("SELECT state,COUNT(*) AS n FROM outbox GROUP BY state"):
                counts[row["state"]] = row["n"]
            rows = [dict(r) for r in db.execute("SELECT * FROM outbox ORDER BY seq DESC LIMIT ?", (max(0, limit),))]
            return {"counts": counts, "records": rows}

    @contextmanager
    def sender_lock(self):
        """The OS releases this exclusion lock if a process crashes."""
        filename = str(self.path) + ".sync.lock"
        handle = open(filename, "a+b")
        acquired = False
        try:
            if os.name == "nt":
                import msvcrt
                handle.seek(0, 2)
                if handle.tell() == 0:
                    handle.write(b"\0"); handle.flush()
                handle.seek(0)
                try:
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                    acquired = True
                except OSError:
                    pass
            else:
                import fcntl
                try:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    acquired = True
                except BlockingIOError:
                    pass
            yield acquired
        finally:
            if acquired:
                if os.name == "nt":
                    import msvcrt
                    handle.seek(0); msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            handle.close()
