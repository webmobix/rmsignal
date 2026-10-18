"""Evidence is stored one record per tool result (ids are content hashes, so a shared result is stored once per date)
plus an ordered id list per subject, so no record approaches a document-size limit and any result is found by id."""

import json
from datetime import date

from rm_dashboard.domain import ToolResult

from .base import Artifact, ArtifactStore, Kind

# Index namespaces: which subject's evidence an index lists.
REPORT = "report"
OUTLOOK_MARKET = "outlook-market"
OUTLOOK_INSTRUMENT = "outlook-instrument"
SCENARIO_VECTOR = "scenario-vector"
SCENARIO_IMPACT = "scenario-impact"


def evidence_items(as_of: date, namespace: str, subject: str, results: list[ToolResult]) -> list[Artifact]:
    """The records to save: each result once, then the subject's index last."""
    seen: dict[str, Artifact] = {}
    for r in results:
        seen.setdefault(r.evidence_id, Artifact(as_of, Kind.EVIDENCE, r.evidence_id, r.model_dump_json()))
    index = json.dumps([r.evidence_id for r in results])
    return [*seen.values(), Artifact(as_of, Kind.EVIDENCE_INDEX, f"{namespace}/{subject}", index)]


def put_evidence(store: ArtifactStore, as_of: date, namespace: str, subject: str, results: list[ToolResult]) -> None:
    store.put_many(evidence_items(as_of, namespace, subject, results))


def get_evidence(store: ArtifactStore, as_of: date, namespace: str, subject: str) -> list[ToolResult] | None:
    """The subject's results in the order they were saved; ``None`` when the subject has no evidence index."""
    raw = store.get(as_of, Kind.EVIDENCE_INDEX, f"{namespace}/{subject}")
    if raw is None:
        return None
    try:
        ids = json.loads(raw)
    except ValueError:
        return None
    bodies = store.get_many(as_of, Kind.EVIDENCE, ids)
    out: list[ToolResult] = []
    for i in ids:
        try:
            out.append(ToolResult.model_validate_json(bodies[i]))
        except (KeyError, ValueError):
            continue
    return out


def find_evidence(store: ArtifactStore, as_of: date, evidence_id: str) -> ToolResult | None:
    body = store.get(as_of, Kind.EVIDENCE, evidence_id)
    if body is None:
        return None
    try:
        return ToolResult.model_validate_json(body)
    except ValueError:
        return None
