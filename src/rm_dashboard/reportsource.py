"""Reads the stored output of a batch run: reports, their evidence and stable finding references."""

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from rm_dashboard.domain import Report, ToolResult
from rm_dashboard.store import ArtifactStore, Kind, as_store, read_model
from rm_dashboard.store.evidence import REPORT, get_evidence


@dataclass(frozen=True)
class FlatFinding:
    """One finding of a report tree. ``ref`` is stable: ``CL-0001#f7`` or ``CL-0001/PF-0001#f3`` (1-based)."""

    ref: str
    report_path: str
    claim: str
    confidence: str
    evidence_ids: tuple[str, ...]


def flatten(report: Report) -> list[FlatFinding]:
    """Findings of a report and, depth first, of its child reports."""
    out: list[FlatFinding] = []

    def walk(r: Report, path: str) -> None:
        for i, f in enumerate(r.findings, start=1):
            out.append(FlatFinding(f"{path}#f{i}", path, f.claim, f.confidence, tuple(f.evidence_ids)))
        for c in r.children:
            walk(c, f"{path}/{c.subject}")

    walk(report, report.subject)
    return out


class StoreReportSource:
    """The reports and evidence of the batch runner, read from the artifact store."""

    def __init__(self, store: ArtifactStore | str | Path):
        self.store = as_store(store)

    def location(self, as_of: date) -> str:
        return f"{self.store.location} ({as_of})"

    def client_ids(self, as_of: date) -> list[str]:
        return self.store.keys(as_of, Kind.REPORT)

    def report(self, as_of: date, client_id: str) -> Report | None:
        return read_model(self.store, as_of, Kind.REPORT, client_id, Report)

    def evidence(self, as_of: date, client_id: str) -> dict[str, ToolResult] | None:
        results = get_evidence(self.store, as_of, REPORT, client_id)
        return None if results is None else {r.evidence_id: r for r in results}
