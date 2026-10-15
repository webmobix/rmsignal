"""Output guard of the note reconciliation: code, not the model, decides what a verdict may rest on."""

from dataclasses import dataclass
from datetime import date
from typing import Any

from rm_dashboard.agents.guard import evidence_numbers, unsupported_numbers
from rm_dashboard.domain import Gap, ToolResult
from rm_dashboard.reportsource import FlatFinding

from .contracts import NoteResult

VERDICTS = ("consistent", "contradicted", "unverifiable")
SUPPORTED = ("consistent", "contradicted")
NO_RESULT = "No assessment was returned for this note; it is treated as unverifiable."
REMOVED = "The assessment of this note was removed by the output guard; it is treated as unverifiable."


@dataclass(frozen=True)
class Note:
    note_id: str
    note_date: date
    quote: str


@dataclass
class GuardOutcome:
    results: list[NoteResult]
    gaps: list[Gap]


def _unverifiable(note: Note, rationale: str) -> NoteResult:
    return NoteResult(note_id=note.note_id, note_date=note.note_date, note_quote=note.quote,
                      verdict="unverifiable", rationale=rationale)


def guard_results(raw: list[Any], notes: list[Note], findings: dict[str, FlatFinding],
                  evidence: dict[str, ToolResult], as_of: date) -> GuardOutcome:
    """One result per note dated on or before ``as_of``, in note order.

    Unknown or later notes are dropped; refs that do not resolve are ignored; a supported verdict without
    resolvable evidence becomes ``unverifiable``; a rationale with a figure found neither in the cited
    evidence nor in the note replaces the assessment by ``unverifiable``.
    """
    gaps: list[Gap] = []
    by_note = {n.note_id: n for n in notes if n.note_date <= as_of}
    chosen: dict[str, dict] = {}
    for item in raw if isinstance(raw, list) else []:
        nid = item.get("note_id") if isinstance(item, dict) else None
        if nid not in by_note:
            gaps.append(Gap(kind="guard_removed", subject=str(nid)[:40],
                            description=f"result removed: note {nid} is not a note of this client dated on or before {as_of}"))
        elif nid in chosen:
            gaps.append(Gap(kind="guard_removed", subject=nid, description=f"second result for note {nid} removed"))
        else:
            chosen[nid] = item

    results: list[NoteResult] = []
    for note in sorted(by_note.values(), key=lambda n: (n.note_date, n.note_id)):
        item = chosen.get(note.note_id)
        if item is None:
            gaps.append(Gap(kind="other", subject=note.note_id, description=f"no result returned for note {note.note_id}"))
            results.append(_unverifiable(note, NO_RESULT))
            continue
        rationale = item.get("rationale")
        verdict = item.get("verdict")
        if not isinstance(rationale, str) or not rationale.strip():
            gaps.append(Gap(kind="guard_removed", subject=note.note_id, description=f"result for {note.note_id} removed: no rationale"))
            results.append(_unverifiable(note, REMOVED))
            continue
        if verdict not in VERDICTS:
            gaps.append(Gap(kind="guard_removed", subject=note.note_id,
                            description=f"verdict {verdict!r} for {note.note_id} is not valid; treated as unverifiable"))
            verdict = "unverifiable"
        refs = [r for r in dict.fromkeys(item.get("finding_refs") or []) if isinstance(r, str)]
        unknown = [r for r in refs if r not in findings]
        if unknown:
            gaps.append(Gap(kind="guard_removed", subject=note.note_id,
                            description=f"unknown finding reference(s) ignored for {note.note_id}: {', '.join(unknown)}"))
        refs = [r for r in refs if r in findings]
        ids = [i for i in dict.fromkeys(i for r in refs for i in findings[r].evidence_ids)]
        known = [i for i in ids if i in evidence]
        missing = [i for i in ids if i not in evidence]
        if missing:
            gaps.append(Gap(kind="guard_removed", subject=note.note_id,
                            description=f"evidence not in the client's persisted evidence ignored for {note.note_id}: {', '.join(missing)}"))
        pool = {n for i in known for n in evidence_numbers(evidence[i].data)} | evidence_numbers(note.quote)
        bad = unsupported_numbers(rationale, pool)
        if bad:
            gaps.append(Gap(kind="guard_removed", subject=note.note_id,
                            description=f"result for {note.note_id} removed: figure(s) " + ", ".join(f"{b:g}" for b in bad)
                                        + " not present in the cited evidence or the note"))
            results.append(_unverifiable(note, REMOVED))
            continue
        if verdict in SUPPORTED and not known:
            gaps.append(Gap(kind="guard_removed", subject=note.note_id,
                            description=f"verdict {verdict} for {note.note_id} cites no evidence; treated as unverifiable"))
            verdict = "unverifiable"
        results.append(NoteResult(note_id=note.note_id, note_date=note.note_date, note_quote=note.quote, verdict=verdict,
                                  rationale=rationale.strip(), finding_refs=refs, evidence_ids=known))
    return GuardOutcome(results, gaps)
