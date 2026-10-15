"""Reads the persisted output of a batch run: reports, their evidence and stable finding references."""

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from rm_dashboard.domain import Report, ToolResult


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


class FolderReportSource:
    """``<base>/<as_of>/<client>.json`` and ``evidence/<client>.json`` as written by the batch runner."""

    def __init__(self, base_dir: str | Path):
        self.base_dir = Path(base_dir)

    def run_dir(self, as_of: date) -> Path:
        return self.base_dir / as_of.isoformat()

    def report(self, as_of: date, client_id: str) -> Report | None:
        p = self.run_dir(as_of) / f"{client_id}.json"
        return Report.model_validate_json(p.read_text()) if p.is_file() else None

    def evidence(self, as_of: date, client_id: str) -> dict[str, ToolResult] | None:
        p = self.run_dir(as_of) / "evidence" / f"{client_id}.json"
        if not p.is_file():
            return None
        return {r.evidence_id: r for r in (ToolResult.model_validate(x) for x in json.loads(p.read_text()))}
