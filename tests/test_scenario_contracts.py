import json
from datetime import datetime

import pytest
from pydantic import ValidationError

from rm_dashboard.scenarios import SEED_SCENARIOS, CatalogueStore, ScenarioRecord
from rm_dashboard.scenarios.catalogue import scenario_hash
from rm_dashboard.scenarios.channels import (
    fx_channel, instrument_channels, is_single_instrument_key, region_bucket, sector_channels, vocabulary,
)


def test_record_defaults_to_three_months_and_a_not_a_probability_caveat():
    r = ScenarioRecord(scenario_id="x", name="X", premise="Something happens.")
    assert r.horizon_months == 3 and "not a probability" in r.caveat


def test_record_without_premise_is_invalid():
    with pytest.raises(ValidationError, match="premise"):
        ScenarioRecord(scenario_id="x", name="X")
    with pytest.raises(ValidationError):
        ScenarioRecord(scenario_id="x", name="X", premise="   ")


def test_fresh_store_lists_the_three_seeded_scenarios(tmp_path):
    cat = CatalogueStore(tmp_path).load()
    assert [s.name for s in cat.scenarios] == ["Gulf de-escalation", "Gulf deterioration", "Rates higher for longer"]
    assert all(s.horizon_months == 3 for s in cat.scenarios) and not cat.rejected
    assert not CatalogueStore(tmp_path).path.exists()  # loading never writes


def test_seeded_mirrors_name_an_event_log_date():
    import re
    assert all(re.search(r"Event log \d{4}-\d{2}-\d{2}", s.mirrors) for s in SEED_SCENARIOS)


def test_adding_a_scenario_from_text_keeps_the_seeds(tmp_path):
    store = CatalogueStore(tmp_path)
    store.add(ScenarioRecord(scenario_id="taiwan-strait", name="Taiwan Strait", premise="Shipping lanes close.",
                             created_at=datetime(2026, 8, 26, 9, 0)))
    cat = store.load()
    assert [s.scenario_id for s in cat.scenarios][-1] == "taiwan-strait" and len(cat.scenarios) == 4
    assert cat.get("taiwan-strait").horizon_months == 3 and cat.get("taiwan-strait").created_at == datetime(2026, 8, 26, 9, 0)


def test_a_record_without_premise_is_rejected_and_the_rest_survive(tmp_path):
    store = CatalogueStore(tmp_path)
    store.path.parent.mkdir(parents=True)
    store.path.write_text(json.dumps({"scenarios": [
        {"scenario_id": "ok", "name": "Ok", "premise": "Fine."}, {"scenario_id": "bad", "name": "Bad"},
        {"scenario_id": "ok", "name": "Dup", "premise": "Again."}]}))
    cat = store.load()
    assert [s.scenario_id for s in cat.scenarios] == ["ok"]
    assert any("bad" in m and "premise" in m for m in cat.rejected) and any("duplicate" in m for m in cat.rejected)


def test_scenario_hash_follows_the_text_not_the_creation_time():
    a = SEED_SCENARIOS[0]
    assert scenario_hash(a) == scenario_hash(a.model_copy(update={"created_at": None}))
    assert scenario_hash(a) != scenario_hash(a.model_copy(update={"premise": a.premise + " More."}))


def test_equity_reaches_its_regional_market_and_sector_overlay():
    r = instrument_channels({"asset_class": "Equity", "sector": "Energy", "region": "Indonesia"})
    assert [c for c, _ in r.channels] == ["equity_asia", "sector_energy"] and r.ambiguous is None
    assert [c for c, _ in instrument_channels({"asset_class": "Equity", "sector": "Diversified", "region": "Global"}).channels] == ["equity_global"]


def test_bonds_reach_rates_and_credit_only_when_credit_risky():
    assert [c for c, _ in instrument_channels({"asset_class": "Fixed Income", "sector": "Sovereign", "sub_asset_class": "Government Bond"}).channels] == ["rates_duration"]
    assert [c for c, _ in instrument_channels({"asset_class": "Fixed Income", "sector": "Corporate", "sub_asset_class": "High Yield Credit"}).channels] == ["rates_duration", "credit_spreads"]


def test_cash_reaches_nothing_and_hedge_funds_are_ambiguous():
    assert not instrument_channels({"asset_class": "Cash and Equivalents", "sector": "Cash"}).channels
    assert instrument_channels({"asset_class": "Alternatives", "sector": "Macro", "sub_asset_class": "Hedge Fund"}).ambiguous
    assert instrument_channels({"asset_class": "Alternatives", "sector": "Real Estate"}).channels[0][0] == "real_estate"


def test_structured_product_fallback_follows_its_sector_or_is_ambiguous():
    assert sector_channels({"sector": "Gold"}).channels[0][0] == "gold"
    assert sector_channels({"sector": "Multi"}).ambiguous and sector_channels({"sector": None}).ambiguous


def test_fx_and_region_helpers():
    assert fx_channel("USD") is None and fx_channel("sgd") == "fx_sgd" and fx_channel(None) is None
    assert region_bucket("Hong Kong") == "equity_asia" and region_bucket("Narnia") == "equity_global"


def test_single_instrument_keys_are_recognised():
    assert is_single_instrument_key("SYN-EQ-0001") and is_single_instrument_key("Helios Cloud Systems", {"helios cloud systems"})
    assert not is_single_instrument_key("equity_us")


def test_vocabulary_is_derived_from_the_seeded_instruments(pit_repo):
    from datetime import date
    rows = pit_repo.instruments(as_of=date(2026, 8, 26)).frame.to_dicts()
    ids = [c.channel for c in vocabulary(rows)]
    kinds = {c.channel: c.kind for c in vocabulary(rows)}
    assert {"equity_us", "equity_asia", "rates_duration", "gold", "credit_spreads", "sector_energy", "fx_eur", "fx_sgd"} <= set(ids)
    assert kinds["equity_us"] == "market" and kinds["sector_energy"] == "overlay" and kinds["fx_eur"] == "fx"
    assert ids.index("equity_us") < ids.index("credit_spreads") < ids.index("fx_eur")
    assert "fx_usd" not in ids
