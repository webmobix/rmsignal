"""``/api/scenarios``: the scenario catalogue and per-client results, behind a replaceable provider.

There is no scenario engine yet. The only provider, ``PlaceholderScenarioProvider``, returns fixed data in the final
contract shape and says so (``status: "placeholder"``). Scenario names, premises and caveats live here, in the backend;
the UI holds none. A computed provider replaces it without a change to routes or response models.
"""

from datetime import date
from typing import Literal, Protocol

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from .clientdata import client_rows
from .deps import AsOf, Ctx

router = APIRouter(prefix="/api", tags=["scenarios"])

PLACEHOLDER_NOTE = (
    "Illustrative, not computed: these figures are fixed placeholder data in the final contract shape. "
    "They are not derived from this client's holdings and say nothing about what would happen."
)
ScenarioStatus = Literal["placeholder", "computed"]


class ScenarioInfo(BaseModel):
    scenario_id: str
    name: str
    premise: str
    mirrors: str
    caveat: str


class Channel(BaseModel):
    channel: str
    pct: float
    why: str


class PositionMove(BaseModel):
    instrument: str
    asset_class: str
    weight_pct: float
    move_pct: float
    delta_usd: float
    channels: list[Channel]


class CollateralEffect(BaseModel):
    facility: str
    ltv_before_pct: float
    ltv_after_pct: float | None
    trigger_pct: float
    breaches: bool
    shortfall_usd: float | None = None


class BandCrossing(BaseModel):
    asset_class: str
    portfolio: str
    before_pct: float
    after_pct: float
    band_min_pct: float
    band_max_pct: float
    crosses: Literal["out", "in"]


class ScenarioResult(ScenarioInfo):
    status: ScenarioStatus
    note: str = ""
    before_usd: float
    after_usd: float
    delta_usd: float
    delta_pct: float
    reached_pct: float
    untouched_count: int
    collateral: list[CollateralEffect]
    bands: list[BandCrossing]
    positions: list[PositionMove]


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
    status: ScenarioStatus

    def catalogue(self, as_of: date) -> list[ScenarioInfo]: ...
    def for_client(self, client_id: str, as_of: date) -> list[ScenarioResult]: ...


_CATALOGUE = [
    ScenarioInfo(
        scenario_id="gulf-de-escalation", name="Gulf de-escalation",
        premise="Shipping through the Strait of Hormuz normalises and the energy risk premium unwinds.",
        mirrors="Event log 2026-03-04: Strait of Hormuz effectively closed, read in reverse.",
        caveat="Placeholder. A real run would size the move from the event log and apply it to the holdings that the stated "
               "channels reach; it would not net hedges, which the dataset does not record."),
    ScenarioInfo(
        scenario_id="gulf-deterioration", name="Gulf deterioration",
        premise="The naval blockade widens and energy and shipping stay under pressure.",
        mirrors="Event log 2026-08-05: United States reimposes a naval blockade; energy risk premium re-widens.",
        caveat="Placeholder. Channels are additive and no probability is attached to the scenario."),
    ScenarioInfo(
        scenario_id="rates-higher-for-longer", name="Rates higher for longer",
        premise="The Federal Reserve stays on hold and the 10-year yield rises further.",
        mirrors="Event log 2026-07-29: Federal Reserve holds again; US 10-year yield reaches 4.71%.",
        caveat="Placeholder. Duration effects on bonds and valuation effects on growth equity would be separate channels."),
]


def _result(info: ScenarioInfo, sign: float) -> ScenarioResult:
    before = 10_000_000.0
    delta_pct = round(sign * 3.2, 1)
    delta = before * delta_pct / 100
    return ScenarioResult(
        **info.model_dump(), status="placeholder", note=PLACEHOLDER_NOTE, before_usd=before, after_usd=before + delta,
        delta_usd=delta, delta_pct=delta_pct, reached_pct=62.0, untouched_count=4,
        collateral=[CollateralEffect(facility="Illustrative Lombard facility", ltv_before_pct=58.0,
                                     ltv_after_pct=58.0 - sign * 4.0, trigger_pct=75.0, breaches=False)],
        bands=[BandCrossing(asset_class="Illustrative asset class", portfolio="Illustrative portfolio", before_pct=34.0,
                            after_pct=34.0 + sign * 2.0, band_min_pct=20.0, band_max_pct=35.0,
                            crosses="out" if sign > 0 else "in")],
        positions=[
            PositionMove(instrument="Illustrative position A", asset_class="Equity", weight_pct=18.0, move_pct=round(sign * 6.0, 1),
                         delta_usd=round(before * 0.18 * sign * 0.06, 2),
                         channels=[Channel(channel="Illustrative channel", pct=round(sign * 6.0, 1), why="Placeholder reasoning")]),
            PositionMove(instrument="Illustrative position B", asset_class="Fixed Income", weight_pct=12.0, move_pct=round(sign * -1.5, 1),
                         delta_usd=round(before * 0.12 * sign * -0.015, 2),
                         channels=[Channel(channel="Illustrative channel", pct=round(sign * -1.5, 1), why="Placeholder reasoning")]),
        ])


class PlaceholderScenarioProvider:
    """Fixed data in the final contract shape. Nothing here reads a holding."""

    status: ScenarioStatus = "placeholder"
    SIGNS = {"gulf-de-escalation": 1.0, "gulf-deterioration": -1.0, "rates-higher-for-longer": -0.5}

    def catalogue(self, as_of: date) -> list[ScenarioInfo]:
        return list(_CATALOGUE)

    def for_client(self, client_id: str, as_of: date) -> list[ScenarioResult]:
        return [_result(i, self.SIGNS[i.scenario_id]) for i in _CATALOGUE]


def _status(items) -> ScenarioStatus:
    return "placeholder" if any(getattr(i, "status", "placeholder") == "placeholder" for i in items) else "computed"


def provider(request: Request) -> ScenarioProvider:
    return request.app.state.scenarios


@router.get("/scenarios")
def get_scenarios(request: Request, as_of: AsOf) -> ScenarioCatalogue:
    p = provider(request)
    items, status = p.catalogue(as_of), p.status
    return ScenarioCatalogue(status=status, note=PLACEHOLDER_NOTE if status == "placeholder" else "", as_of=as_of, scenarios=items)


@router.get("/clients/{client_id}/scenarios")
def get_client_scenarios(request: Request, ctx: Ctx, as_of: AsOf, client_id: str) -> ClientScenarios:
    if client_id not in client_rows(ctx, as_of):
        raise HTTPException(404, f"no client {client_id!r} at {as_of}")
    results = provider(request).for_client(client_id, as_of)
    status = _status(results)
    return ClientScenarios(status=status, note=PLACEHOLDER_NOTE if status == "placeholder" else "", as_of=as_of,
                           client_id=client_id, scenarios=results)
