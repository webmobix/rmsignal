"""The impact of a shock vector on one portfolio, computed by code from the holdings and the vector.

Per position and case: move = sum over the channels that reach it of (share of the holding reached x the channel's value for the
case); change in USD = position USD value x move. Cases bracket rather than estimate: all-best, all-likely and all-worst channel
values are applied together, which ignores diversification between channels. Mandate bands are measured on base-currency values
and the Lombard LTV in the facility currency; the portfolio's base currency is not itself shocked.
"""

from datetime import date

from rm_dashboard.analytics.credit import ltv
from rm_dashboard.domain import Gap

from .contracts import (
    CASES, AgentMapping, BandCrossing, CaseImpact, CasePoint, CollateralEffect, PortfolioImpact, PositionChannel, PositionImpact,
    ScenarioRecord, ShockVector,
)
from .figures import fmt_pct, fmt_usd
from .mapping import Mapped, PortfolioInputs, ambiguous_holdings, map_holdings

CUSTODY = "Custody"
VALUE = "market_value_usd"
BASE = "market_value_base"


def _unrelated_channels(vector: ShockVector, mapped: list[Mapped]) -> list[str]:
    have = vector.by_channel()
    return sorted({u.channel for m in mapped for u in m.channels if u.channel not in have})


def _position(portfolio_id: str, m: Mapped, vector: ShockVector, total_usd: float) -> PositionImpact:
    h = m.holding
    have = vector.by_channel()
    uses = [u for u in m.channels if u.channel in have]
    channels = [PositionChannel(channel=u.channel, best_pct=u.weight * have[u.channel].best, likely_pct=u.weight * have[u.channel].likely,
                                worst_pct=u.weight * have[u.channel].worst, why=u.why, agent_assigned=u.agent_assigned) for u in uses]
    value = float(h[VALUE])
    move = {k: sum(getattr(c, f"{k}_pct") for c in channels) for k in CASES}
    mapping, reason = m.mapping, m.reason
    if not uses and m.mapping != "untouched":
        missing = ", ".join(sorted({u.channel for u in m.channels}))
        mapping, reason = "untouched", f"the vector has no move for {missing or 'its channels'}"
    return PositionImpact(
        portfolio_id=portfolio_id, instrument_id=h["instrument_id"], instrument=h["instrument_name"], asset_class=h["asset_class"],
        value_usd=round(value, 2), weight_pct=round(value / total_usd * 100, 4) if total_usd else 0.0, mapping=mapping, reason=reason,
        moves={k: CasePoint(move_pct=round(move[k], 4), delta_usd=round(value * move[k] / 100, 2)) for k in CASES}, channels=channels)


def _bands(inputs: PortfolioInputs, positions: list[PositionImpact], case: str) -> list[BandCrossing]:
    """Asset-class weights before and after, on base-currency values, against the mandate band: crossings only."""
    if inputs.portfolio.get("service_model") == CUSTODY or not inputs.bands:
        return []
    by_id = {p.instrument_id: p for p in positions}
    before: dict[str, float] = {}
    after: dict[str, float] = {}
    for h in inputs.holdings:
        v = float(h[BASE])
        m = by_id[h["instrument_id"]].moves[case].move_pct
        before[h["asset_class"]] = before.get(h["asset_class"], 0.0) + v
        after[h["asset_class"]] = after.get(h["asset_class"], 0.0) + v * (1 + m / 100)
    tb, ta = sum(before.values()), sum(after.values())
    if tb <= 0 or ta <= 0:
        return []
    out = []
    for b in inputs.bands:
        w0, w1 = before.get(b["asset_class"], 0.0) / tb * 100, after.get(b["asset_class"], 0.0) / ta * 100
        out0, out1 = not b["min_pct"] <= w0 <= b["max_pct"], not b["min_pct"] <= w1 <= b["max_pct"]
        if out0 != out1:
            out.append(BandCrossing(asset_class=b["asset_class"], portfolio=inputs.portfolio["portfolio_id"], before_pct=round(w0, 2),
                                    after_pct=round(w1, 2), band_min_pct=b["min_pct"], band_max_pct=b["max_pct"],
                                    crosses="out" if out1 else "in"))
    return out


def _collateral(inputs: PortfolioInputs, positions: list[PositionImpact], case: str, gaps: list[Gap]) -> list[CollateralEffect]:
    """LTV before and after: collateral and lending value scale with the position moves; breach and cure by the credit analytics."""
    by_id = {p.instrument_id: p for p in positions}
    out = []
    for f in inputs.facilities:
        mv = [(float(h[BASE]), float(h.get("lending_value_base") or 0.0), by_id[h["instrument_id"]].moves[case].move_pct / 100)
              for h in inputs.holdings]
        base, lend = sum(v for v, _, _ in mv), sum(lv for _, lv, _ in mv)
        if base <= 0:
            continue
        coll_ratio = sum(v * (1 + m) for v, _, m in mv) / base
        lend_ratio = sum(lv * (1 + m) for _, lv, m in mv) / lend if lend > 0 else coll_ratio
        before = ltv(drawn=f["drawn"], lending_value=f["lending_value"], collateral_value=f["collateral_market_value"],
                     trigger_pct=f["margin_call_ltv_pct"])
        after = ltv(drawn=f["drawn"], lending_value=f["lending_value"] * lend_ratio,
                    collateral_value=f["collateral_market_value"] * coll_ratio, trigger_pct=f["margin_call_ltv_pct"])
        if before.status != "ok":
            gaps.append(Gap(kind="no_data", subject=f["facility_id"], description=f"{f['facility_id']}: LTV not computable ({before.reason})"))
            continue
        d = after.data if after.status == "ok" else None
        shortfall = None
        if d and d["breached"]:
            usd = sum(float(h[VALUE]) for h in inputs.holdings)
            if f["facility_ccy"] == inputs.portfolio.get("base_currency") and base > 0:
                shortfall = round(d["cure_sale_required"] * usd / base, 2)
        out.append(CollateralEffect(facility=f["facility_id"], portfolio=inputs.portfolio["portfolio_id"], ltv_before_pct=round(before.data["ltv_pct"], 2),
                                    ltv_after_pct=round(d["ltv_pct"], 2) if d else None, trigger_pct=f["margin_call_ltv_pct"],
                                    breaches=bool(d and d["breached"]), shortfall_usd=shortfall))
        if d and d["breached"] and shortfall is None:
            gaps.append(Gap(kind="other", subject=f["facility_id"], description=f"{f['facility_id']} is in {f['facility_ccy']} but the portfolio is in "
                            f"{inputs.portfolio.get('base_currency')}: the shortfall in USD cannot be stated"))
    return out


def explainers(h: int, reached_pct: float, untouched: int) -> dict[str, str]:
    """How each headline figure is derived. Code-built: it states the method, never a result."""
    common = (f"Over {h} months, each channel's move is applied to the holdings it reaches (overlay channels such as a sector or credit "
              "spreads are an excess over the market channel and add to it), position by position. Cases are conditional on the "
              "scenario and are not probabilities.")
    return {
        "likely": f"The likely case applies every channel's likely move together. {common}",
        "best": "The best case applies every channel's best move together. It ignores diversification between channels, so it brackets "
                f"the likely case rather than estimating a tail. {common}",
        "worst": "The worst case applies every channel's worst move together. It ignores diversification between channels, so it brackets "
                 f"the likely case rather than estimating a tail. {common}",
        "reached": f"{reached_pct:.1f}% of the portfolio's USD value sits in holdings that at least one channel of the scenario reaches; "
                   f"{untouched} holding(s) are untouched and are counted at a move of zero.",
        "bands": "Asset-class weights before and after the case, on base-currency values, against the mandate band; only a class that "
                 "moves into or out of its band is listed.",
        "collateral": "Collateral and lending value of the Lombard facility move with the pledged positions; LTV is recomputed on the "
                      "drawn amount. Shortfall is the collateral to sell to restore the trigger.",
    }


def built_summary(scenario: ScenarioRecord, impact: PortfolioImpact) -> str:
    """The summary in code: used when no agent prose passes the figure check."""
    c = impact.cases
    parts = [f"Under {scenario.name}, over {impact.horizon_months} months, the portfolio's likely change is "
             f"{fmt_pct(c['likely'].delta_pct)} ({fmt_usd(c['likely'].delta_usd)}), ranging from {fmt_pct(c['worst'].delta_pct)} "
             f"({fmt_usd(c['worst'].delta_usd)}) in the worst case to {fmt_pct(c['best'].delta_pct)} ({fmt_usd(c['best'].delta_usd)}) in the best."]
    parts.append(f"The scenario reaches {impact.reached_pct:.1f}% of the portfolio's value; {impact.untouched_count} holding(s) are untouched.")
    crossings = len(c["worst"].bands)
    if crossings:
        parts.append(f"In the worst case {crossings} mandate band(s) are crossed.")
    if any(e.breaches for e in c["worst"].collateral):
        parts.append("In the worst case a credit facility trigger is breached.")
    parts.append("Cases are conditional on the scenario, not probabilities.")
    return " ".join(parts)


def summary_figures(impact: PortfolioImpact) -> dict:
    """Every value agent prose about this impact may quote."""
    c = impact.cases
    return {"horizon_months": impact.horizon_months, "reached_pct": impact.reached_pct, "untouched_count": impact.untouched_count,
            "position_count": impact.position_count, "before_usd": impact.before_usd,
            "cases": {k: {"after_usd": v.after_usd, "delta_usd": v.delta_usd, "delta_pct": v.delta_pct,
                          "bands_crossed": len(v.bands), "facilities_breached": sum(e.breaches for e in v.collateral),
                          "bands": [b.model_dump() for b in v.bands], "collateral": [e.model_dump() for e in v.collateral]}
                      for k, v in c.items()}}


def compute_impact(inputs: PortfolioInputs, vector: ShockVector | None, scenario: ScenarioRecord, as_of: date, *,
                   agent_channels: dict[str, list[tuple[str, str]]] | None = None, agent_mappings: list[AgentMapping] | None = None,
                   inputs_hash: str = "", vector_hash: str = "") -> PortfolioImpact:
    """The impact of ``vector`` on the portfolio. Without a usable vector or holdings the result carries no figures."""
    p = inputs.portfolio
    base = dict(scenario_id=scenario.scenario_id, portfolio_id=p["portfolio_id"], client_id=p["client_id"], as_of=as_of,
                horizon_months=scenario.horizon_months, agent_mappings=agent_mappings or [], inputs_hash=inputs_hash, vector_hash=vector_hash)
    if vector is None or not vector.channels:
        why = "no shock vector exists for this scenario and date" if vector is None else "the shock vector has no usable channel"
        return PortfolioImpact(status="insufficient_data", gaps=[Gap(kind="no_data", subject=scenario.scenario_id, description=why)], **base)
    if not inputs.holdings:
        return PortfolioImpact(status="insufficient_data", gaps=[Gap(kind="no_data", subject=p["portfolio_id"], description="the portfolio has no holdings")], **base)
    gaps: list[Gap] = []
    if vector.status != "complete":
        gaps.append(Gap(kind="other", subject=scenario.scenario_id, description=f"the shock vector is {vector.status}: some channels may be missing"))
    mapped = map_holdings(inputs, agent_channels)
    total_usd = sum(float(h[VALUE]) for h in inputs.holdings)
    positions = [_position(p["portfolio_id"], m, vector, total_usd) for m in mapped]
    absent = _unrelated_channels(vector, mapped)
    if absent:
        gaps.append(Gap(kind="no_data", subject=scenario.scenario_id, description="the vector has no move for channel(s) " + ", ".join(absent)
                        + ": holdings reached only by them are untouched"))
    unresolved = [m.holding["instrument_id"] for m in mapped if m.mapping == "untouched" and m.reason.startswith("not mapped")]
    if unresolved:
        gaps.append(Gap(kind="no_data", subject="mapping", description="not mapped to any channel and left untouched: " + ", ".join(unresolved)))
    untouched = [x for x in positions if x.mapping == "untouched"]
    reached = sum(x.value_usd for x in positions if x.mapping != "untouched")
    cases: dict[str, CaseImpact] = {}
    for k in CASES:
        delta = sum(x.moves[k].delta_usd for x in positions)
        cases[k] = CaseImpact(before_usd=round(total_usd, 2), after_usd=round(total_usd + delta, 2), delta_usd=round(delta, 2),
                              delta_pct=round(delta / total_usd * 100, 4) if total_usd else 0.0, bands=_bands(inputs, positions, k),
                              collateral=_collateral(inputs, positions, k, gaps if k == "likely" else []))
    seen = set()
    gaps = [g for g in gaps if (g.subject, g.description) not in seen and not seen.add((g.subject, g.description))]
    reached_pct = round(reached / total_usd * 100, 2) if total_usd else 0.0
    impact = PortfolioImpact(status="partial" if gaps else "complete", before_usd=round(total_usd, 2), cases=cases, reached_pct=reached_pct,
                             untouched_count=len(untouched), position_count=len(positions), positions=positions, gaps=gaps,
                             explainers=explainers(scenario.horizon_months, reached_pct, len(untouched)), **base)
    return impact.model_copy(update={"summary": built_summary(scenario, impact)})


__all__ = ["ambiguous_holdings", "built_summary", "compute_impact", "explainers", "summary_figures"]
