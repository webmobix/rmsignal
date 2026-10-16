"""Breach subjects: the computed breaches in a client's persisted evidence, and nothing else."""

import re
from dataclasses import dataclass, field

from rm_dashboard.domain import Gap, ToolResult

from .contracts import BreachKind

CUSTODY = "Custody"
GENERIC_WORDS = frozenset({"fund", "index", "group", "global", "equity", "bond", "trust", "limited", "income", "core"})


@dataclass(frozen=True)
class Breach:
    portfolio_id: str
    kind: BreachKind
    key: str
    evidence_id: str
    description: str
    portfolio_name: str = ""
    names: tuple[str, ...] = field(default_factory=tuple)
    """Words that tie a note to this breach: asset class, instrument and portfolio names."""

    @property
    def ref(self) -> str:
        return f"{self.portfolio_id}/{self.kind}/{self.key}"


def _tokens(name: str) -> list[str]:
    return [t for t in re.findall(r"[a-z]{4,}", name.lower()) if t not in GENERIC_WORDS]


def _class_terms(asset_class: str, positions: list[dict]) -> tuple[str, ...]:
    terms = {asset_class.lower(), asset_class.lower()[:6]}
    for p in positions:
        if p.get("asset_class") == asset_class:
            terms.add(p["instrument_name"].lower())
            terms.update(_tokens(p["instrument_name"]))
    return tuple(sorted(t for t in terms if t))


def _by_portfolio(evidence: dict[str, ToolResult], tool: str) -> dict[str, ToolResult]:
    out: dict[str, ToolResult] = {}
    for r in evidence.values():
        if r.computation.tool == tool and r.status == "ok" and isinstance(r.data, (dict, list)):
            pid = r.data.get("portfolio_id") if isinstance(r.data, dict) else r.computation.parameters.get("portfolio_id")
            if pid:
                out.setdefault(pid, r)
    return out


def build_subjects(evidence: dict[str, ToolResult]) -> tuple[list[Breach], list[Gap], int]:
    """(breaches, gaps, managed portfolio count). Custody portfolios are skipped; a missing check is a gap."""
    listed = next((r for r in evidence.values() if r.computation.tool == "portfolios.list" and isinstance(r.data, list)), None)
    gets = _by_portfolio(evidence, "portfolios.get")
    drift = _by_portfolio(evidence, "analytics.mandate_drift")
    excl = _by_portfolio(evidence, "analytics.exclusion_breaches")
    positions = _by_portfolio(evidence, "positions.list")
    info: dict[str, dict] = {}
    for p in (listed.data if listed else []):
        info[p["portfolio_id"]] = p
    for pid, r in gets.items():
        info.setdefault(pid, r.data)
    for pid in drift:
        info.setdefault(pid, {"portfolio_id": pid})
    breaches: list[Breach] = []
    gaps: list[Gap] = []
    managed = 0
    for pid in sorted(info):
        meta = info[pid]
        model = meta.get("service_model") or (drift[pid].data.get("service_model") if pid in drift else None)
        if model == CUSTODY or (pid in drift and drift[pid].data.get("applicable") is False):
            continue
        managed += 1
        name = meta.get("portfolio_name", "")
        pos = (positions[pid].data if pid in positions and isinstance(positions[pid].data, list) else [])
        if pid not in drift:
            gaps.append(Gap(kind="no_data", subject=pid, description=f"no persisted mandate check (analytics.mandate_drift) for {pid}"))
        else:
            d = drift[pid].data
            for b in d.get("breaches") or []:
                word, lim = ("maximum", b["max_pct"]) if b["breach"] == "above_max" else ("minimum", b["min_pct"])
                breaches.append(Breach(
                    pid, "band", b["asset_class"], drift[pid].evidence_id,
                    f"{b['asset_class']} weight is {b['weight_pct']:.2f}% against a {word} of {lim:.2f}% "
                    f"(gap {abs(b['gap_pp']):.2f} percentage points)", name,
                    _class_terms(b["asset_class"], pos) + ((name.lower(),) if name else ())))
            for b in d.get("single_position_breaches") or []:
                breaches.append(Breach(
                    pid, "position", b["instrument_id"], drift[pid].evidence_id,
                    f"{b['instrument_name']} ({b['instrument_id']}) is {b['weight_pct']:.2f}% of the portfolio "
                    f"against a single-position limit of {b['limit_pct']:.2f}%", name,
                    (b["instrument_name"].lower(), *_tokens(b["instrument_name"])) + ((name.lower(),) if name else ())))
        if pid not in excl:
            gaps.append(Gap(kind="no_data", subject=pid, description=f"no persisted exclusion check (analytics.exclusion_breaches) for {pid}"))
        else:
            for b in excl[pid].data.get("breaches") or []:
                key = b["instrument_id"] + (f"@{b['via_instrument_id']}" if b["held"] == "look_through" else "")
                how = f"through {b['via_instrument_name']}" if b["held"] == "look_through" else "directly"
                breaches.append(Breach(
                    pid, "exclusion", key, excl[pid].evidence_id,
                    f"Excluded holding {b['instrument_name']} ({b['instrument_id']}) is {b['weight_pct']:.2f}% of the portfolio, "
                    f"held {how}, against the mandate's binding exclusions", name,
                    (b["instrument_name"].lower(), *_tokens(b["instrument_name"]), "exclu", "sustainab") + ((name.lower(),) if name else ())))
    return breaches, gaps, managed
