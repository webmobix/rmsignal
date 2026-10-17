"""Small hand-made portfolios and vectors for the scenario engine tests. Plain rows, no database."""

from datetime import date

from rm_dashboard.scenarios.contracts import ChannelMove, ScenarioRecord, ShockVector
from rm_dashboard.scenarios.mapping import PortfolioInputs

AS_OF = date(2026, 8, 26)
SCENARIO = ScenarioRecord(scenario_id="test-scenario", name="Test scenario", premise="Something happens in the Gulf.")


def instrument(iid, name, asset_class, sector, region="North America", ccy="USD", sub="", ref=None):
    return {"instrument_id": iid, "instrument_name": name, "asset_class": asset_class, "sub_asset_class": sub, "sector": sector,
            "region": region, "currency": ccy, "underlying_reference": ref}


def holding(iid, inst, usd, base=None, lending=0.6, ccy=None, pf="PF-T"):
    base = usd if base is None else base
    return {"snapshot_date": AS_OF, "portfolio_id": pf, "client_id": "CL-T", "instrument_id": iid, "instrument_name": inst["instrument_name"],
            "asset_class": inst["asset_class"], "sub_asset_class": inst["sub_asset_class"], "sector": inst["sector"], "region": inst["region"],
            "instrument_ccy": ccy or inst["currency"], "market_value_usd": usd, "market_value_base": base, "lending_value_base": base * lending}


def move(channel, best, likely, worst, **kw):
    return ChannelMove(channel=channel, best=best, likely=likely, worst=worst, rationale="r", explainer="e", evidence_ids=["ev_1"], **kw)


def vector(*moves, status="complete", scenario_id="test-scenario"):
    return ShockVector(scenario_id=scenario_id, as_of=AS_OF, status=status, summary="s", channels=list(moves))


US_EQ = instrument("SYN-EQ-0001", "US Core Fund", "Equity", "Diversified")
FI = instrument("SYN-FI-0001", "Treasury Fund", "Fixed Income", "Sovereign", sub="Government Bond")
CASH = instrument("SYN-CA-0001", "USD Deposit", "Cash and Equivalents", "Cash", region="Global")
ENERGY = instrument("SYN-EQ-0100", "Alpha Energy Corp", "Equity", "Energy", region="Indonesia", ccy="IDR", sub="Single Stock")
TECH = instrument("SYN-EQ-0101", "Beta Tech Inc", "Equity", "Information Technology", sub="Single Stock")
BASKET = instrument("SYN-SP-0001", "Note ref. Basket", "Structured Products", "Multi", region="Global", sub="Yield Enhancement",
                    ref="Worst-of basket: Alpha Energy Corp / Beta Tech Inc")
HEDGE = instrument("SYN-AL-0001", "Macro Fund", "Alternatives", "Macro", region="Global", sub="Hedge Fund")
ALL = {i["instrument_id"]: i for i in (US_EQ, FI, CASH, ENERGY, TECH, BASKET, HEDGE)}


def simple_portfolio(**kw) -> PortfolioInputs:
    """60 US equity, 30 treasuries, 10 USD cash; one band that the worst case crosses; one facility the worst case breaches."""
    pf = {"portfolio_id": "PF-T", "client_id": "CL-T", "portfolio_name": "Test", "mandate_code": "T", "service_model": "Discretionary",
          "base_currency": "USD"}
    bands = [{"asset_class": "Equity", "min_pct": 20.0, "max_pct": 65.0}, {"asset_class": "Fixed Income", "min_pct": 20.0, "max_pct": 31.0},
             {"asset_class": "Cash and Equivalents", "min_pct": 5.0, "max_pct": 15.0}]
    fac = [{"facility_id": "CF-T", "facility_ccy": "USD", "margin_call_ltv_pct": 70.0, "drawn": 40.0, "collateral_market_value": 100.0,
            "lending_value": 60.0}]
    return PortfolioInputs(pf, [holding("SYN-EQ-0001", US_EQ, 60), holding("SYN-FI-0001", FI, 30), holding("SYN-CA-0001", CASH, 10)], ALL,
                           kw.get("bands", bands), kw.get("facilities", fac))
