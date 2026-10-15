"""Builds the ``ToolResult`` envelope from repository results and analytic outputs."""

from datetime import date
from typing import Any

from pydantic import BaseModel

from rm_dashboard.analytics.base import Calc
from rm_dashboard.domain import Computation, QualityFlag, Source, ToolResult
from rm_dashboard.pit import PitResult


def _merge_flags(flags: list[QualityFlag]) -> list[QualityFlag]:
    seen, out = set(), []
    for f in flags:
        k = (f.code, f.subject, f.message)
        if k not in seen:
            seen.add(k)
            out.append(f)
    return out


def build_result(*, tool: str, version: str, params: BaseModel, as_of: date, data: Any,
                 pits: list[PitResult] | None = None, calc: Calc | None = None, method: str = "",
                 status: str | None = None, reason: str | None = None,
                 extra_flags: list[QualityFlag] | None = None, mock: bool = False,
                 pit_tag: str | None = None) -> ToolResult:
    pits = pits or []
    flags: list[QualityFlag] = []
    sources: list[Source] = []
    for p in pits:
        flags += p.flags
        sources += p.sources
    if calc:
        flags += calc.flags
        method = calc.method
    flags += extra_flags or []

    eff = next((p.effective_snapshot_date for p in pits if p.effective_snapshot_date), None)
    gap = next((p.gap_days for p in pits if p.effective_snapshot_date), None)

    st, why = "ok", None
    bad = next((p for p in pits if p.status != "ok"), None)
    if bad:
        st, why = bad.status, bad.reason
    elif calc and calc.status != "ok":
        st, why = calc.status, calc.reason
    if status:
        st, why = status, reason or why
    if pit_tag is None:
        tags = {p.pit for p in pits}
        pit_tag = "current_only" if "current_only" in tags else (next(iter(tags)) if len(tags) == 1 else None)

    return ToolResult(
        data=data, as_of=as_of, effective_snapshot_date=eff, gap_days=gap, status=st, reason=why,
        sources=sources, computation=Computation(
            tool=tool, version=version, parameters=params.model_dump(mode="json"), method=method),
        flags=_merge_flags(flags), pit=pit_tag, mock=mock,
    )


def rows(pit: PitResult) -> list[dict]:
    return pit.frame.to_dicts() if pit.frame.height else []
