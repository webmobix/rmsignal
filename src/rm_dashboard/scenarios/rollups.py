"""Client and RM-book roll-ups of portfolio impacts: totals, rankings and crossings are sums and sorts in code."""

from datetime import date

from rm_dashboard.domain import Gap

from .contracts import (
    CASES, CaseImpact, ClientLine, ClientRollup, Coverage, Crossing, PortfolioImpact, PortfolioLine, RMRollup, ScenarioRecord, Totals,
)
from .figures import fmt_pct, fmt_usd
from .impact import explainers


def usable(impact: PortfolioImpact | None) -> bool:
    return impact is not None and impact.status != "insufficient_data" and bool(impact.cases)


def _totals(before: float, delta: float) -> Totals:
    return Totals(before_usd=round(before, 2), after_usd=round(before + delta, 2), delta_usd=round(delta, 2),
                  delta_pct=round(delta / before * 100, 4) if before else 0.0)


def build_client_rollup(scenario: ScenarioRecord, as_of: date, client_id: str, impacts: dict[str, PortfolioImpact | None],
                        names: dict[str, str] | None = None, *, inputs_hash: str = "", model: str = "") -> ClientRollup:
    """``impacts`` maps every portfolio id of the client to its impact, or None when none exists."""
    names = names or {}
    done = {pid: i for pid, i in impacts.items() if usable(i)}
    missing = sorted(pid for pid in impacts if pid not in done)
    cov = Coverage(computed=len(done), total=len(impacts), missing=missing)
    base = dict(scenario_id=scenario.scenario_id, client_id=client_id, as_of=as_of, horizon_months=scenario.horizon_months,
                coverage=cov, inputs_hash=inputs_hash, model=model)
    if not done:
        gaps = [Gap(kind="no_data", subject=client_id, description="no portfolio of this client has a computed result: " + (", ".join(missing) or "no portfolios"))]
        return ClientRollup(status="insufficient_data", gaps=gaps, **base)
    before = sum(i.before_usd for i in done.values())
    cases: dict[str, CaseImpact] = {}
    for k in CASES:
        t = _totals(before, sum(i.cases[k].delta_usd for i in done.values()))
        cases[k] = CaseImpact(**t.model_dump(), bands=[b for i in done.values() for b in i.cases[k].bands],
                              collateral=[c for i in done.values() for c in i.cases[k].collateral])
    positions = [p for i in done.values() for p in i.positions]
    reached = sum(p.value_usd for p in positions if p.mapping != "untouched")
    untouched = sum(i.untouched_count for i in done.values())
    reached_pct = round(reached / before * 100, 2) if before else 0.0
    gaps = []
    if missing:
        gaps.append(Gap(kind="no_data", subject=client_id, description=f"{len(missing)} of {len(impacts)} portfolio(s) have no computed result and are "
                                                                        f"not in these totals: {', '.join(missing)}"))
    lines = [PortfolioLine(portfolio_id=pid, name=names.get(pid, ""), before_usd=i.before_usd,
                           cases={k: Totals(**{f: getattr(i.cases[k], f) for f in Totals.model_fields}) for k in CASES}) for pid, i in sorted(done.items())]
    partial = bool(gaps) or any(i.status != "complete" for i in done.values())
    rollup = ClientRollup(status="partial" if partial else "complete", before_usd=round(before, 2), cases=cases, reached_pct=reached_pct,
                          untouched_count=untouched, positions=positions, portfolios=lines, gaps=gaps,
                          explainers=explainers(scenario.horizon_months, reached_pct, untouched), **base)
    return rollup.model_copy(update={"summary": built_client_summary(scenario, rollup)})


def built_client_summary(scenario: ScenarioRecord, r: ClientRollup) -> str:
    c = r.cases
    parts = [f"Under {scenario.name}, over {r.horizon_months} months, the client's likely change across {r.coverage.computed} portfolio(s) is "
             f"{fmt_pct(c['likely'].delta_pct)} ({fmt_usd(c['likely'].delta_usd)}), from {fmt_pct(c['worst'].delta_pct)} "
             f"({fmt_usd(c['worst'].delta_usd)}) in the worst case to {fmt_pct(c['best'].delta_pct)} ({fmt_usd(c['best'].delta_usd)}) in the best."]
    if r.portfolios:
        hit = min(r.portfolios, key=lambda p: p.cases["worst"].delta_usd)
        parts.append(f"The portfolio most affected in the worst case is {hit.portfolio_id} ({fmt_usd(hit.cases['worst'].delta_usd)}).")
    if r.coverage.missing:
        parts.append(f"{len(r.coverage.missing)} portfolio(s) are not covered.")
    parts.append("Cases are conditional on the scenario, not probabilities.")
    return " ".join(parts)


def client_figures(r: ClientRollup) -> dict:
    """Every value agent prose about this client may quote."""
    return {"horizon_months": r.horizon_months, "before_usd": r.before_usd, "reached_pct": r.reached_pct, "untouched_count": r.untouched_count,
            "coverage": r.coverage.model_dump(),
            "cases": {k: {"after_usd": v.after_usd, "delta_usd": v.delta_usd, "delta_pct": v.delta_pct, "bands_crossed": len(v.bands),
                          "facilities_breached": sum(e.breaches for e in v.collateral)} for k, v in r.cases.items()},
            "portfolios": [{"portfolio_id": p.portfolio_id, "before_usd": p.before_usd,
                            "cases": {k: t.model_dump() for k, t in p.cases.items()}} for p in r.portfolios]}


# ---- RM book --------------------------------------------------------------------------------------
def _line(r: ClientRollup) -> ClientLine:
    return ClientLine(client_id=r.client_id, before_usd=r.before_usd,
                      cases={k: Totals(**{f: getattr(r.cases[k], f) for f in Totals.model_fields}) for k in CASES})


def _crossings(r: ClientRollup) -> list[Crossing]:
    out = []
    for k in CASES:
        for b in r.cases[k].bands:
            word = "leaves" if b.crosses == "out" else "returns to"
            out.append(Crossing(client_id=r.client_id, portfolio_id=b.portfolio, case=k, kind="band", label=b.asset_class,
                                detail=f"{b.asset_class} {word} its band: {b.before_pct:.1f}% to {b.after_pct:.1f}% (band {b.band_min_pct:g}-{b.band_max_pct:g}%)"))
        for c in r.cases[k].collateral:
            if c.breaches:
                short = f", shortfall {fmt_usd(c.shortfall_usd)}" if c.shortfall_usd else ""
                out.append(Crossing(client_id=r.client_id, portfolio_id=c.portfolio, case=k, kind="ltv", label=c.facility,
                                    detail=f"{c.facility} LTV {c.ltv_before_pct:.1f}% to {c.ltv_after_pct:.1f}% against a trigger of {c.trigger_pct:g}%{short}"))
    return out


def build_rm_rollup(scenario: ScenarioRecord, as_of: date, rm_id: str | None, clients: dict[str, ClientRollup | None], *,
                    inputs_hash: str = "", model: str = "") -> RMRollup:
    """``clients`` maps every client of the book to its roll-up, or None when none exists."""
    done = {cid: r for cid, r in clients.items() if r is not None and r.status != "insufficient_data" and r.cases}
    missing = sorted(cid for cid in clients if cid not in done)
    cov = Coverage(computed=len(done), total=len(clients), missing=missing)
    base = dict(scenario_id=scenario.scenario_id, as_of=as_of, rm_id=rm_id, horizon_months=scenario.horizon_months, coverage=cov,
                inputs_hash=inputs_hash, model=model)
    if not done:
        return RMRollup(status="insufficient_data", gaps=[Gap(kind="no_data", subject=scenario.scenario_id, description="no client has a computed result")], **base)
    before = sum(r.before_usd for r in done.values())
    cases = {k: _totals(before, sum(r.cases[k].delta_usd for r in done.values())) for k in CASES}
    most_hit = sorted((_line(r) for r in done.values()), key=lambda c: (c.cases["worst"].delta_usd, c.client_id))
    benefit = sorted((_line(r) for r in done.values() if r.cases["likely"].delta_usd > 0), key=lambda c: (-c.cases["likely"].delta_usd, c.client_id))
    crossings = [x for cid in sorted(done) for x in _crossings(done[cid])]
    gaps = []
    if missing:
        gaps.append(Gap(kind="no_data", subject=scenario.scenario_id, description=f"{cov.computed} of {cov.total} clients covered; not in these totals: "
                                                                                    + ", ".join(missing)))
    partial = bool(gaps) or any(r.status != "complete" for r in done.values())
    rollup = RMRollup(status="partial" if partial else "complete", before_usd=round(before, 2), cases=cases, most_hit=most_hit, beneficiaries=benefit,
                      crossings=crossings, gaps=gaps, **base)
    return rollup.model_copy(update={"summary": built_rm_summary(scenario, rollup)})


def built_rm_summary(scenario: ScenarioRecord, r: RMRollup) -> str:
    c = r.cases
    parts = [f"Under {scenario.name}, over {r.horizon_months} months, the book's likely change is {fmt_pct(c['likely'].delta_pct)} "
             f"({fmt_usd(c['likely'].delta_usd)}), from {fmt_pct(c['worst'].delta_pct)} ({fmt_usd(c['worst'].delta_usd)}) in the worst case to "
             f"{fmt_pct(c['best'].delta_pct)} ({fmt_usd(c['best'].delta_usd)}) in the best, across {r.coverage.computed} of {r.coverage.total} clients."]
    if r.most_hit and r.most_hit[0].cases["worst"].delta_usd < 0:
        top = r.most_hit[0]
        parts.append(f"The most affected client in the worst case is [[{top.client_id}]] ({fmt_usd(top.cases['worst'].delta_usd)}).")
    worst = [x for x in r.crossings if x.case == "worst"]
    if worst:
        parts.append(f"In the worst case {len(worst)} mandate band or facility trigger crossing(s) are listed.")
    parts.append("Cases are conditional on the scenario, not probabilities.")
    return " ".join(parts)


def rm_figures(r: RMRollup) -> dict:
    """Every value agent prose about the book may quote."""
    return {"horizon_months": r.horizon_months, "before_usd": r.before_usd, "coverage": r.coverage.model_dump(),
            "cases": {k: t.model_dump() for k, t in r.cases.items()},
            "most_hit": [{"client_id": c.client_id, "worst": c.cases["worst"].model_dump()} for c in r.most_hit[:5]],
            "beneficiaries": [{"client_id": c.client_id, "likely": c.cases["likely"].model_dump()} for c in r.beneficiaries[:5]],
            "crossings": {k: sum(1 for x in r.crossings if x.case == k) for k in CASES}}
