"""Outlook guard: the model proposes views, code decides what they may rest on and what changed."""

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from rm_dashboard.agents.guard import evidence_numbers, unsupported_numbers
from rm_dashboard.domain import Gap, ToolResult
from rm_dashboard.tools import EvidenceStore

from .contracts import (
    CONFIDENCES, DEFAULT_HORIZON, DIRECTIONS, HORIZONS, Change, EventRef, InstrumentOutlook, InstrumentView, MarketOutlook, Reason, View,
    ViewBody,
)

EVENT_TOOLS = ("events.list", "news.list", "events.relevant")
PRIOR_TOOLS = ("outlook.previous_market", "outlook.previous_instrument")
TREND_TOOLS = ("analytics.market_trend", "market.history")


@dataclass
class GuardInput:
    store: EvidenceStore
    as_of: date
    required: list[str]
    prev: MarketOutlook | None = None
    all_events: list[dict] = field(default_factory=list)
    severe_in_window: list[EventRef] = field(default_factory=list)


@dataclass
class GuardOutcome:
    views: list[View]
    summary: str
    gaps: list[Gap]
    unaddressed: list[EventRef]
    changes_summary: str
    fresh: int = 0
    """Views that came from the model, as opposed to previous views kept for a segment it did not answer."""


def seen_events(store: EvidenceStore) -> dict[str, tuple[dict, list[str]]]:
    """event_id -> (event, evidence ids of the tool results that returned it), for events returned in this run."""
    out: dict[str, tuple[dict, list[str]]] = {}
    for r in store.results.values():
        if r.computation.tool not in EVENT_TOOLS or r.status != "ok" or not r.data:
            continue
        items = (r.data.get("news") or r.data.get("events") or []) if isinstance(r.data, dict) else r.data
        for e in items:
            if isinstance(e.get("event_date"), str):
                e = {**e, "event_date": date.fromisoformat(e["event_date"])}
            ev, ids = out.setdefault(e["event_id"], (e, []))
            if r.evidence_id not in ids:
                ids.append(r.evidence_id)
    return out


def latest_snapshot(r: ToolResult) -> date | None:
    """Date of the newest market snapshot a trend or history result covers."""
    d = r.data
    if r.computation.tool == "analytics.market_trend" and isinstance(d, dict):
        v = d.get("latest_snapshot_date")
        return date.fromisoformat(v) if isinstance(v, str) else v
    if r.computation.tool == "instruments.context" and isinstance(d, dict):
        v = (d.get("summary") or {}).get("latest_date")
        return date.fromisoformat(v) if isinstance(v, str) else v
    if r.computation.tool == "market.history" and isinstance(d, list) and d:
        dates = [s["values"][-1]["snapshot_date"] for s in d if s.get("values")]
        return max((date.fromisoformat(x) if isinstance(x, str) else x) for x in dates) if dates else None
    return None


class _Core:
    """What both outlooks share: citations, grounded figures, derived change and the body of a view."""

    def __init__(self, store: EvidenceStore, as_of: date):
        self.store, self.as_of = store, as_of
        self.gaps: list[Gap] = []
        self.events = seen_events(store)
        self.numbers: dict[str, set[float]] = {}

    def gap(self, subject: str, text: str) -> None:
        self.gaps.append(Gap(kind="guard_removed", subject=subject[:80], description=text))

    # ---- evidence ------------------------------------------------------------------
    def pool(self, ids: list[str], refs: list[str] = ()) -> set[float]:
        out: set[float] = set()
        for i in ids:
            if i not in self.numbers:
                self.numbers[i] = evidence_numbers(self.store.get(i).data)
            out |= self.numbers[i]
        for r in refs:
            out |= evidence_numbers(self.events[r][0])
        return out

    def reason(self, raw: Any, where: str) -> Reason | None:
        if not isinstance(raw, dict) or not isinstance(raw.get("claim"), str) or not raw["claim"].strip():
            self.gap(where, f"{where}: an entry without a claim was removed")
            return None
        claim = raw["claim"]
        ids = raw.get("evidence_ids") if isinstance(raw.get("evidence_ids"), list) else []
        refs = raw.get("event_refs") if isinstance(raw.get("event_refs"), list) else []
        if not all(isinstance(i, str) for i in [*ids, *refs]):
            self.gap(claim, f"{where} removed: evidence ids and event refs must be text")
            return None
        unknown = [i for i in ids if i not in self.store]
        if unknown:
            self.gap(claim, f"{where} removed: cites evidence not produced in this run ({', '.join(unknown)})")
            return None
        if any(self.store.get(i).computation.tool in PRIOR_TOOLS for i in ids):
            self.gap(claim, f"{where} removed: the previous outlook is a reference, not support")
            return None
        stale = sorted({str(self.store.get(i).as_of) for i in ids if self.store.get(i).as_of != self.as_of})
        if stale:
            self.gap(claim, f"{where} removed: cites evidence from as_of {', '.join(stale)}, not {self.as_of}")
            return None
        missing = [r for r in refs if r not in self.events]
        if missing:
            self.gap(claim, f"{where} removed: cites event(s) that were not returned in this run ({', '.join(missing)})")
            return None
        ids = list(dict.fromkeys([*ids, *(i for r in refs for i in self.events[r][1])]))
        if not ids:
            self.gap(claim, f"{where} removed: it cites no evidence")
            return None
        bad = unsupported_numbers(claim, self.pool(ids, refs))
        if bad:
            self.gap(claim, f"{where} removed: figure(s) " + ", ".join(f"{b:g}" for b in bad) + " not present in the cited evidence")
            return None
        return Reason(claim=claim, evidence_ids=ids, event_refs=list(dict.fromkeys(refs)))

    def reasons(self, raw: Any, where: str) -> list[Reason]:
        return [r for r in (self.reason(x, where) for x in (raw if isinstance(raw, list) else [])) if r]

    def text(self, value: Any, ids: list[str], refs: list[str], subject: str, what: str) -> str:
        if not isinstance(value, str) or not value.strip():
            return ""
        bad = unsupported_numbers(value, self.pool(ids, refs))
        if bad:
            self.gap(subject, f"{what} removed: figure(s) " + ", ".join(f"{b:g}" for b in bad) + " not present in the cited evidence")
            return ""
        return value

    # ---- to be provided by the outlook kind ------------------------------------------------
    def new_since_previous(self, ids: list[str], refs: list[str]) -> tuple[list[str], list[str]]:
        raise NotImplementedError

    def confidence_limit(self, ids: list[str], refs: list[str]) -> str:
        raise NotImplementedError

    # ---- the body of one view ----------------------------------------------------------------
    def body(self, raw: dict, label: str, before: ViewBody | None, prev_as_of: date | None) -> dict | None:
        direction, conf = raw.get("direction"), raw.get("confidence")
        horizon = raw.get("horizon") or DEFAULT_HORIZON
        if direction not in DIRECTIONS or horizon not in HORIZONS or conf not in CONFIDENCES:
            self.gap(label, f"view {label} removed: direction, horizon and confidence must come from the closed sets")
            return None
        drivers = self.reasons(raw.get("drivers"), f"driver ({label})")
        if not drivers:
            self.gap(label, f"view {label} removed: no driver rests on valid evidence")
            return None
        risks = self.reasons(raw.get("risks"), f"risk ({label})")
        ch_raw = raw.get("change") if isinstance(raw.get("change"), dict) else {}
        ch_reason = self.reason({"claim": ch_raw.get("why") or "n/a", "evidence_ids": ch_raw.get("evidence_ids") or [],
                                 "event_refs": ch_raw.get("event_refs") or []}, f"change ({label})") if (ch_raw.get("evidence_ids") or ch_raw.get("event_refs")) else None
        ids = list(dict.fromkeys(i for r in [*drivers, *risks] for i in r.evidence_ids))
        refs = list(dict.fromkeys(e for r in [*drivers, *risks] for e in r.event_refs))
        rationale = self.text(raw.get("rationale"), ids, refs, label, f"rationale ({label})")
        would = self.text(raw.get("would_change_if"), ids, refs, label, f"would-change-if ({label})")
        change, direction = self.change(label, direction, before, prev_as_of, drivers, risks, ch_reason, ch_raw)
        ids_all = ids + [i for i in (ch_reason.evidence_ids if ch_reason else []) if i not in ids]
        refs_all = refs + [e for e in (ch_reason.event_refs if ch_reason else []) if e not in refs]
        limit = self.confidence_limit(ids_all, refs_all)
        conf = CONFIDENCES[min(CONFIDENCES.index(conf), CONFIDENCES.index(limit))]
        return dict(direction=direction, horizon=horizon, confidence=conf, rationale=rationale, drivers=drivers, risks=risks,
                    would_change_if=would, change=change)

    def change(self, label: str, direction: str, before: ViewBody | None, prev_as_of: date | None, drivers, risks,
               ch_reason: Reason | None, ch_raw: dict) -> tuple[Change, str]:
        if before is None:
            return Change(kind="new"), direction
        why = ch_raw.get("why") if isinstance(ch_raw.get("why"), str) else ""
        cited = [r for r in (*drivers, *risks, *([ch_reason] if ch_reason else []))]
        ids = list(dict.fromkeys(i for r in cited for i in r.evidence_ids))
        refs = list(dict.fromkeys(e for r in cited for e in r.event_refs))
        new_ids, new_refs = self.new_since_previous(ids, refs)
        if direction == before.direction:
            return Change(kind="unchanged", previous_direction=before.direction, why=why), direction
        if not (new_ids or new_refs):
            self.gaps.append(Gap(kind="guard_removed", subject=label, description=(
                f"direction change of {label} from {before.direction} to {direction} rejected: it cites no evidence newer than {prev_as_of}; "
                f"the previous direction is kept")))
            return Change(kind="unchanged", previous_direction=before.direction, why=why), before.direction
        kind = "upgraded" if DIRECTIONS.index(direction) > DIRECTIONS.index(before.direction) else "downgraded"
        return Change(kind=kind, previous_direction=before.direction, why=why, new_evidence_ids=new_ids, new_event_refs=new_refs), direction


class _Guard(_Core):
    """The market outlook: one view per segment."""

    def __init__(self, g: GuardInput):
        super().__init__(g.store, g.as_of)
        self.g = g
        self.trend_short = any(r.computation.tool == "analytics.market_trend" and r.status == "insufficient_history"
                               for r in g.store.results.values())

    def new_since_previous(self, ids: list[str], refs: list[str]) -> tuple[list[str], list[str]]:
        prev = self.g.prev
        if prev is None:
            return [], []
        new_refs = [r for r in refs if self.events[r][0]["event_date"] > prev.as_of]
        floor = prev.inputs.market_snapshot_date
        new_ids = []
        for i in ids:
            snap = latest_snapshot(self.store.get(i))
            if snap is not None and (floor is None or snap > floor):
                new_ids.append(i)
        return new_ids, new_refs

    def confidence_limit(self, ids: list[str], refs: list[str]) -> str:
        return "low" if self.trend_short else ("medium" if not refs else "high")

    def view(self, raw: Any) -> View | None:
        if not isinstance(raw, dict):
            self.gap("views", "a view that was not an object was removed")
            return None
        seg = raw.get("segment")
        if seg not in self.g.required:
            self.gap(str(seg), f"view removed: segment {seg!r} is not one of {', '.join(self.g.required)}")
            return None
        prev = self.g.prev
        before = next((v for v in prev.views if v.segment == seg), None) if prev else None
        body = self.body(raw, seg, before, prev.as_of if prev else None)
        return None if body is None else View(segment=seg, **body)


def guard_market_outlook(raw_views: list, raw_summary: str, g: GuardInput) -> GuardOutcome:
    guard = _Guard(g)
    views: dict[str, View] = {}
    for raw in raw_views:
        v = guard.view(raw)
        if v is None:
            continue
        if v.segment in views:
            guard.gap(v.segment, f"second view for {v.segment} removed")
            continue
        views[v.segment] = v
    fresh = len(views)
    for seg in g.required:
        if seg in views:
            continue
        before = next((v for v in g.prev.views if v.segment == seg), None) if g.prev else None
        if before is not None:
            views[seg] = before.model_copy(update={"change": Change(kind="unchanged", previous_direction=before.direction,
                                                                      why="no valid new view: the previous view is carried forward")})
            guard.gaps.append(Gap(kind="other", subject=seg, description=f"no valid view for {seg}: the previous view is carried forward"))
        else:
            guard.gaps.append(Gap(kind="no_data", subject=seg, description=f"no view for {seg}"))
    if guard.trend_short:
        guard.gaps.append(Gap(kind="no_data", subject="analytics.market_trend", description="market history is insufficient for a trend: confidence is low"))
    ordered = [views[s] for s in g.required if s in views]
    summary = ""
    if isinstance(raw_summary, str) and raw_summary.strip():
        ids = sorted({i for v in ordered for r in (*v.drivers, *v.risks) for i in r.evidence_ids})
        bad = unsupported_numbers(raw_summary, guard.pool(ids)) if ids else [1.0]
        if bad:
            guard.gap("summary", "summary removed: figure(s) not present in the cited evidence")
        else:
            summary = raw_summary
    cited = {e for v in ordered for r in (*v.drivers, *v.risks) for e in r.event_refs} | {e for v in ordered for e in v.change.new_event_refs}
    unaddressed = [e for e in g.severe_in_window if e.event_id not in cited]
    return GuardOutcome(ordered, summary, guard.gaps, unaddressed, describe_changes(ordered, g.prev), fresh)


def describe_changes(views: list[View], prev: MarketOutlook | None) -> str:
    if prev is None:
        return "First outlook: there is no earlier outlook to compare with."
    counts = {k: sum(1 for v in views if v.change.kind == k) for k in ("upgraded", "downgraded", "unchanged", "new")}
    moved = ", ".join(f"{v.segment} {v.change.previous_direction} -> {v.direction}" for v in views if v.change.kind in ("upgraded", "downgraded"))
    text = f"Compared with {prev.as_of}: " + ", ".join(f"{n} {k}" for k, n in counts.items() if n) + "."
    return text + (f" Moved: {moved}." if moved else "")


# ---- instrument outlook ---------------------------------------------------------------------------
CONTEXT_TOOL = "instruments.context"
MARKET_TOOL = "outlook.market"


@dataclass
class InstrumentGuardInput:
    store: EvidenceStore
    as_of: date
    prev: InstrumentOutlook | None = None
    severe_in_window: list[EventRef] = field(default_factory=list)


@dataclass
class InstrumentGuardOutcome:
    view: InstrumentView | None
    summary: str
    gaps: list[Gap]
    unaddressed: list[EventRef]
    changes_summary: str
    cited_events: list[EventRef]
    unavailable_statistics: list[str]
    fresh: bool = False
    """The view came from the model, as opposed to the previous view kept because the model gave none."""


class _InstrumentGuard(_Core):
    """The outlook of one instrument: one view, confidence bounded by history, events and peers."""

    def __init__(self, g: InstrumentGuardInput):
        super().__init__(g.store, g.as_of)
        self.g = g
        self.context = [r for r in g.store.results.values() if r.computation.tool == CONTEXT_TOOL]
        self.unavailable = sorted({name for r in self.context if isinstance(r.data, dict)
                                   for name, st in (r.data.get("risk_statistics") or {}).items() if st.get("status") != "ok"})
        self.history_short = not self.context or any(r.status != "ok" for r in self.context) or bool(self.unavailable)

    def new_since_previous(self, ids: list[str], refs: list[str]) -> tuple[list[str], list[str]]:
        prev = self.g.prev
        if prev is None:
            return [], []
        new_refs = [r for r in refs if self.events[r][0]["event_date"] > prev.as_of]
        floor, digest = prev.inputs.price_snapshot_date, prev.inputs.market_outlook_digest
        new_ids = []
        for i in ids:
            r = self.store.get(i)
            snap = latest_snapshot(r)
            if snap is not None and (floor is None or snap > floor):
                new_ids.append(i)
            elif r.computation.tool == MARKET_TOOL and isinstance(r.data, dict) and r.data.get("digest") != digest:
                new_ids.append(i)
        return new_ids, new_refs

    def peer_comparison_cited(self, ids: list[str]) -> bool:
        return any(i in ids and self.store.get(i).computation.tool == CONTEXT_TOOL and isinstance(self.store.get(i).data, dict)
                   and (self.store.get(i).data.get("peers") or {}).get("members") for i in ids)

    def confidence_limit(self, ids: list[str], refs: list[str]) -> str:
        if self.history_short:
            return "low"
        return "high" if refs or self.peer_comparison_cited(ids) else "medium"

    def view(self, raw: Any) -> InstrumentView | None:
        if not isinstance(raw, dict):
            self.gap("view", "a view that was not an object was removed")
            return None
        prev = self.g.prev
        body = self.body(raw, "instrument", prev.view if prev else None, prev.as_of if prev else None)
        return None if body is None else InstrumentView(**body)


def guard_instrument_outlook(raw_view: Any, raw_summary: str, g: InstrumentGuardInput) -> InstrumentGuardOutcome:
    guard = _InstrumentGuard(g)
    view = guard.view(raw_view)
    fresh = view is not None
    prev = g.prev
    if view is None and prev is not None and prev.view is not None:
        view = prev.view.model_copy(update={"change": Change(kind="unchanged", previous_direction=prev.view.direction,
                                                               why="no valid new view: the previous view is carried forward")})
        guard.gaps.append(Gap(kind="other", subject="instrument", description="no valid view: the previous view is carried forward"))
    elif view is None:
        guard.gaps.append(Gap(kind="no_data", subject="instrument", description="no view"))
    summary = ""
    if isinstance(raw_summary, str) and raw_summary.strip() and view is not None:
        ids = sorted({i for r in (*view.drivers, *view.risks) for i in r.evidence_ids})
        if ids and not unsupported_numbers(raw_summary, guard.pool(ids)):
            summary = raw_summary
        else:
            guard.gap("summary", "summary removed: figure(s) not present in the cited evidence")
    cited_ids = list(dict.fromkeys(e for r in ((*view.drivers, *view.risks) if view else ()) for e in r.event_refs))
    cited_ids += [e for e in (view.change.new_event_refs if view else []) if e not in cited_ids]
    cited = [EventRef(event_id=i, event_date=guard.events[i][0]["event_date"], severity=guard.events[i][0]["severity"],
                      description=guard.events[i][0]["description"]) for i in cited_ids if i in guard.events]
    unaddressed = [e for e in g.severe_in_window if e.event_id not in set(cited_ids)]
    return InstrumentGuardOutcome(view, summary, guard.gaps, unaddressed, describe_instrument_change(view, prev), cited,
                                  guard.unavailable, fresh)


def describe_instrument_change(view: InstrumentView | None, prev: InstrumentOutlook | None) -> str:
    if prev is None:
        return "First outlook: there is no earlier outlook to compare with."
    if view is None:
        return f"Compared with {prev.as_of}: no view."
    moved = f" ({view.change.previous_direction} -> {view.direction})" if view.change.kind in ("upgraded", "downgraded") else ""
    return f"Compared with {prev.as_of}: {view.change.kind}{moved}."
