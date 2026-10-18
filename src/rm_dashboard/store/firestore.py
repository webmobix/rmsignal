"""Firestore artifact store: one flat collection, document id ``"{as_of}|{kind}|{key}"`` (``/`` and ``%`` percent-encoded, as an
id cannot contain a slash), the body kept as JSON text so Firestore's map, NaN and field-name rules never apply to it.

Runners get a read-only store: saving or deleting raises ``ReadOnlyStore`` naming the loader. ``rm-dashboard-load`` opens the same
class writable. Listing keys is a range query on the document id, so it needs no composite index; the dates come from marker
documents in the ``runs`` collection, which the loader writes once a date's artifacts are in."""

from collections.abc import Iterable
from datetime import date

from rm_dashboard.firestore_client import document_id_field, open_client, where

from .base import GLOBAL, Artifact, Kind, ReadOnlyStore

COLLECTION = "artifacts"
RUNS = "runs"
BATCH_OPS = 400
"""Operations per commit: Firestore allows 500."""
BATCH_BYTES = 8 * 1024 * 1024
"""Bytes per commit: Firestore allows 10 MiB."""
MAX_BODY = 1_000_000
"""A document is limited to 1 MiB including its name and fields."""
READ_ONLY = ("the Firestore backend is read-only for runners: publish artifacts with "
             "`rm-dashboard-load artifacts --to firestore:<project>` and run the stages against SQLite")
_ESCAPES = {"%": "%25", "/": "%2F"}


def encode(text: str) -> str:
    return "".join(_ESCAPES.get(ch, ch) for ch in text)


def doc_id(as_of: date, kind: Kind, key: str) -> str:
    return f"{as_of.isoformat()}|{kind}|{encode(key)}"


class FirestoreArtifactStore:
    def __init__(self, client, *, collection: str = COLLECTION, runs: str = RUNS, writable: bool = False, location: str = ""):
        self.client = client
        self.collection = collection
        self.runs = runs
        self.writable = writable
        self._location = location or f"firestore:{getattr(client, 'project', '')}"

    @property
    def location(self) -> str:
        return self._location

    def __repr__(self) -> str:
        return f"FirestoreArtifactStore({self._location!r}{', writable' if self.writable else ''})"

    def require_writable(self) -> None:
        if not self.writable:
            raise ReadOnlyStore(READ_ONLY)

    # ---- reading ---------------------------------------------------------------------------------
    def _coll(self):
        return self.client.collection(self.collection)

    def get(self, as_of: date, kind: Kind, key: str) -> str | None:
        snap = self._coll().document(doc_id(as_of, kind, key)).get()
        return snap.to_dict()["body"] if snap.exists else None

    def get_many(self, as_of: date, kind: Kind, keys: Iterable[str]) -> dict[str, str]:
        wanted = list(dict.fromkeys(keys))
        out: dict[str, str] = {}
        for i in range(0, len(wanted), 100):
            refs = [self._coll().document(doc_id(as_of, kind, k)) for k in wanted[i:i + 100]]
            for snap in self.client.get_all(refs):
                if snap.exists:
                    d = snap.to_dict()
                    out[d["key"]] = d["body"]
        return out

    def keys(self, as_of: date, kind: Kind, prefix: str = "") -> list[str]:
        start = doc_id(as_of, kind, prefix)
        coll = self._coll()
        q = where(coll, document_id_field(), ">=", coll.document(start))
        q = where(q, document_id_field(), "<", coll.document(start + "\U0010ffff"))
        return sorted(d.to_dict()["key"] for d in q.select(["key"]).stream())  # ascending by key, not by encoded id

    def dates(self) -> list[date]:
        return sorted(date.fromisoformat(d.id) for d in self.client.collection(self.runs).stream() if d.id != GLOBAL.isoformat())

    # ---- writing (the loader only) ------------------------------------------------------------------
    def put(self, as_of: date, kind: Kind, key: str, body: str) -> None:
        self.put_many([Artifact(as_of, kind, key, body)])

    def put_many(self, items: Iterable[Artifact]) -> None:
        """Written in commits of at most ``BATCH_OPS`` operations and ``BATCH_BYTES`` bytes. Not atomic across commits: the loader
        writes evidence before what cites it and is repeatable."""
        self.require_writable()
        batch, ops, size = self.client.batch(), 0, 0
        for a in items:
            if len(a.body.encode()) > MAX_BODY:
                raise ValueError(f"artifact {a.kind} {a.key} of {a.as_of} is {len(a.body.encode())} bytes: over the Firestore document limit")
            if ops >= BATCH_OPS or size + len(a.body) > BATCH_BYTES:
                batch.commit()
                batch, ops, size = self.client.batch(), 0, 0
            batch.set(self._coll().document(doc_id(a.as_of, a.kind, a.key)),
                      {"as_of": a.as_of.isoformat(), "kind": str(a.kind), "key": a.key, "body": a.body})
            ops, size = ops + 1, size + len(a.body)
        if ops:
            batch.commit()

    def mark_run(self, as_of: date) -> None:
        """Record that ``as_of`` has artifacts: ``dates()`` lists only the dates marked."""
        self.require_writable()
        self.client.collection(self.runs).document(as_of.isoformat()).set({"as_of": as_of.isoformat()})

    def delete_prefix(self, as_of: date, kind: Kind, prefix: str = "") -> int:
        self.require_writable()
        keys = self.keys(as_of, kind, prefix)
        for i in range(0, len(keys), BATCH_OPS):
            batch = self.client.batch()
            for k in keys[i:i + BATCH_OPS]:
                batch.delete(self._coll().document(doc_id(as_of, kind, k)))
            batch.commit()
        return len(keys)

    def unmark_run(self, as_of: date) -> None:
        self.require_writable()
        self.client.collection(self.runs).document(as_of.isoformat()).delete()


def open_firestore_store(location: str, *, writable: bool = False) -> FirestoreArtifactStore:
    """``location`` is ``<project>[/<database>]``. Raises ImportError (naming the extra to install) without the client library."""
    return FirestoreArtifactStore(open_client(location), writable=writable, location=f"firestore:{location}")
