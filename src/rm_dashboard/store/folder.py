"""Reads the artifacts of an older ``reports/<as_of>/...`` folder tree, as the runners used to write it, and presents them
at their new addresses: evidence and audit trails come out re-chunked into one record per tool result and per entry.

    <as_of>/<client>.json, evidence/<client>.json, summary.json, audit.jsonl            report, evidence, run summary and audit of "analyse"
    <as_of>/{reconciliation,mandate-reconciliation,actions,overview}/<key>.json, summary.json, audit.jsonl
    <as_of>/outlook/market.json, evidence/market.json, instruments/<id>.json, evidence/instruments/<id>.json, summary.json, audit.jsonl
    <as_of>/scenarios/<id>/{vector,rollup}.json, impacts/<pf>.json, clients/<cl>.json, evidence/vector.json, evidence/impacts/<pf>.json
    <as_of>/scenarios/summary.json, audit.jsonl;  scenarios/catalogue.json (no date)
"""

import json
from collections.abc import Iterator
from datetime import date
from pathlib import Path

from rm_dashboard.domain import ToolResult

from . import evidence as ev
from .base import GLOBAL, Artifact, Kind

# folder name -> (kind of its per-key JSON files, stage name of its summary and audit trail)
_STAGES = {
    "reconciliation": (Kind.RECONCILIATION, "reconcile"),
    "mandate-reconciliation": (Kind.MANDATE_RECONCILIATION, "mandate-reconcile"),
    "actions": (Kind.ACTIONS, "actions"),
    "overview": (Kind.OVERVIEW, "overview"),
}


def looks_like_reports_folder(path: Path) -> bool:
    return path.is_dir() and any(_as_date(p.name) for p in path.iterdir() if p.is_dir())


def _as_date(name: str) -> date | None:
    try:
        return date.fromisoformat(name)
    except ValueError:
        return None


def _json_files(d: Path) -> list[Path]:
    return sorted(d.glob("*.json")) if d.is_dir() else []


class FolderArtifactSource:
    """``dates()`` and ``items(as_of)``, the same shape as a store source in the loader."""

    def __init__(self, root: str | Path):
        self.root = Path(root)

    @property
    def location(self) -> str:
        return str(self.root)

    def dates(self) -> list[date]:
        return sorted(d for p in self.root.iterdir() if p.is_dir() and (d := _as_date(p.name)))

    def items(self, as_of: date) -> Iterator[Artifact]:
        if as_of == GLOBAL:
            yield from self._catalogue()
            return
        run = self.root / as_of.isoformat()
        yield from self._clients(run, as_of)
        for folder, (kind, stage) in _STAGES.items():
            yield from self._keyed(run / folder, as_of, kind, stage)
        yield from self._outlook(run / "outlook", as_of)
        yield from self._scenarios(run / "scenarios", as_of)

    # ---- pieces ----------------------------------------------------------------------------
    def _catalogue(self) -> Iterator[Artifact]:
        p = self.root / "scenarios" / "catalogue.json"
        if p.is_file():
            yield Artifact(GLOBAL, Kind.SCENARIO_CATALOGUE, "catalogue", p.read_text())

    @staticmethod
    def _results(path: Path) -> list[ToolResult]:
        return [ToolResult.model_validate(x) for x in json.loads(path.read_text())]

    @staticmethod
    def _stage_files(d: Path, as_of: date, stage: str) -> Iterator[Artifact]:
        summary = d / "summary.json"
        if summary.is_file():
            yield Artifact(as_of, Kind.RUN_SUMMARY, stage, summary.read_text())
        audit = d / "audit.jsonl"
        if audit.is_file():
            lines = [ln for ln in audit.read_text().splitlines() if ln.strip()]
            for n, line in enumerate(lines, start=1):  # line order is the order of appending
                rec = json.loads(line)
                rec["seq"] = n
                yield Artifact(as_of, Kind.AUDIT, f"{stage}/{n:08d}", json.dumps(rec, default=str))

    def _clients(self, run: Path, as_of: date) -> Iterator[Artifact]:
        for p in _json_files(run):
            if p.name == "summary.json":
                continue
            cid = p.stem
            efile = run / "evidence" / p.name
            if efile.is_file():  # evidence first, the report last
                yield from ev.evidence_items(as_of, ev.REPORT, cid, self._results(efile))
            yield Artifact(as_of, Kind.REPORT, cid, p.read_text())
        yield from self._stage_files(run, as_of, "analyse")

    def _keyed(self, d: Path, as_of: date, kind: Kind, stage: str) -> Iterator[Artifact]:
        for p in _json_files(d):
            if p.name != "summary.json":
                yield Artifact(as_of, kind, p.stem, p.read_text())
        yield from self._stage_files(d, as_of, stage)

    def _outlook(self, d: Path, as_of: date) -> Iterator[Artifact]:
        market = d / "market.json"
        if market.is_file():
            mev = d / "evidence" / "market.json"
            if mev.is_file():
                yield from ev.evidence_items(as_of, ev.OUTLOOK_MARKET, "market", self._results(mev))
            yield Artifact(as_of, Kind.OUTLOOK_MARKET, "market", market.read_text())
        for p in _json_files(d / "instruments"):
            iev = d / "evidence" / "instruments" / p.name
            if iev.is_file():
                yield from ev.evidence_items(as_of, ev.OUTLOOK_INSTRUMENT, p.stem, self._results(iev))
            yield Artifact(as_of, Kind.OUTLOOK_INSTRUMENT, p.stem, p.read_text())
        yield from self._stage_files(d, as_of, "outlook")

    def _scenarios(self, d: Path, as_of: date) -> Iterator[Artifact]:
        if not d.is_dir():
            return
        for sd in sorted(p for p in d.iterdir() if p.is_dir()):
            sid = sd.name
            vev = sd / "evidence" / "vector.json"
            if vev.is_file():
                yield from ev.evidence_items(as_of, ev.SCENARIO_VECTOR, sid, self._results(vev))
            if (sd / "vector.json").is_file():
                yield Artifact(as_of, Kind.SCENARIO_VECTOR, sid, (sd / "vector.json").read_text())
            for p in _json_files(sd / "impacts"):
                iev = sd / "evidence" / "impacts" / p.name
                if iev.is_file():
                    yield from ev.evidence_items(as_of, ev.SCENARIO_IMPACT, f"{sid}/{p.stem}", self._results(iev))
                yield Artifact(as_of, Kind.SCENARIO_IMPACT, f"{sid}/{p.stem}", p.read_text())
            for p in _json_files(sd / "clients"):
                yield Artifact(as_of, Kind.SCENARIO_CLIENT, f"{sid}/{p.stem}", p.read_text())
            if (sd / "rollup.json").is_file():
                yield Artifact(as_of, Kind.SCENARIO_ROLLUP, sid, (sd / "rollup.json").read_text())
        yield from self._stage_files(d, as_of, "scenarios")
