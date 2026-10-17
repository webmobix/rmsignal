"""What scenario runs rest on, read from the point-in-time repository, and the hashes that decide whether a result is still current."""

import hashlib
import json
from datetime import date

from rm_dashboard.outlook.inputs import all_events

from .mapping import PortfolioInputs

PROMPT_VERSION = "1"
"""Bump when a scenario prompt changes in a way that should regenerate stored results."""


def digest(*parts) -> str:
    body = json.dumps(parts, sort_keys=True, default=str)
    return hashlib.sha256(body.encode()).hexdigest()[:16]


def data_fingerprint(repo, as_of: date) -> str:
    """The market and event data available at ``as_of``: equal fingerprints mean nothing new has arrived for a vector."""
    m = repo.market_context(as_of=as_of)
    ev = all_events(repo, as_of)
    return digest(m.effective_snapshot_date if m.status == "ok" else None, [e["event_id"] for e in ev])


def holdings_fingerprint(inputs: PortfolioInputs) -> str:
    """The positions an impact rests on, with the facility and band figures that feed bands and LTV."""
    return digest([(h["instrument_id"], h["market_value_usd"], h["market_value_base"], h.get("lending_value_base")) for h in inputs.holdings],
                  inputs.bands, inputs.facilities, inputs.portfolio.get("base_currency"))


def vector_inputs_hash(*, scenario_hash: str, data: str, model: str) -> str:
    return digest("vector", scenario_hash, data, model, PROMPT_VERSION)


def impact_inputs_hash(*, vector_hash: str, holdings: str, model: str) -> str:
    """Includes the vector's hash: a changed vector regenerates every impact that rests on it."""
    return digest("impact", vector_hash, holdings, model, PROMPT_VERSION)


def rollup_inputs_hash(*, member_hashes: list[str], model: str) -> str:
    return digest("rollup", sorted(member_hashes), model, PROMPT_VERSION)


def load_portfolio_inputs(repo, as_of: date, portfolio_id: str) -> PortfolioInputs | None:
    """The portfolio, its holdings at the effective snapshot, the instruments, mandate bands and facilities it collateralises."""
    pf = repo.portfolios(as_of=as_of, portfolio_id=portfolio_id).frame
    if not pf.height:
        return None
    portfolio = pf.to_dicts()[0]
    holdings = repo.holdings(as_of=as_of, portfolio_id=portfolio_id).frame
    instruments = {r["instrument_id"]: r for r in repo.instruments(as_of=as_of).frame.to_dicts()}
    bands = repo.mandates(as_of=as_of, mandate_code=portfolio.get("mandate_code")).frame
    terms = repo.facility_terms(as_of=as_of, client_id=portfolio["client_id"]).frame
    snaps = repo.facility_snapshots(as_of=as_of, client_id=portfolio["client_id"]).frame
    facilities = []
    for t in terms.to_dicts():
        if t["collateral_portfolio_id"] != portfolio_id:
            continue
        rows = sorted((s for s in snaps.to_dicts() if s["facility_id"] == t["facility_id"]), key=lambda s: s["snapshot_date"])
        if rows:
            facilities.append({**t, **{k: rows[-1][k] for k in ("drawn", "collateral_market_value", "lending_value", "snapshot_date")}})
    return PortfolioInputs(portfolio=portfolio, holdings=holdings.to_dicts() if holdings.height else [], instruments=instruments,
                           bands=bands.to_dicts() if bands.height else [], facilities=facilities)
