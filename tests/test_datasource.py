import sqlite3
from datetime import date

import pytest

from rm_dashboard.data import models
from rm_dashboard.data.datasource import SqliteDataSource


@pytest.fixture
def ds(seeded_db):
    with SqliteDataSource(seeded_db) as source:
        yield source


def test_list_clients_typed(ds):
    clients = ds.list_clients()
    assert len(clients) == 20 and all(isinstance(c, models.Client) for c in clients)
    c = ds.get_client("CL-0001")
    assert c.kyc_review_due == date(2026, 11, 30) and isinstance(c.client_since, date)
    assert c.pep_status is False and isinstance(c.total_aum_usd, float)


def test_null_returns_none(ds):
    assert any(c.age is None for c in ds.list_clients())
    assert any(t.instrument_id is None for t in ds.list_transactions())


def test_get_and_unknown_id(ds):
    assert ds.get_portfolio("PF-0001").portfolio_id == "PF-0001"
    assert ds.get_portfolio("PF-NOPE") is None
    assert ds.get_instrument("SYN-EQ-0001") is not None


def test_boolean_roundtrip(ds):
    flags = {i.concentration_limit_applies for i in ds.list_instruments()}
    assert flags == {True, False}
    assert all(type(i.sustainability_excluded) is bool for i in ds.list_instruments())


def test_join_filters(ds):
    assert {p.client_id for p in ds.portfolios_for_client("CL-0001")} == {"CL-0001"}
    snap = date(2025, 12, 31)
    held = ds.holdings_for("PF-0001", snap)
    assert held and all(h.portfolio_id == "PF-0001" and h.snapshot_date == snap for h in held)


def test_all_lists_have_expected_counts(ds):
    assert len(ds.list_portfolios()) == 24 and len(ds.list_holdings()) == 1015
    assert len(ds.list_instruments()) == 62 and len(ds.list_mandates()) == 48
    assert len(ds.list_transactions()) == 393 and len(ds.list_credit_facilities()) == 5
    assert len(ds.list_commitments()) == 5 and len(ds.list_planned_cash_needs()) == 20
    assert len(ds.list_market_context()) == 115 and len(ds.list_events()) == 16
    assert len(ds.list_rm_notes()) == 28 and ds.list_rm_notes()[0].note_date == date(2026, 1, 8)


def test_read_only(ds):
    with pytest.raises(sqlite3.OperationalError):
        ds.connection.execute("DELETE FROM clients")
    assert len(ds.list_clients()) == 20


def test_missing_database(tmp_path):
    with pytest.raises(FileNotFoundError, match="seed"):
        SqliteDataSource(tmp_path / "nope.db")


def test_select_filter_and_paging(ds):
    assert len(ds.select("clients")) == 20 == ds.count("clients")
    mine = ds.select("portfolios", {"client_id": "CL-0001"})
    assert mine and all(p.client_id == "CL-0001" for p in mine)
    assert ds.count("portfolios", {"client_id": "CL-0001"}) == len(mine)
    everything = ds.select("transactions")
    assert ds.select("transactions", limit=5, offset=10) == everything[10:15]
    assert ds.select("transactions", offset=len(everything)) == []


def test_select_typed_filter_values(ds):
    assert {c.pep_status for c in ds.select("clients", {"pep_status": "true"})} <= {True}
    assert ds.count("clients", {"pep_status": "true"}) + ds.count(
        "clients", {"pep_status": "false"}
    ) == 20
    c = ds.get_client("CL-0001")
    hit = ds.select("clients", {"kyc_review_due": c.kyc_review_due.isoformat()})
    assert c in hit
    assert ds.select("clients", {"risk_tolerance_score": str(c.risk_tolerance_score)})


def test_select_rejects_unknown_and_hostile_names(ds):
    from rm_dashboard.data.datasource import UnknownColumnError, UnknownTableError
    from rm_dashboard.data.schema import ValueParseError

    with pytest.raises(UnknownTableError):
        ds.select("nope")
    with pytest.raises(UnknownTableError):
        ds.count('clients"; DROP TABLE clients; --')
    with pytest.raises(UnknownColumnError):
        ds.select("clients", {"nope": "x"})
    with pytest.raises(UnknownColumnError):
        ds.select("clients", {'client_id" = 1 OR "1': "x"})
    with pytest.raises(ValueParseError):
        ds.select("clients", {"kyc_review_due": "not-a-date"})
    assert ds.select("clients", {"client_id": "' OR '1'='1"}) == []
    assert ds.count("clients") == 20


def test_get_by_key_single_and_composite(ds):
    assert ds.get_by_key("portfolios", ("PF-0001",)) == ds.get_portfolio("PF-0001")
    assert ds.get_by_key("portfolios", ("PF-NOPE",)) is None
    m = ds.list_mandates()[0]
    assert ds.get_by_key("mandates", (m.mandate_code, m.asset_class)) == m
    assert ds.get_by_key("mandates", (m.mandate_code,)) is None
    assert ds.get_by_key("holdings", ("x",)) is None
