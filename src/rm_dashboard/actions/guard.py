"""Output guard of the client actions: the model proposes, code checks every claim against this client's content."""

from dataclasses import dataclass
from typing import Any

from rm_dashboard.agents.guard import evidence_numbers, unsupported_numbers
from rm_dashboard.domain import Gap
from rm_dashboard.reconciliation import NoteResult
from rm_dashboard.reportsource import FlatFinding

from .contracts import CATEGORIES, IMPORTANCE_ORDER, Action, SourceRef


@dataclass
class GuardOutcome:
    actions: list[Action]
    gaps: list[Gap]


def _removed(subject: str, why: str) -> Gap:
    return Gap(kind="guard_removed", subject=subject[:80], description=f"action removed: {why}")


def guard_actions(raw: Any, findings: dict[str, FlatFinding], notes: dict[str, NoteResult]) -> GuardOutcome:
    """Keep actions with a valid category and importance, references that exist for this client only, and figures
    that appear in the content they link to. Evidence ids are copied from that content, never from the model."""
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
        unknown = [r for r in refs if r not in findings and r not in notes]
        if not refs or unknown:
            gaps.append(_removed(label, "it links no source" if not refs else
                                 f"unknown source reference(s) for this client: {', '.join(unknown)}"))
            continue
        linked = [findings[r].claim for r in refs if r in findings]
        linked += [s for r in refs if r in notes for s in (notes[r].rationale, notes[r].note_quote)]
        bad = unsupported_numbers(" ".join(text), evidence_numbers(linked))
        if bad:
            gaps.append(_removed(label, "figure(s) " + ", ".join(f"{b:g}" for b in bad) + " not present in the linked content"))
            continue
        sources = [SourceRef(kind="finding", ref=r, report_path=findings[r].report_path, evidence_ids=list(findings[r].evidence_ids))
                   if r in findings else SourceRef(kind="note", ref=r, evidence_ids=list(notes[r].evidence_ids)) for r in refs]
        kept.append(Action(title=text[0].strip(), what=text[1].strip(), why=text[2].strip(), category=item["category"],
                           importance=item["importance"], sources=sources))
    return GuardOutcome(kept, gaps)
