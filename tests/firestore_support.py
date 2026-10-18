"""Backends the contract suites run against: SQLite, the in-memory Firestore fake and, when ``FIRESTORE_EMULATOR_HOST`` is set and the
client library is installed, a real Firestore emulator."""

import importlib.util
import os
import uuid
from contextlib import contextmanager
from datetime import date

from firestore_fake import FakeClient

from rm_dashboard.store import GLOBAL
from rm_dashboard.store.firestore import FirestoreArtifactStore

EMULATOR = bool(os.environ.get("FIRESTORE_EMULATOR_HOST")) and importlib.util.find_spec("google.cloud.firestore") is not None
BACKENDS = ["sqlite", "firestore", *(["emulator"] if EMULATOR else [])]


class LoaderArtifactStore(FirestoreArtifactStore):
    """A writable Firestore store that marks the dates it writes, as ``rm-dashboard-load`` does."""

    def put_many(self, items):
        items = list(items)
        super().put_many(items)
        for d in {a.as_of for a in items if a.as_of != GLOBAL}:
            self.mark_run(d)


def new_client(backend: str):
    if backend == "emulator":
        from google.cloud import firestore

        return firestore.Client(project=f"test-{uuid.uuid4().hex[:8]}")
    return FakeClient()


def new_store(backend: str, tmp_path):
    from rm_dashboard.store import SqliteArtifactStore

    if backend == "sqlite":
        return SqliteArtifactStore(tmp_path / "artifacts.db")
    suffix = uuid.uuid4().hex[:8]
    return LoaderArtifactStore(new_client(backend), collection=f"artifacts-{suffix}", runs=f"runs-{suffix}", writable=True)


@contextmanager
def patched_client(client):
    """Make every ``open_client`` in the application return ``client``."""
    import pytest

    mp = pytest.MonkeyPatch()
    for mod in ("rm_dashboard.firestore_client", "rm_dashboard.data.firestore", "rm_dashboard.store.firestore", "rm_dashboard.loader.firestore"):
        mp.setattr(f"{mod}.open_client", lambda spec, _c=client: _c, raising=False)
    try:
        yield client
    finally:
        mp.undo()


__all__ = ["BACKENDS", "FakeClient", "LoaderArtifactStore", "date", "new_client", "new_store", "patched_client"]
