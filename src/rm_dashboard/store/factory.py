"""Choosing the backend: ``sqlite:<path>`` (a file, or a folder holding ``artifacts.db``) or ``firestore:<project>[/<database>]``."""

import re
from pathlib import Path

from .base import ArtifactStore
from .sqlite import FILE_NAME, SqliteArtifactStore

BACKENDS = ("sqlite", "firestore")
DEFAULT_SPEC = f"sqlite:reports/{FILE_NAME}"


def sqlite_path(location: str | Path) -> Path:
    """A ``.db``/``.sqlite`` path is the file; anything else is a folder holding ``artifacts.db`` (the old ``--reports-dir``)."""
    p = Path(location)
    return p if p.suffix in (".db", ".sqlite", ".sqlite3") else p / FILE_NAME


def open_store(spec: str | Path | None = None, *, writable: bool = False) -> ArtifactStore:
    """The artifact store named by ``spec``. A bare path is the SQLite folder form. SQLite stores always accept writes; a Firestore
    store does only with ``writable`` (runners, the loader), so the API cannot change artifacts. Raises ValueError for an unknown backend."""
    if spec is None or str(spec) == "":
        spec = DEFAULT_SPEC
    text = str(spec)
    m = re.match(r"^([A-Za-z][A-Za-z0-9+.-]*):(.*)$", text)
    if m is None:
        return SqliteArtifactStore(sqlite_path(text))  # a plain folder or file path
    backend, rest = m.groups()
    if backend == "sqlite":
        if not rest:
            raise ValueError("sqlite artifact store needs a path: sqlite:<path>")
        return SqliteArtifactStore(sqlite_path(rest))
    if backend == "firestore":
        from .firestore import open_firestore_store  # lazy: the Firestore client library is optional

        return open_firestore_store(rest, writable=writable)
    raise ValueError(f"unknown artifact backend {backend!r}; valid backends: {', '.join(BACKENDS)}")


def as_store(target: "ArtifactStore | str | Path") -> ArtifactStore:
    """An artifact store as given, or the SQLite store a folder or ``.db`` path names (the old ``reports_dir`` argument)."""
    return open_store(target) if isinstance(target, (str, Path)) else target
