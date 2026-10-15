"""Output guard: every number in agent output must match a number in the evidence it cites."""

import re
from dataclasses import dataclass
from datetime import date
from typing import Any

from rm_dashboard.domain import Finding, Gap
from rm_dashboard.tools import EvidenceStore

RELATIVE_TOLERANCE = 0.005

_SKIP = re.compile(
    r"\d{4}-\d{2}-\d{2}"                      # ISO dates
    r"|ev_[0-9a-f]{8,}"                       # evidence ids
    r"|PERSON_[0-9A-F]{6}"                    # pseudonyms
    r"|\b[A-Z]{1,5}(?:-[A-Z0-9]{1,6})*-\d+\b"  # CL-0001, SYN-EQ-0001, PF-0001, TXN-0013
)
_NUMBER = re.compile(r"(?<![\w.])(-?\d{1,3}(?:,\d{3})+(?:\.\d+)?|-?\d+(?:\.\d+)?)(\s?%|\s?(?:bn|m|k)\b)?", re.I)
_SCALE = {"bn": 1e9, "m": 1e6, "k": 1e3}


@dataclass(frozen=True)
class Num:
    value: float
    decimals: int
    raw: float = 0.0  # as written, before m/bn/k scaling


def extract_numbers(text: str, *, scaled: bool = True) -> list[Num]:
    cleaned = _SKIP.sub(" ", text)
    out = []
    for m in _NUMBER.finditer(cleaned):
        lit = m.group(1).replace(",", "")
        dec = len(lit.split(".")[1]) if "." in lit else 0
        v = abs(float(lit))
        suffix = (m.group(2) or "").strip().lower()
        out.append(Num(v * _SCALE[suffix] if scaled and suffix in _SCALE else v, dec, v))
    return out


def evidence_numbers(data: Any) -> set[float]:
    """Numeric leaves of a result, plus numbers written inside its strings."""
    out: set[float] = set()

    def walk(x: Any) -> None:
        if isinstance(x, bool) or x is None:
            return
        if isinstance(x, (int, float)):
            out.add(abs(float(x)))
        elif isinstance(x, str):
            for n in extract_numbers(x, scaled=False):
                out.add(n.value)
        elif isinstance(x, dict):
            for v in x.values():
                walk(v)
        elif isinstance(x, (list, tuple)):
            for v in x:
                walk(v)

    walk(data)
    return out


def _matches(n: Num, pool: set[float]) -> bool:
    for value, slack in ((n.value, 0.5 * 10 ** (-n.decimals) * (n.value / n.raw if n.raw else 1)), (n.raw, 0.5 * 10 ** (-n.decimals))):
        if any(abs(value - e) <= max(RELATIVE_TOLERANCE * abs(e), slack) for e in pool):
            return True
    return False


def unsupported_numbers(text: str, pool: set[float]) -> list[float]:
    return [n.value for n in extract_numbers(text) if not _matches(n, pool)]


@dataclass
class GuardOutcome:
    findings: list[Finding]
    summary: str
    gaps: list[Gap]


def guard_output(raw_findings: list[Any], summary: str, store: EvidenceStore, as_of: date | None = None) -> GuardOutcome:
    kept: list[Finding] = []
    gaps: list[Gap] = []
    cache: dict[str, set[float]] = {}

    def pool_for(ids: list[str]) -> set[float]:
        out: set[float] = set()
        for i in ids:
            if i not in cache:
                cache[i] = evidence_numbers(store.get(i).data)
            out |= cache[i]
        return out

    for raw in raw_findings:
        claim = raw.get("claim") if isinstance(raw, dict) else None
        ids = raw.get("evidence_ids") if isinstance(raw, dict) else None
        if not isinstance(claim, str) or not isinstance(ids, list) or not ids or not all(isinstance(i, str) for i in ids):
            gaps.append(Gap(kind="guard_removed", description="a finding without a claim or evidence ids was removed"))
            continue
        unknown = [i for i in ids if i not in store]
        if unknown:
            gaps.append(Gap(kind="guard_removed", subject=claim[:80],
                            description=f"finding removed: cites evidence not produced in this run ({', '.join(unknown)})"))
            continue
        stale = sorted({str(store.get(i).as_of) for i in ids if as_of and store.get(i).as_of != as_of})
        if stale:
            gaps.append(Gap(kind="guard_removed", subject=claim[:80],
                            description=f"finding removed: cites evidence from as_of {', '.join(stale)}, not {as_of}"))
            continue
        bad = unsupported_numbers(claim, pool_for(ids))
        if bad:
            gaps.append(Gap(kind="guard_removed", subject=claim[:80],
                            description="finding removed: figure(s) "
                                        + ", ".join(f"{b:g}" for b in bad) + " not present in the cited evidence"))
            continue
        conf = raw.get("confidence", "medium")
        kept.append(Finding(claim=claim, confidence=conf if conf in ("high", "medium", "low") else "medium", evidence_ids=ids))

    if summary:
        everything = pool_for(sorted({i for f in kept for i in f.evidence_ids}))
        bad = unsupported_numbers(summary, everything)
        if bad:
            gaps.append(Gap(kind="guard_removed", subject="summary",
                            description="summary removed: figure(s) " + ", ".join(f"{b:g}" for b in bad) + " not present in the cited evidence"))
            summary = ""
    return GuardOutcome(kept, summary, gaps)
