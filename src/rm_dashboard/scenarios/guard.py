"""Guards for what the scenario agents return: the model proposes moves, mappings and prose; code decides what survives."""

import math
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from rm_dashboard.agents.guard import evidence_numbers, unsupported_numbers
from rm_dashboard.domain import Gap
from rm_dashboard.outlook.contracts import EventRef
from rm_dashboard.outlook.guard import seen_events
from rm_dashboard.tools import EvidenceStore

from .channels import is_single_instrument_key
from .contracts import NOT_ANCHORED, ChannelMove

MOVE_LIMITS = (-100.0, 200.0)
"""A percent move outside this range cannot be a move of a market channel over a few months: the item is removed."""


@dataclass
class VectorGuardInput:
    store: EvidenceStore
    as_of: date
    channels: list[str]
    """The vocabulary: the channels the data supports and the vector is asked to cover."""
    horizon_months: int = 3
    instrument_names: set[str] = field(default_factory=set)
    """Lower-cased names of instruments, so a move keyed by a company name is recognised as a single-instrument move."""


@dataclass
class VectorOutcome:
    channels: list[ChannelMove]
    summary: str
    gaps: list[Gap]


def _gap(description: str, subject: str | None = None) -> Gap:
    return Gap(kind="guard_removed", description=description, subject=subject)


def _number(x: Any) -> float | None:
    if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x):
        return None
    return float(x)


def _text(x: Any) -> str:
    return x.strip() if isinstance(x, str) else ""


def guard_vector(raw: list[Any], summary: str, g: VectorGuardInput) -> VectorOutcome:
    gaps: list[Gap] = []
    kept: dict[str, ChannelMove] = {}
    events = seen_events(g.store)
    cache: dict[str, set[float]] = {}

    def pool_for(ids: list[str]) -> set[float]:
        out: set[float] = set()
        for i in ids:
            if i not in cache:
                cache[i] = evidence_numbers(g.store.get(i).data)
            out |= cache[i]
        return out

    for item in raw:
        if not isinstance(item, dict) or not _text(item.get("channel")):
            gaps.append(_gap("a channel move without a channel name was removed"))
            continue
        ch = _text(item["channel"])
        if is_single_instrument_key(ch, g.instrument_names):
            gaps.append(_gap(f"move keyed to a single instrument ({ch}) removed: a vector holds channel moves only", ch))
            continue
        if ch not in g.channels:
            gaps.append(_gap(f"move for {ch} removed: no holding in the data can reach this channel", ch))
            continue
        if ch in kept:
            gaps.append(_gap(f"second move for {ch} removed", ch))
            continue
        values = [_number(item.get(k)) for k in ("best", "likely", "worst")]
        if any(v is None or not MOVE_LIMITS[0] <= v <= MOVE_LIMITS[1] for v in values):
            gaps.append(_gap(f"move for {ch} removed: best, likely and worst must be percentages between {MOVE_LIMITS[0]:g} and {MOVE_LIMITS[1]:g}", ch))
            continue
        ids = item.get("evidence_ids")
        if not isinstance(ids, list) or not ids or not all(isinstance(i, str) for i in ids):
            gaps.append(_gap(f"move for {ch} removed: it cites no evidence of this run", ch))
            continue
        unknown = [i for i in ids if i not in g.store]
        if unknown:
            gaps.append(_gap(f"move for {ch} removed: cites evidence not produced in this run ({', '.join(unknown)})", ch))
            continue
        stale = sorted({str(g.store.get(i).as_of) for i in ids if g.store.get(i).as_of != g.as_of})
        if stale:
            gaps.append(_gap(f"move for {ch} removed: cites evidence from as_of {', '.join(stale)}, not {g.as_of}", ch))
            continue
        best, likely, worst = values
        ordered = sorted(values)
        if (worst, likely, best) != tuple(ordered):
            worst, likely, best = ordered
            gaps.append(_gap(f"move for {ch} was misordered by the model: its three values were reordered so that worst <= likely <= best", ch))
        text_pool = pool_for(ids) | {abs(best), abs(likely), abs(worst), float(g.horizon_months)}
        rationale, explainer = _text(item.get("rationale")), _text(item.get("explainer"))
        bad = unsupported_numbers(f"{rationale} {explainer}", text_pool)
        if bad:
            gaps.append(_gap(f"move for {ch} removed: figure(s) {', '.join(f'{b:g}' for b in bad)} in its text are neither in the cited evidence "
                             "nor one of its moves", ch))
            continue
        anchored, note = _anchor(item, events, g, ch, gaps)
        if anchored is not None:
            ids = [*ids, *(i for i in events[anchored.event_id][1] if i not in ids)]
        kept[ch] = ChannelMove(channel=ch, best=best, likely=likely, worst=worst, rationale=rationale,
                               explainer=explainer or "Read as the move of this channel over the horizon if the scenario happened.",
                               evidence_ids=ids, anchored_event=anchored, anchor_note=note)
    missing = [c for c in g.channels if c not in kept and c not in {d.subject for d in gaps}]
    if missing:
        gaps.append(Gap(kind="no_data", subject="vector", description="no move for channel(s) " + ", ".join(missing)))
    summary = _text(summary)
    if summary:
        pool = {abs(v) for c in kept.values() for v in (c.best, c.likely, c.worst)} | {float(g.horizon_months)}
        for c in kept.values():
            pool |= pool_for(c.evidence_ids)
        bad = unsupported_numbers(summary, pool)
        if bad:
            gaps.append(_gap("summary removed: figure(s) " + ", ".join(f"{b:g}" for b in bad) + " are neither in the cited evidence nor a move", "summary"))
            summary = ""
    return VectorOutcome(list(kept.values()), summary, gaps)


def _anchor(item: dict, events: dict, g: VectorGuardInput, ch: str, gaps: list[Gap]) -> tuple[EventRef | None, str]:
    """The comparable past event of a move, or the statement that none exists. An event not returned by a tool of this run, or
    dated after ``as_of``, is not an anchor."""
    ref = _text(item.get("anchored_event"))
    if ref:
        found = events.get(ref)
        if found and found[0]["event_date"] <= g.as_of:
            e = found[0]
            return EventRef(event_id=e["event_id"], event_date=e["event_date"], severity=e["severity"], description=e["description"]), ""
        gaps.append(_gap(f"the event {ref} named as the anchor of {ch} was not returned by a tool of this run on or before {g.as_of}: "
                         "the move is not anchored", ch))
    return None, _text(item.get("anchor_note")) or NOT_ANCHORED


# ---- layer B ------------------------------------------------------------------------------------
def guard_mappings(raw: Any, ambiguous: dict[str, str], vector_channels: list[str]) -> tuple[dict[str, list[tuple[str, str]]], list[dict], list[Gap]]:
    """(accepted instrument -> [(channel, reason)], every proposal with its verdict, gaps).

    A proposal is accepted only for a holding code could not map, and only with channels of the vector that are not fx channels.
    Anything else leaves the holding untouched with a gap."""
    accepted: dict[str, list[tuple[str, str]]] = {}
    verdicts: list[dict] = []
    gaps: list[Gap] = []
    for item in raw if isinstance(raw, list) else []:
        iid = _text(item.get("instrument_id")) if isinstance(item, dict) else ""
        chans = item.get("channels") if isinstance(item, dict) else None
        reason = _text(item.get("reason")) if isinstance(item, dict) else ""
        if iid not in ambiguous:
            if iid:
                gaps.append(_gap(f"mapping proposed for {iid} dropped: it is not a holding left unmapped by the rules", iid))
            continue
        if not isinstance(chans, list) or not chans or not all(isinstance(c, str) for c in chans):
            verdicts.append({"instrument_id": iid, "channels": [], "reason": reason, "accepted": False})
            gaps.append(_gap(f"mapping proposed for {iid} dropped: no channels given; the holding stays untouched", iid))
            continue
        outside = [c for c in chans if c not in vector_channels or c.startswith("fx_")]
        if outside or not reason:
            verdicts.append({"instrument_id": iid, "channels": chans, "reason": reason, "accepted": False})
            why = (f"channel(s) {', '.join(outside)} are not market or overlay channels of the vector" if outside
                   else "it gave no reason")
            gaps.append(_gap(f"mapping proposed for {iid} dropped: {why}; the holding stays untouched", iid))
            continue
        accepted[iid] = [(c, reason) for c in dict.fromkeys(chans)]
        verdicts.append({"instrument_id": iid, "channels": list(dict.fromkeys(chans)), "reason": reason, "accepted": True})
    return accepted, verdicts, gaps
