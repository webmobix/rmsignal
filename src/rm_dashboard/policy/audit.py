"""Append-only audit trail. There is no update or delete."""

import hashlib
import json
import threading
from dataclasses import asdict, dataclass, field
from typing import Any, Callable


def input_hash(payload: Any) -> str:
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(text.encode()).hexdigest()[:16]


@dataclass(frozen=True)
class AuditRecord:
    seq: int
    run_id: str
    kind: str  # decision | tool_call | tool_error | tool_refused | model_call | a2a_call
    agent: str
    subject: str
    as_of: str
    input_hash: str
    evidence_ids: tuple[str, ...] = ()
    requester_chain: tuple[str, ...] = ()
    detail: dict[str, Any] = field(default_factory=dict)


class AuditLog:
    def __init__(self, *, sink: Callable[[int, dict], None] | None = None, start_seq: int = 0):
        """``sink(seq, record)`` receives each entry as it is appended (an artifact store); ``start_seq`` continues
        the numbering of an earlier run of the same trail."""
        self._records: list[AuditRecord] = []
        self._sink = sink
        self._start = start_seq
        self._lock = threading.Lock()

    def append(self, **fields: Any) -> AuditRecord:
        with self._lock:
            rec = AuditRecord(seq=self._start + len(self._records) + 1, **fields)
            self._records.append(rec)
            if self._sink:
                self._sink(rec.seq, asdict(rec))
        return rec

    @property
    def records(self) -> tuple[AuditRecord, ...]:
        return tuple(self._records)

    def for_run(self, run_id: str) -> list[AuditRecord]:
        return [r for r in self._records if r.run_id == run_id]
