from datetime import date

import pytest
from pydantic import ValidationError

from rm_dashboard.domain import (
    Client, Computation, Finding, Instrument, Party, Person, Portfolio, Relationship,
    Report, Source, ToolResult,
)


def comp(**p):
    return Computation(tool="t", version="1", parameters=p, method="m")


def result(as_of=date(2026, 8, 26), data=None, **kw):
    return ToolResult(data=data or {"x": 1}, as_of=as_of, computation=comp(a=1), **kw)


def test_entities_construct_and_validate():
    c = Client(client_id="CL-1", name="n", base_currency="SGD", wealth_band="UHNW",
               risk_profile="Balanced", risk_tolerance_score=5, tax_domicile="SG",
               country_of_residence="SG", kyc_review_due=date(2026, 1, 1), pep_status=False,
               liquidity_needs="Low", investment_horizon_years=5, objectives="o", source_of_wealth="s")
    assert c.pit == "current_only"
    with pytest.raises(ValidationError):
        Client(client_id="CL-1")
    Party(party_id="p", kind="individual", name="n")
    with pytest.raises(ValidationError):
        Party(party_id="p", kind="robot", name="n")
    Person(person_id="x", name="n")
    Relationship(from_id="a", to_id="b", kind="spouse", source="kyc")
    Portfolio(portfolio_id="PF", client_id="CL", name="n", mandate_code="M", service_model="Advisory",
              base_currency="USD", benchmark="b")
    Instrument(instrument_id="i", name="n", asset_class="Equity", sub_asset_class="s", sector=None,
               region="G", currency="USD", liquidity_tier="Daily", underlying_reference=None,
               sustainability_excluded=False, concentration_limit_applies=False)


def test_same_input_same_evidence_id():
    assert result().evidence_id == result().evidence_id
    assert result().evidence_id.startswith("ev_")


def test_different_as_of_different_id():
    a = result(as_of=date(2026, 8, 26), effective_snapshot_date=date(2026, 8, 26))
    b = result(as_of=date(2026, 6, 30), effective_snapshot_date=date(2026, 6, 30))
    assert a.evidence_id != b.evidence_id


def test_non_ok_status_needs_reason():
    with pytest.raises(ValidationError):
        result(status="no_data")
    assert result(status="no_data", reason="no person source").status == "no_data"


def test_status_values_restricted():
    with pytest.raises(ValidationError):
        result(status="weird", reason="x")


def test_source_in_envelope():
    r = result(sources=[Source(dataset="holdings", key="PF-1/I-1", snapshot_date=date(2026, 8, 26))])
    assert r.sources[0].dataset == "holdings"


def test_finding_requires_evidence():
    with pytest.raises(ValidationError):
        Finding(claim="x", evidence_ids=[])
    assert Finding(claim="x", evidence_ids=["ev_1"]).confidence == "medium"


def test_report_status_values():
    r = Report(subject="CL-1", as_of=date(2026, 8, 26), status="partial", agent="a")
    assert r.model_dump(mode="json")["status"] == "partial"
    with pytest.raises(ValidationError):
        Report(subject="CL-1", as_of=date(2026, 8, 26), status="bogus", agent="a")


def _blocks(tag):
    import json
    import re
    from pathlib import Path
    text = (Path(__file__).parent.parent / "docs" / "contracts.md").read_text()
    return [json.loads(b) for b in re.findall(rf"```json {tag}\n(.*?)```", text, re.S)]


def test_documented_examples_validate():
    tr = _blocks("tool-result")
    rp = _blocks("report")
    assert tr and rp
    for obj in tr:
        assert ToolResult.model_validate(obj).evidence_id
    for obj in rp:
        Report.model_validate(obj)
