"""The local backend: one SQLite file of artifacts, created on the first write.

A connection is opened per operation, so the store is safe to share between the worker threads of a runner and the
request threads of the API. Reads never create the file."""

import sqlite3
import threading
from collections.abc import Iterable
from contextlib import closing
from datetime import date
from pathlib import Path

from .base import GLOBAL, Artifact, Kind

FILE_NAME = "artifacts.db"

_SCHEMA = """CREATE TABLE IF NOT EXISTS artifacts (
    as_of TEXT NOT NULL, kind TEXT NOT NULL, key TEXT NOT NULL, body TEXT NOT NULL,
    PRIMARY KEY (as_of, kind, key)) WITHOUT ROWID"""


class SqliteArtifactStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._setup = threading.Lock()
        self._ready = False

    @property
    def location(self) -> str:
        return str(self.path)

    def __repr__(self) -> str:
        return f"SqliteArtifactStore({str(self.path)!r})"

    # ---- connections ---------------------------------------------------------------------
    def _reader(self) -> sqlite3.Connection | None:
        if not self.path.is_file():
            return None
        return sqlite3.connect(self.path, timeout=30)

    def _writer(self) -> sqlite3.Connection:
        if not self._ready or not self.path.is_file():
            with self._setup:  # switching to WAL and creating the table need the file to themselves
                self.path.parent.mkdir(parents=True, exist_ok=True)
                with closing(sqlite3.connect(self.path, timeout=30)) as conn:
                    conn.execute("PRAGMA journal_mode=WAL")
                    conn.execute(_SCHEMA)
                self._ready = True
        conn = sqlite3.connect(self.path, timeout=30)
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def _read(self, sql: str, args: tuple = ()) -> list[tuple]:
        conn = self._reader()
        if conn is None:
            return []
        with closing(conn):
            try:
                return conn.execute(sql, args).fetchall()
            except sqlite3.OperationalError as e:  # a file with no table yet holds nothing
                if "no such table" in str(e):
                    return []
                raise

    # ---- writing -------------------------------------------------------------------------
    def put(self, as_of: date, kind: Kind, key: str, body: str) -> None:
        self.put_many([Artifact(as_of, kind, key, body)])

    def put_many(self, items: Iterable[Artifact]) -> None:
        rows = [(a.as_of.isoformat(), str(a.kind), a.key, a.body) for a in items]
        if not rows:
            return
        with closing(self._writer()) as conn, conn:  # one transaction: all of the batch or none
            conn.executemany("INSERT OR REPLACE INTO artifacts (as_of, kind, key, body) VALUES (?, ?, ?, ?)", rows)

    def delete_prefix(self, as_of: date, kind: Kind, prefix: str = "") -> int:
        if not self.path.is_file():
            return 0
        with closing(self._writer()) as conn, conn:
            cur = conn.execute("DELETE FROM artifacts WHERE as_of = ? AND kind = ? AND substr(key, 1, ?) = ?",
                               (as_of.isoformat(), str(kind), len(prefix), prefix))
            return cur.rowcount

    # ---- reading -------------------------------------------------------------------------
    def get(self, as_of: date, kind: Kind, key: str) -> str | None:
        rows = self._read("SELECT body FROM artifacts WHERE as_of = ? AND kind = ? AND key = ?", (as_of.isoformat(), str(kind), key))
        return rows[0][0] if rows else None

    def get_many(self, as_of: date, kind: Kind, keys: Iterable[str]) -> dict[str, str]:
        out: dict[str, str] = {}
        wanted = list(dict.fromkeys(keys))
        for i in range(0, len(wanted), 500):
            chunk = wanted[i:i + 500]
            marks = ",".join("?" * len(chunk))
            for k, body in self._read(f"SELECT key, body FROM artifacts WHERE as_of = ? AND kind = ? AND key IN ({marks})",
                                      (as_of.isoformat(), str(kind), *chunk)):
                out[k] = body
        return out

    def keys(self, as_of: date, kind: Kind, prefix: str = "") -> list[str]:
        rows = self._read("SELECT key FROM artifacts WHERE as_of = ? AND kind = ? AND substr(key, 1, ?) = ? ORDER BY key",
                          (as_of.isoformat(), str(kind), len(prefix), prefix))
        return [r[0] for r in rows]

    def dates(self) -> list[date]:
        rows = self._read("SELECT DISTINCT as_of FROM artifacts WHERE as_of != ? ORDER BY as_of", (GLOBAL.isoformat(),))
        return [date.fromisoformat(r[0]) for r in rows]
