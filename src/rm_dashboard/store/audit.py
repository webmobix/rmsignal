"""The audit trail in a store: one record per entry, key ``<stage>/<seq:08d>``. Append-only; a stage is replaced as a whole."""

import json
from datetime import date

from .base import ArtifactStore, Kind


class StoreAuditSink:
    """Where an ``AuditLog`` writes. ``resume`` continues the numbering of an earlier run of the same stage; ``replace``
    removes the earlier trail first."""

    def __init__(self, store: ArtifactStore, as_of: date, stage: str, *, replace: bool = False):
        self.store, self.as_of, self.stage = store, as_of, stage
        if replace:
            store.delete_prefix(as_of, Kind.AUDIT, f"{stage}/")

    @property
    def last_seq(self) -> int:
        keys = self.store.keys(self.as_of, Kind.AUDIT, f"{self.stage}/")
        return int(keys[-1].rsplit("/", 1)[1]) if keys else 0

    def __call__(self, seq: int, record: dict) -> None:
        self.store.put(self.as_of, Kind.AUDIT, f"{self.stage}/{seq:08d}", json.dumps(record, default=str))


def read_audit(store: ArtifactStore, as_of: date, stage: str) -> list[dict]:
    keys = store.keys(as_of, Kind.AUDIT, f"{stage}/")
    bodies = store.get_many(as_of, Kind.AUDIT, keys)
    return [json.loads(bodies[k]) for k in keys if k in bodies]
