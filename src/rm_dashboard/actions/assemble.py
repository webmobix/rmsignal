"""After the guard: merge duplicates, apply the importance floor, derive horizons, order and rank. All in code."""

from datetime import date

from rm_dashboard.domain import ToolResult
from rm_dashboard.reconciliation import NoteResult
from rm_dashboard.reportsource import FlatFinding

from .contracts import HORIZON_ORDER, IMPORTANCE_ORDER, Action, NotActioned
from .horizon import due_date, horizon_for
from .rubric import apply_floor, floor_for


def _imp(a: Action) -> int:
    return IMPORTANCE_ORDER.index(a.importance)


def merge(actions: list[Action]) -> list[Action]:
    """Actions of the same category that share a source become one: union of sources, highest importance."""
    groups: list[list[Action]] = []
    for a in actions:
        refs = {(s.kind, s.ref) for s in a.sources}
        hit = [g for g in groups if g[0].category == a.category and any((s.kind, s.ref) in refs for x in g for s in x.sources)]
        merged = [a, *[x for g in hit for x in g]]
        groups = [g for g in groups if all(g is not h for h in hit)] + [merged]
    out = []
    for g in groups:
        best = min(g, key=lambda x: (_imp(x), x.title))
        sources, seen = [], set()
        for x in g:
            for s in x.sources:
                if (s.kind, s.ref) not in seen:
                    seen.add((s.kind, s.ref))
                    sources.append(s)
        out.append(best.model_copy(update={"sources": sources}))
    return out


def finalise(actions: list[Action], findings: dict[str, FlatFinding], notes: dict[str, NoteResult],
             evidence: dict[str, ToolResult], as_of: date) -> list[Action]:
    out = []
    for a in merge(actions):
        results = [evidence[i] for i in dict.fromkeys(i for s in a.sources for i in s.evidence_ids) if i in evidence]
        contradicted = any(s.kind == "note" and notes[s.ref].verdict == "contradicted" for s in a.sources if s.ref in notes)
        importance = apply_floor(a.importance, floor_for(a.category, results, contradicted_note=contradicted))
        texts = [findings[s.ref].claim for s in a.sources if s.kind == "finding" and s.ref in findings]
        due = due_date(results, texts, as_of)
        out.append(a.model_copy(update={
            "importance": importance, "importance_raised_from": a.importance if importance != a.importance else None,
            "due_date": due, "horizon": horizon_for(due, as_of)}))
    out.sort(key=lambda a: (_imp(a), HORIZON_ORDER.index(a.horizon), a.due_date or date.max, a.title))
    return [a.model_copy(update={"rank": i}) for i, a in enumerate(out, start=1)]


def not_actioned(actions: list[Action], notes: dict[str, NoteResult]) -> list[NotActioned]:
    used = {s.ref for a in actions for s in a.sources if s.kind == "note"}
    return [NotActioned(note_id=n.note_id, rationale=n.rationale) for n in notes.values()
            if n.verdict == "contradicted" and n.note_id not in used]
