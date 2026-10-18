"""``/api/scenarios``: the scenario catalogue, per-client results and the RM-book roll-up, behind a replaceable provider.

``ComputedScenarioProvider`` reads the persisted results of ``rm-dashboard-scenarios``; ``PlaceholderScenarioProvider`` returns fixed,
illustrative data in the same shape and says so (``status: "placeholder"``). Scenario names, premises and caveats live in the
backend (the catalogue store); the UI holds none. Switching the default is one line in ``api/app.py``.
"""

from datetime import date
from typing import Literal, Protocol

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from rm_dashboard.domain import Gap
from rm_dashboard.scenarios.catalogue import CatalogueStore
from rm_dashboard.scenarios.contracts import (
    CASES, BandCrossing, CaseImpact, ChannelMove, ClientLine, ClientRollup, CollateralEffect, Coverage, Crossing, PortfolioLine, PositionChannel,
    PositionImpact, RMRollup, ScenarioRecord, ShockVector, Totals, CasePoint, Case,
)
from rm_dashboard.scenarios.store import ScenarioStore

from .clientdata import client_rows
from .context import NO_ARTIFACTS, ReadContext
from .deps import AsOf, Ctx

router = APIRouter(prefix="/api", tags=["scenarios"])

PLACEHOLDER_NOTE = (
    "Illustrative, not computed: these figures are fixed placeholder data in the final contract shape. "
    "They are not derived from this client's holdings and say nothing about what would happen."
)
NOT_RUN_NOTE = "Not computed: scenarios have not been run for this date (run `rm-dashboard-scenarios`). No figures are shown."
ScenarioStatus = Literal["placeholder", "computed"]
ResultStatus = Literal["computed", "partial", "placeholder", "insufficient_data"]
_STATUS = {"complete": "computed", "partial": "partial", "insufficient_data": "insufficient_data"}


class MarketShock(BaseModel):
    """The scenario's shock vector: best, likely and worst move per market channel."""

    status: ResultStatus
    horizon_months: int
    summary: str
    not_a_probability: str
    channels: list[ChannelMove]
    gaps: list[Gap] = []


class ScenarioInfo(BaseModel):
    scenario_id: str
    name: str
    premise: str
    mirrors: str
    caveat: str
    horizon_months: int = 3
    market: MarketShock | None = None
    """None until the scenario has been run for the date."""


class ScenarioResult(ScenarioInfo):
    """One scenario for one client: three cases and what lies behind them."""

    status: ResultStatus
    note: str = ""
    before_usd: float = 0.0
    cases: dict[Case, CaseImpact] = {}
    reached_pct: float = 0.0
    untouched_count: int = 0
    positions: list[PositionImpact] = []
    portfolios: list[PortfolioLine] = []
    coverage: Coverage = Coverage(computed=0, total=0)
    summary: str = ""
    explainers: dict[str, str] = {}
    gaps: list[Gap] = []


class ScenarioRollup(ScenarioInfo):
    """One scenario for the RM's book."""

    status: ResultStatus
    note: str = ""
    as_of: date
    rm_id: str | None = None
    before_usd: float = 0.0
    cases: dict[Case, Totals] = {}
    most_hit: list[ClientLine] = []
    beneficiaries: list[ClientLine] = []
    crossings: list[Crossing] = []
    coverage: Coverage = Coverage(computed=0, total=0)
    summary: str = ""
    gaps: list[Gap] = []


class ScenarioCatalogue(BaseModel):
    status: ScenarioStatus
    note: str
    as_of: date
    scenarios: list[ScenarioInfo]


class ClientScenarios(BaseModel):
    status: ScenarioStatus
    note: str
    as_of: date
    client_id: str
    scenarios: list[ScenarioResult]


class ScenarioProvider(Protocol):
    def catalogue(self, as_of: date) -> list[ScenarioInfo]: ...
    def for_client(self, client_id: str, as_of: date) -> list[ScenarioResult]: ...
    def rollup(self, scenario_id: str, as_of: date) -> ScenarioRollup | None:
        """None when no such scenario exists."""
        ...


# ---- the computed provider ------------------------------------------------------------------------
def _info(rec: ScenarioRecord, vector: ShockVector | None) -> ScenarioInfo:
    market = None
    if vector is not None:
        market = MarketShock(status=_STATUS[vector.status], horizon_months=vector.horizon_months, summary=vector.summary,
                             not_a_probability=vector.not_a_probability, channels=vector.channels, gaps=vector.gaps)
    return ScenarioInfo(scenario_id=rec.scenario_id, name=rec.name, premise=rec.premise, mirrors=rec.mirrors, caveat=rec.caveat,
                        horizon_months=rec.horizon_months, market=market)


class ComputedScenarioProvider:
    """Reads what ``rm-dashboard-scenarios`` persisted. A scenario without a usable stored result is returned without figures and with a
    status and note saying why; nothing is ever filled in."""

    def __init__(self, ctx: ReadContext):
        self.ctx = ctx

    def _records(self) -> list[ScenarioRecord]:
        return CatalogueStore(self.ctx.store if self.ctx.store is not None else NO_ARTIFACTS).load().scenarios

    def _store(self) -> ScenarioStore | None:
        return ScenarioStore(self.ctx.store) if self.ctx.store is not None else None

    def catalogue(self, as_of: date) -> list[ScenarioInfo]:
        store = self._store()
        return [_info(r, store.load_vector(as_of, r.scenario_id) if store else None) for r in self._records()]

    def for_client(self, client_id: str, as_of: date) -> list[ScenarioResult]:
        store = self._store()
        out = []
        for rec in self._records():
            info = _info(rec, store.load_vector(as_of, rec.scenario_id) if store else None)
            roll = store.load_client(as_of, rec.scenario_id, client_id) if store else None
            out.append(self._result(info, roll))
        return out

    @staticmethod
    def _result(info: ScenarioInfo, roll: ClientRollup | None) -> ScenarioResult:
        if roll is None:
            return ScenarioResult(**info.model_dump(), status="placeholder", note=NOT_RUN_NOTE)
        if roll.status == "insufficient_data" or not roll.cases:
            why = "; ".join(g.description for g in roll.gaps) or "no portfolio of the client has a computed result"
            return ScenarioResult(**info.model_dump(), status="insufficient_data", note=f"Insufficient data: {why}. No figures are shown.",
                                  coverage=roll.coverage, gaps=roll.gaps)
        return ScenarioResult(**info.model_dump(), status=_STATUS[roll.status], before_usd=roll.before_usd, cases=roll.cases,
                              reached_pct=roll.reached_pct, untouched_count=roll.untouched_count, positions=roll.positions, portfolios=roll.portfolios,
                              coverage=roll.coverage, summary=roll.summary, explainers=roll.explainers, gaps=roll.gaps)

    def rollup(self, scenario_id: str, as_of: date) -> ScenarioRollup | None:
        rec = next((r for r in self._records() if r.scenario_id == scenario_id), None)
        if rec is None:
            return None
        store = self._store()
        info = _info(rec, store.load_vector(as_of, scenario_id) if store else None)
        roll: RMRollup | None = store.load_rollup(as_of, scenario_id) if store else None
        if roll is None:
            return ScenarioRollup(**info.model_dump(), status="placeholder", note=NOT_RUN_NOTE, as_of=as_of)
        if roll.status == "insufficient_data" or not roll.cases:
            why = "; ".join(g.description for g in roll.gaps) or "no client has a computed result"
            return ScenarioRollup(**info.model_dump(), status="insufficient_data", note=f"Insufficient data: {why}. No figures are shown.",
                                  as_of=as_of, rm_id=roll.rm_id, coverage=roll.coverage, gaps=roll.gaps)
        return ScenarioRollup(**info.model_dump(), status=_STATUS[roll.status], as_of=as_of, rm_id=roll.rm_id, before_usd=roll.before_usd,
                              cases=roll.cases, most_hit=roll.most_hit, beneficiaries=roll.beneficiaries, crossings=roll.crossings,
                              coverage=roll.coverage, summary=roll.summary, gaps=roll.gaps)


# ---- the placeholder provider ---------------------------------------------------------------------
_CATALOGUE = [
    ScenarioInfo(
        scenario_id="gulf-de-escalation", name="Gulf de-escalation",
        premise="Shipping through the Strait of Hormuz normalises and the energy risk premium unwinds.",
        mirrors="Event log 2026-03-04: Strait of Hormuz effectively closed, read in reverse.",
        caveat="Placeholder. A real run sizes the moves from the event log and applies them to the holdings that the stated channels reach; "
               "it does not net hedges, which the dataset does not record."),
    ScenarioInfo(
        scenario_id="gulf-deterioration", name="Gulf deterioration",
        premise="The naval blockade widens and energy and shipping stay under pressure.",
        mirrors="Event log 2026-08-05: United States reimposes a naval blockade; energy risk premium re-widens.",
        caveat="Placeholder. Channels are additive and no probability is attached to the scenario."),
    ScenarioInfo(
        scenario_id="rates-higher-for-longer", name="Rates higher for longer",
        premise="The Federal Reserve stays on hold and the 10-year yield rises further.",
        mirrors="Event log 2026-07-29: Federal Reserve holds again; US 10-year yield reaches 4.71%.",
        caveat="Placeholder. Duration effects on bonds and valuation effects on growth equity are separate channels."),
]
_SIGNS = {"gulf-de-escalation": 1.0, "gulf-deterioration": -1.0, "rates-higher-for-longer": -0.5}


def _illustrative(info: ScenarioInfo, sign: float) -> ScenarioResult:
    before = 10_000_000.0
    pct = {"best": abs(sign) * 4.0 * (1 if sign > 0 else 0.5), "likely": sign * 3.2, "worst": -abs(sign) * 7.0 if sign < 0 else -1.5}
    cases = {}
    for k in CASES:
        d = before * pct[k] / 100
        cases[k] = CaseImpact(before_usd=before, after_usd=before + d, delta_usd=d, delta_pct=pct[k],
                              collateral=[CollateralEffect(facility="Illustrative Lombard facility", ltv_before_pct=58.0, ltv_after_pct=58.0 - pct[k],
                                                           trigger_pct=75.0, breaches=False)],
                              bands=[BandCrossing(asset_class="Illustrative asset class", portfolio="Illustrative portfolio", before_pct=34.0,
                                                  after_pct=34.0 + pct[k] / 2, band_min_pct=20.0, band_max_pct=35.0,
                                                  crosses="out" if pct[k] > 2 else "in")] if k == "worst" else [])
    pos = [PositionImpact(portfolio_id="Illustrative", instrument_id="-", instrument=f"Illustrative position {n}", asset_class=ac, value_usd=before * w / 100,
                          weight_pct=w, mapping="rule", reason="Placeholder reasoning",
                          moves={k: CasePoint(move_pct=round(pct[k] * m, 2), delta_usd=round(before * w / 100 * pct[k] * m / 100, 2)) for k in CASES},
                          channels=[PositionChannel(channel="illustrative_channel", best_pct=pct["best"] * m, likely_pct=pct["likely"] * m,
                                                    worst_pct=pct["worst"] * m, why="Placeholder reasoning")])
           for n, ac, w, m in (("A", "Equity", 18.0, 1.5), ("B", "Fixed Income", 12.0, -0.5))]
    return ScenarioResult(**info.model_dump(), status="placeholder", note=PLACEHOLDER_NOTE, before_usd=before, cases=cases, reached_pct=62.0,
                          untouched_count=4, positions=pos, summary="Illustrative summary. Nothing here is computed.",
                          explainers={"likely": "Illustrative, not computed."})


class PlaceholderScenarioProvider:
    """Fixed data in the final contract shape. Nothing here reads a holding."""

    def catalogue(self, as_of: date) -> list[ScenarioInfo]:
        return [i.model_copy() for i in _CATALOGUE]

    def for_client(self, client_id: str, as_of: date) -> list[ScenarioResult]:
        return [_illustrative(i, _SIGNS[i.scenario_id]) for i in _CATALOGUE]

    def rollup(self, scenario_id: str, as_of: date) -> ScenarioRollup | None:
        info = next((i for i in _CATALOGUE if i.scenario_id == scenario_id), None)
        if info is None:
            return None
        return ScenarioRollup(**info.model_dump(), status="placeholder", note=PLACEHOLDER_NOTE, as_of=as_of)


# ---- routes ---------------------------------------------------------------------------------------
def _catalogue_status(items: list[ScenarioInfo]) -> ScenarioStatus:
    """``computed`` only when every scenario has a vector (even a partial one), else ``placeholder``."""
    ok = [i.market is not None and i.market.status in ("computed", "partial") for i in items]
    return "computed" if ok and all(ok) else "placeholder"


def _results_status(items: list[ScenarioResult]) -> ScenarioStatus:
    ok = [r.status in ("computed", "partial") for r in items]
    return "computed" if ok and all(ok) else "placeholder"


def provider(request: Request) -> ScenarioProvider:
    return request.app.state.scenarios


@router.get("/scenarios")
def get_scenarios(request: Request, as_of: AsOf) -> ScenarioCatalogue:
    items = provider(request).catalogue(as_of)
    status = _catalogue_status(items)
    return ScenarioCatalogue(status=status, note="" if status == "computed" else NOT_RUN_NOTE, as_of=as_of, scenarios=items)


@router.get("/clients/{client_id}/scenarios")
def get_client_scenarios(request: Request, ctx: Ctx, as_of: AsOf, client_id: str) -> ClientScenarios:
    if client_id not in client_rows(ctx, as_of):
        raise HTTPException(404, f"no client {client_id!r} at {as_of}")
    results = provider(request).for_client(client_id, as_of)
    status = _results_status(results)
    note = "" if status == "computed" else (PLACEHOLDER_NOTE if any(r.status == "placeholder" and r.cases for r in results) else NOT_RUN_NOTE)
    return ClientScenarios(status=status, note=note, as_of=as_of, client_id=client_id, scenarios=results)


@router.get("/scenarios/{scenario_id}/rollup")
def get_scenario_rollup(request: Request, as_of: AsOf, scenario_id: str) -> ScenarioRollup:
    r = provider(request).rollup(scenario_id, as_of)
    if r is None:
        raise HTTPException(404, f"no scenario {scenario_id!r}")
    return r
