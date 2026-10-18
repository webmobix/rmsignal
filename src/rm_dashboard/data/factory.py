"""Choosing the source-data backend: ``sqlite:<file>`` or ``firestore:<project>[/<database>]``. A bare path means SQLite."""

import re
from pathlib import Path

from .contract import DataSource
from .datasource import SqliteDataSource

BACKENDS = ("sqlite", "firestore")


def parse_spec(spec: str | Path) -> tuple[str, str]:
    """``(backend, rest)``. Raises ValueError for a backend that is not one of ``BACKENDS``."""
    text = str(spec)
    m = re.match(r"^([A-Za-z][A-Za-z0-9+.-]*):(.*)$", text)
    if m is None:
        return "sqlite", text
    backend, rest = m.groups()
    if backend not in BACKENDS:
        raise ValueError(f"unknown data source backend {backend!r}; valid backends: {', '.join(BACKENDS)}")
    return backend, rest


def open_data_source(spec: str | Path) -> DataSource:
    """The datasource named by ``spec``. Raises FileNotFoundError for a missing SQLite file, ValueError for an unknown backend."""
    backend, rest = parse_spec(spec)
    if backend == "sqlite":
        if not rest:
            raise ValueError("sqlite data source needs a path: sqlite:<file>")
        return SqliteDataSource(rest)
    from .firestore import open_firestore_data_source  # lazy: the Firestore client library is optional

    return open_firestore_data_source(rest)
