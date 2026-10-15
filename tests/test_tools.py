from datetime import date

import polars as pl
import pytest
from pydantic import ValidationError

from rm_dashboard.tools import ALLOWLISTS, EvidenceStore, ToolRefused
from rm_dashboard.tools.analytics_tools import ANALYTICS_TOOLS
from rm_dashboard.tools.domain_tools import DOMAIN_TOOLS
from rm_dashboard.tools.peer_tools import PEER_TOOLS

AS_OF = "2026-08-26"
ARGS = {
    "ClientParams": {"client_id": "CL-0001"}, "AsOfOnly": {}, "PortfolioParams": {"portfolio_id": "PF-0001"},
    "InstrumentParams": {"instrument_id": "SYN-EQ-0001"}, "FacilityParams": {"facility_id": "CF-0002"},
    "ExposureParams": {"portfolio_id": "PF-0001", "dimension": "sector"}, "ConcentrationParams": {"client_id": "CL-0001"},
    "LiquidityParams": {"client_id": "CL-0017"}, "ChangeParams": {"portfolio_id": "PF-0001", "from_date": "2026-03-31"},
    "RiskParams": {"instrument_id": "SYN-EQ-0001", "measure": "volatility"},
}


def call(registry, name, as_of=AS_OF, **over):
    spec = registry.specs[name]
    args = {**ARGS[spec.params.__name__], **over}
    if as_of is not None:
        args["as_of"] = as_of
    return registry.toolbox("test", registry.names()).call(name, args)


# ---- 5.1 envelope -------------------------------------------------------------------
def test_envelope_of_sample_tool(registry):
    r = call(registry, "analytics.weights")
    assert r.evidence_id.startswith("ev_") and r.status == "ok"
    assert r.as_of == date(2026, 8, 26) and r.effective_snapshot_date == date(2026, 8, 26) and r.gap_days == 0
    assert r.computation.tool == "analytics.weights" and r.computation.version == "1"
    assert r.computation.parameters == {"as_of": AS_OF, "portfolio_id": "PF-0001"}
    assert "denominator" in r.computation.method
    assert r.sources and all(s.dataset == "holdings" and s.snapshot_date == date(2026, 8, 26) for s in r.sources)
    assert r.data["denominator_label"].startswith("portfolio PF-0001")


def test_same_call_same_evidence_id_and_other_date_differs(registry):
    a, b = call(registry, "analytics.weights"), call(registry, "analytics.weights")
    assert a.evidence_id == b.evidence_id
    c = call(registry, "analytics.weights", as_of="2026-06-30")
    assert c.evidence_id != a.evidence_id and c.effective_snapshot_date == date(2026, 6, 30)


# ---- 5.2 domain tools ---------------------------------------------------------------
@pytest.mark.parametrize("spec", DOMAIN_TOOLS + ANALYTICS_TOOLS + PEER_TOOLS, ids=lambda s: s.name)
def test_every_tool_requires_as_of_and_returns_envelope(registry, spec):
    with pytest.raises(ValidationError):
        call(registry, spec.name, as_of=None)
    r = call(registry, spec.name)
    assert r.computation.tool == spec.name
    assert r.as_of == date(2026, 8, 26)
    if r.status in ("ok", "partial"):
        assert r.sources or not r.data, spec.name
    else:
        assert r.reason


def test_positions_at_a_date(registry):
    r = call(registry, "positions.list", as_of="2026-06-30")
    assert r.effective_snapshot_date == date(2026, 6, 30)
    assert r.data and all(p["snapshot_date"] == date(2026, 6, 30) for p in r.data)
    assert {s.snapshot_date for s in r.sources} == {date(2026, 6, 30)}


def test_before_first_snapshot_is_insufficient(registry):
    r = call(registry, "positions.list", as_of="2025-01-01")
    assert r.status == "insufficient_data" and r.reason and r.data == []


def test_notes_are_quoted_and_dated(registry):
    r = call(registry, "notes.list", as_of="2026-08-26", client_id="CL-0001")
    assert r.data and all(n["source_type"] == "quoted_text" and n["note_id"].startswith("N-") and n["quote"] for n in r.data)
    early = call(registry, "notes.list", as_of="2026-01-10", client_id="CL-0001")
    assert all(n["note_date"] <= date(2026, 1, 10) for n in early.data) and len(early.data) < len(r.data)


def test_waiver_note_does_not_change_calculation(registry):
    # notes are text evidence only: analytics tools take no note input, so figures cannot depend on them
    for spec in ANALYTICS_TOOLS:
        assert "note" not in " ".join(spec.params.model_fields)
    a = call(registry, "analytics.mandate_drift", portfolio_id="PF-0001")
    notes = call(registry, "notes.list", client_id="CL-0001")
    assert notes.status == "ok"
    assert a.evidence_id == call(registry, "analytics.mandate_drift", portfolio_id="PF-0001").evidence_id


def test_news_unavailable_returns_no_data_and_events(registry):
    n = call(registry, "news.list", as_of="2026-03-31")
    assert n.status == "no_data" and "news" in n.reason
    assert n.data["news"] == [] and n.data["curated_events"]
    assert all(e["event_date"] <= date(2026, 3, 31) for e in n.data["curated_events"])
    ev = call(registry, "events.list", as_of="2026-03-31")
    assert ev.status == "ok" and len(ev.data) == len(n.data["curated_events"])


def test_historical_client_tagged_current_only(registry):
    r = call(registry, "clients.get", as_of="2026-03-31")
    assert r.pit == "current_only" and "risk_profile" in r.data["current_only_attributes"]
    assert any(f.code == "current_only" for f in r.flags)


# ---- 5.3 no-data adapters -----------------------------------------------------------
@pytest.mark.parametrize("tool", ["persons.list", "relationships.list"])
def test_no_data_adapters(registry, tool):
    r = call(registry, tool)
    assert r.status == "no_data" and r.reason and r.data == []


def test_client_as_party(registry):
    ind = call(registry, "parties.get", client_id="CL-0001")
    org = call(registry, "parties.get", client_id="CL-0017")
    assert ind.data["party"]["kind"] == "individual" and org.data["party"]["kind"] == "organisation"
    assert ind.data["relationships"] == [] and ind.data["relationships_status"] == "unavailable"
    assert any(f.code == "related_parties_unavailable" for f in ind.flags)


def test_unknown_client_is_no_data(registry):
    assert call(registry, "clients.get", client_id="CL-9999").status == "no_data"
    assert call(registry, "portfolios.get", portfolio_id="PF-9999").status == "no_data"


# ---- 5.4 analytics take identifiers only --------------------------------------------
def test_analytics_tools_need_no_numeric_inputs(registry):
    allowed_extra = {"as_of", "from_date", "horizon_days", "top_n", "include_custody", "dimension", "measure"}
    for spec in ANALYTICS_TOOLS:
        for name, f in spec.params.model_fields.items():
            assert name.endswith("_id") or name in allowed_extra, (spec.name, name)
    r = call(registry, "analytics.concentration")
    assert r.status == "ok" and r.data["top"] and r.computation.parameters["client_id"] == "CL-0001"
    assert any(f.code == "basket_attribution_assumption" for f in r.flags)


def test_numbers_cannot_be_injected(registry):
    with pytest.raises(ValidationError):
        call(registry, "analytics.weights", market_value=1.0)


def test_analytics_tool_values(registry):
    liq = call(registry, "analytics.liquidity", client_id="CL-0017", horizon_days=730)
    assert liq.data["horizon_days"] == 730 and liq.computation.parameters["horizon_days"] == 730
    ltv = call(registry, "analytics.credit_ltv", facility_id="CF-0001")
    assert ltv.data["ltv_pct"] == pytest.approx(73.71, abs=0.01) and len(ltv.data["history"]) == 5
    assert sum(h["breached"] for h in ltv.data["history"]) == 1
    mand = call(registry, "analytics.mandate_drift", portfolio_id="PF-0002")
    assert mand.data["applicable"] is False and mand.data["service_model"] == "Custody"
    ch = call(registry, "analytics.change")
    t = ch.data["total"]
    assert t["flow"] + t["price"] + t["fx"] == pytest.approx(t["change"], rel=1e-9)
    assert ch.data["from_snapshot"] == "2026-03-31"
    bad = call(registry, "analytics.change", from_date="2026-09-30")
    assert bad.status == "insufficient_data"
    risk = call(registry, "analytics.risk")
    assert risk.status == "insufficient_history" and "value" not in risk.data
    fund = call(registry, "analytics.collateral_funding", facility_id="CF-0001", horizon_days=365)
    assert fund.data["pledged_portfolio_id"] == "PF-0003" and "sale_required" in fund.data


def test_historical_analytics_have_no_lookahead(registry):
    r = call(registry, "analytics.liquidity", as_of="2026-03-31", client_id="CL-0001")
    assert r.effective_snapshot_date == date(2026, 3, 31)
    assert all(s.snapshot_date is None or s.snapshot_date <= date(2026, 3, 31) for s in r.sources)


# ---- 5.5 allow-lists ----------------------------------------------------------------
class Recorder:
    def __init__(self):
        self.events = []

    def before(self, agent, tool, args):
        self.events.append(("before", agent, tool))

    def after(self, agent, tool, args, result):
        self.events.append(("after", agent, tool))

    def refused(self, agent, tool, reason):
        self.events.append(("refused", agent, tool))

    def failed(self, agent, tool, args, error):
        self.events.append(("failed", agent, tool))


def test_out_of_list_call_refused_and_recorded(registry):
    obs = Recorder()
    tb = registry.toolbox("instrument_analyst", ALLOWLISTS["instrument_analyst"], observer=obs)
    with pytest.raises(ToolRefused):
        tb.call("credit.facilities", {"client_id": "CL-0001", "as_of": AS_OF})
    assert [(r.agent, r.tool) for r in tb.refusals] == [("instrument_analyst", "credit.facilities")]
    assert ("refused", "instrument_analyst", "credit.facilities") in obs.events
    assert not tb.store.results
    with pytest.raises(ToolRefused):
        tb.call("no.such.tool", {})
    ok = tb.call("instruments.get", {"instrument_id": "SYN-EQ-0001", "as_of": AS_OF})
    assert ok.evidence_id in tb.store


def test_allowlists_name_real_tools_and_are_narrow(registry):
    for agent, names in ALLOWLISTS.items():
        registry.toolbox(agent, names)
        assert set(names) < set(registry.names())
    assert "credit.facilities" not in ALLOWLISTS["instrument_analyst"]
    with pytest.raises(KeyError):
        registry.toolbox("x", ["nope"])


def test_shared_store_across_toolboxes(registry):
    store = EvidenceStore()
    a = registry.toolbox("a", ["clients.list"], store=store)
    b = registry.toolbox("b", ["market.snapshot"], store=store)
    ra, rb = a.call("clients.list", {"as_of": AS_OF}), b.call("market.snapshot", {"as_of": AS_OF})
    assert {ra.evidence_id, rb.evidence_id} <= set(store.results)


# ---- 5.6 inventory ------------------------------------------------------------------
FORBIDDEN = ("path", "file", "sql", "query", "statement", "command", "url", "dir")


def test_no_tool_accepts_path_or_sql(registry):
    for spec in registry.specs.values():
        for name, field in spec.params.model_fields.items():
            assert not any(w in name.lower() for w in FORBIDDEN), (spec.name, name)
            ann = str(field.annotation)
            assert ann in ("<class 'str'>", "<class 'datetime.date'>", "<class 'int'>", "<class 'bool'>",
                           "int | None") or "Literal" in ann, (spec.name, name, ann)
        assert spec.params.model_config.get("extra") == "forbid"


def test_tool_inventory_is_the_defined_set(registry):
    assert set(registry.names()) == {s.name for s in DOMAIN_TOOLS + ANALYTICS_TOOLS + PEER_TOOLS}
    for agent, names in ALLOWLISTS.items():
        assert {s.name for s in registry.toolbox(agent, names).specs()} == set(names)
