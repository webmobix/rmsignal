"""Output guard of the mandate reconciliation: code, not the model, decides what a status may rest on."""

from dataclasses import dataclass
from datetime import date
from typing import Any

from rm_dashboard.agents.guard import evidence_numbers, unsupported_numbers
from rm_dashboard.domain import Gap, ToolResult
from rm_dashboard.reconciliation.guard import Note

from .contracts import STATUSES, AmbiguousNote, BreachResult, NoteQuote
from .subjects import Breach

WAIVER_CLAIM = "A waiver is claimed in the cited note; it is the RM's statement and is not verified."


@dataclass
class GuardOutcome:
    results: list[BreachResult]
    ambiguous: list[AmbiguousNote]
    gaps: list[Gap]


def _neutral(b: Breach) -> BreachResult:
    return BreachResult(portfolio_id=b.portfolio_id, kind=b.kind, key=b.key, evidence_id=b.evidence_id, description=b.description)


def _bears_on(note: Note, b: Breach) -> bool:
    text = note.quote.lower()
    return any(t in text for t in b.names)


def _ambiguous(note: Note, reason: str) -> AmbiguousNote:
    return AmbiguousNote(note_id=note.note_id, note_date=note.note_date, quote=note.quote, reason=reason)


def guard_results(raw: list[Any], raw_ambiguous: list[Any], breaches: list[Breach], notes: list[Note],
                  evidence: dict[str, ToolResult], as_of: date, *, multi_portfolio: bool) -> GuardOutcome:
    """One result per computed breach, in breach order.

    Results for breaches that were not computed are dropped. A status other than ``no_note`` needs the breach's own
    evidence id, at least one cited note dated on or before ``as_of`` and rationale figures found in that evidence or
    the notes; otherwise it is reset to ``no_note`` with a gap. For a client with several managed portfolios a note
    that does not name the breach's asset class, instrument or portfolio is listed as ambiguous instead.
    """
    gaps: list[Gap] = []
    by_note = {n.note_id: n for n in notes if n.note_date <= as_of}
    by_ref = {b.ref: b for b in breaches}
    chosen: dict[str, dict] = {}
    for item in raw if isinstance(raw, list) else []:
        ref = f"{item.get('portfolio_id')}/{item.get('kind')}/{item.get('key')}" if isinstance(item, dict) else None
        if ref not in by_ref:
            gaps.append(Gap(kind="guard_removed", subject=str(ref)[:60],
                            description=f"result removed: {ref} is not a breach computed for this client"))
        elif ref in chosen:
            gaps.append(Gap(kind="guard_removed", subject=ref, description=f"second result for {ref} removed"))
        else:
            chosen[ref] = item

    ambiguous: dict[str, AmbiguousNote] = {}
    for a in raw_ambiguous if isinstance(raw_ambiguous, list) else []:
        nid = a.get("note_id") if isinstance(a, dict) else None
        if nid in by_note:
            ambiguous.setdefault(nid, _ambiguous(by_note[nid], str(a.get("reason") or "the model could not attribute the note")[:300]))

    results: list[BreachResult] = []

    def reset(b: Breach, why: str) -> None:
        gaps.append(Gap(kind="guard_removed", subject=b.ref, description=f"{b.ref} treated as no_note: {why}"))
        results.append(_neutral(b))

    for b in breaches:
        item = chosen.get(b.ref)
        if item is None:
            results.append(_neutral(b))
            continue
        status = item.get("status")
        if status not in STATUSES:
            reset(b, f"status {status!r} is not valid")
            continue
        if status == "no_note":
            results.append(_neutral(b))
            continue
        ev_id = item.get("evidence_id", b.evidence_id)
        if ev_id != b.evidence_id or b.evidence_id not in evidence:
            reset(b, f"evidence id {ev_id} is not the breach's own evidence")
            continue
        rationale = item.get("rationale")
        if not isinstance(rationale, str) or not rationale.strip():
            reset(b, "no rationale")
            continue
        ids = [i for i in dict.fromkeys(item.get("note_ids") or []) if isinstance(i, str)]
        unknown = [i for i in ids if i not in by_note]
        if unknown:
            gaps.append(Gap(kind="guard_removed", subject=b.ref,
                            description=f"note(s) not of this client or dated after {as_of} ignored for {b.ref}: {', '.join(unknown)}"))
        cited = [by_note[i] for i in ids if i in by_note]
        if multi_portfolio:
            for n in [n for n in cited if not _bears_on(n, b)]:
                ambiguous.setdefault(n.note_id, _ambiguous(
                    n, f"the note does not name the asset class, instrument or portfolio of {b.ref} and the client has several managed portfolios"))
            cited = [n for n in cited if _bears_on(n, b)]
        if not cited:
            reset(b, "no cited note dated on or before as_of that bears on this breach")
            continue
        pool = evidence_numbers(evidence[b.evidence_id].data) | {x for n in cited for x in evidence_numbers(n.quote)}
        bad = unsupported_numbers(rationale, pool)
        if bad:
            reset(b, "figure(s) " + ", ".join(f"{x:g}" for x in bad) + " not present in the cited evidence or notes")
            continue
        waiver = any("waiver" in n.quote.lower() for n in cited)
        text = rationale.strip() + (f" {WAIVER_CLAIM}" if waiver else "")
        results.append(BreachResult(
            portfolio_id=b.portfolio_id, kind=b.kind, key=b.key, evidence_id=b.evidence_id, description=b.description,
            status=status, rationale=text, waiver_claimed=waiver,
            notes=[NoteQuote(note_id=n.note_id, note_date=n.note_date, quote=n.quote) for n in cited]))
    return GuardOutcome(results, sorted(ambiguous.values(), key=lambda a: (a.note_date, a.note_id)), gaps)
