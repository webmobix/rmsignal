"""``/api/evidence/{evidence_id}``: one stored tool result and everything that cites it."""

import json
from datetime import date
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from rm_dashboard.domain import ToolResult
from rm_dashboard.reportsource import flatten

from .context import ReadContext
from .deps import AsOf, Ctx
from .overview import build_overview

router = APIRouter(prefix="/api", tags=["evidence"])


class Citation(BaseModel):
    kind: Literal["finding", "action", "market_view", "instrument_view"]
    ref: str
    client_id: str | None = None
    portfolio_id: str | None = None
    instrument_id: str | None = None
    text: str


class EvidenceResponse(BaseModel):
    as_of: date
    evidence_id: str
    result: ToolResult
    cited_by: list[Citation]


def _evidence_files(ctx: ReadContext, as_of: date) -> list[Path]:
    run = ctx.reports.run_dir(as_of)
    files = sorted((run / "evidence").glob("*.json")) if (run / "evidence").is_dir() else []
    out = run / "outlook" / "evidence"
    if out.is_dir():
        files += sorted(out.rglob("*.json"))
    return files


def find_result(ctx: ReadContext, as_of: date, evidence_id: str) -> ToolResult | None:
    for p in _evidence_files(ctx, as_of):
        text = p.read_text()
        if evidence_id not in text:
            continue
        for item in json.loads(text):
            if item.get("evidence_id") == evidence_id:
                return ToolResult.model_validate(item)
    return None


def citations(ctx: ReadContext, as_of: date, evidence_id: str) -> list[Citation]:
    out: list[Citation] = []
    run = ctx.reports.run_dir(as_of)
    for p in sorted(run.glob("CL-*.json")):
        report = ctx.reports.report(as_of, p.stem)
        for f in flatten(report) if report else []:
            if evidence_id in f.evidence_ids:
                parts = f.report_path.split("/")
                out.append(Citation(kind="finding", ref=f.ref, client_id=parts[0],
                                    portfolio_id=parts[1] if len(parts) > 1 else None, text=f.claim))
    for a in build_overview(ctx, as_of).actions:
        if any(evidence_id in r.evidence_ids for r in a.refs):
            out.append(Citation(kind="action", ref=a.action_id, client_id=a.client_id, text=a.title))
    market = ctx.outlooks.load_market(as_of)
    for v in (market.views if market else []):
        if any(evidence_id in d.evidence_ids for d in [*v.drivers, *v.risks]):
            out.append(Citation(kind="market_view", ref=f"market#{v.segment}", text=v.rationale))
    for iid in ctx.outlooks.instrument_ids(as_of):
        o = ctx.outlooks.load_instrument(as_of, iid)
        if o and o.view and any(evidence_id in d.evidence_ids for d in [*o.view.drivers, *o.view.risks]):
            out.append(Citation(kind="instrument_view", ref=f"{iid}#view", instrument_id=iid, text=o.view.rationale))
    return out


@router.get("/evidence/{evidence_id}")
def get_evidence(ctx: Ctx, as_of: AsOf, evidence_id: str) -> EvidenceResponse:
    result = find_result(ctx, as_of, evidence_id)
    if result is None:
        raise HTTPException(404, f"no evidence {evidence_id!r} at {as_of}")
    return EvidenceResponse(as_of=as_of, evidence_id=evidence_id, result=result,
                            cited_by=citations(ctx, as_of, evidence_id))
