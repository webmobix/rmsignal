"""Output guard of the client actions: the model proposes, code checks every claim against this client's content."""

from dataclasses import dataclass
from typing import Any

from rm_dashboard.agents.guard import evidence_numbers, unsupported_numbers
from rm_dashboard.domain import Gap
from rm_dashboard.mandate_reconciliation import BreachResult
from rm_dashboard.reconciliation import NoteResult
from rm_dashboard.reportsource import FlatFinding

from .contracts import CATEGORIES, IMPORTANCE_ORDER, Action, SourceRef


@dataclass
class GuardOutcome:
    actions: list[Action]
    gaps: list[Gap]


def _removed(subject: str, why: str) -> Gap:
    return Gap(kind="guard_removed", subject=subject[:80], description=f"action removed: {why}")


def _source(ref: str, findings: dict[str, FlatFinding], notes: dict[str, NoteResult], mandate: dict[str, BreachResult]) -> SourceRef:
    if ref in findings:
        return SourceRef(kind="finding", ref=ref, report_path=findings[ref].report_path, evidence_ids=list(findings[ref].evidence_ids))
    if ref in notes:
        return SourceRef(kind="note", ref=ref, evidence_ids=list(notes[ref].evidence_ids))
    m = mandate[ref]
    return SourceRef(kind="mandate", ref=ref, evidence_ids=[m.evidence_id], mandate_status=m.status, breach_kind=m.kind,
                     note_ids=m.note_ids)


def guard_actions(raw: Any, findings: dict[str, FlatFinding], notes: dict[str, NoteResult],
                  mandate: dict[str, BreachResult] | None = None) -> GuardOutcome:
    """Keep actions with a valid category and importance, references that exist for this client only, and figures
    that appear in the content they link to. Evidence ids are copied from that content, never from the model."""
    mandate = mandate or {}
    kept: list[Action] = []
    gaps: list[Gap] = []
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, dict):
            gaps.append(_removed("?", "not an object"))
            continue
        title = item.get("title")
        label = title if isinstance(title, str) else "?"
        text = [item.get(k) for k in ("title", "what", "why")]
        if not all(isinstance(t, str) and t.strip() for t in text):
            gaps.append(_removed(label, "title, what and why are required"))
            continue
        if item.get("category") not in CATEGORIES:
            gaps.append(_removed(label, f"category {item.get('category')!r} is not one of the allowed categories"))
            continue
        if item.get("importance") not in IMPORTANCE_ORDER:
            gaps.append(_removed(label, f"importance {item.get('importance')!r} is not valid"))
            continue
        refs = [r for r in dict.fromkeys(item.get("refs") or []) if isinstance(r, str)]
        unknown = [r for r in refs if r not in findings and r not in notes and r not in mandate]
        if not refs or unknown:
            gaps.append(_removed(label, "it links no source" if not refs else
                                 f"unknown source reference(s) for this client: {', '.join(unknown)}"))
            continue
        linked = [findings[r].claim for r in refs if r in findings]
        linked += [s for r in refs if r in notes for s in (notes[r].rationale, notes[r].note_quote)]
        linked += [s for r in refs if r in mandate for s in (mandate[r].description, mandate[r].rationale, *(n.quote for n in mandate[r].notes))]
        bad = unsupported_numbers(" ".join(text), evidence_numbers(linked))
        if bad:
            gaps.append(_removed(label, "figure(s) " + ", ".join(f"{b:g}" for b in bad) + " not present in the linked content"))
            continue
        sources = [_source(r, findings, notes, mandate) for r in refs]
        kept.append(Action(title=text[0].strip(), what=text[1].strip(), why=text[2].strip(), category=item["category"],
                           importance=item["importance"], sources=sources))
    return GuardOutcome(kept, gaps)
