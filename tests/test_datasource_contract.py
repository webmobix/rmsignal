"""The datasource contract, run against every backend."""

import sqlite3
from datetime import date

import pytest

from firestore_support import BACKENDS, new_client, patched_client

from rm_dashboard.data import models, seed
from rm_dashboard.data.contract import DataSource, UnknownColumnError, UnknownTableError
from rm_dashboard.data.datasource import SqliteDataSource
from rm_dashboard.data.schema import ENTITIES, ValueParseError

LISTS = {
    "clients": "list_clients", "portfolios": "list_portfolios", "holdings": "list_holdings", "instruments": "list_instruments",
    "mandates": "list_mandates", "transactions": "list_transactions", "credit_facilities": "list_credit_facilities",
    "commitments": "list_commitments", "planned_cash_needs": "list_planned_cash_needs", "market_context": "list_market_context",
    "event_log": "list_events", "rm_notes": "list_rm_notes",
}


@pytest.fixture(scope="module", params=BACKENDS)
def source(request, seeded_db):
    if request.param == "sqlite":
        with SqliteDataSource(seeded_db) as ds:
            yield ds
        return
    from rm_dashboard.data.firestore import FirestoreDataSource
    from rm_dashboard.loader.firestore import load_source_to_firestore

    client = new_client(request.param)
    with patched_client(client):
        load_source_to_firestore(seed.DEFAULT_DATA_DIR, "demo")
    yield FirestoreDataSource(client)


@pytest.fixture(scope="module")
def reference(seeded_db):
    """The counts the seed command reports."""
    conn = sqlite3.connect(f"file:{seeded_db}?mode=ro", uri=True)
    try:
        return {e.table: conn.execute(f'SELECT COUNT(*) FROM "{e.table}"').fetchone()[0] for e in ENTITIES}
    finally:
        conn.close()


def test_there_are_twelve_tables_and_a_typed_list_for_each():
    assert {e.table for e in ENTITIES} == set(LISTS)


def test_the_object_satisfies_the_contract(source):
    for name in (*LISTS.values(), "select", "count", "get_by_key", "close"):
        assert callable(getattr(source, name)), name
    ds: DataSource = source  # noqa: F841 - the type is the check


@pytest.mark.parametrize("table", sorted(LISTS))
def test_every_table_lists_all_rows_as_its_record_type(source, reference, table):
    rows = getattr(source, LISTS[table])()
    entity = next(e for e in ENTITIES if e.table == table)
    assert len(rows) == reference[table] == source.count(table)
    assert all(type(r) is entity.model for r in rows)
    assert source.select(table) == rows


def test_holdings_have_no_key_and_none_are_lost(source, reference):
    assert len(source.list_holdings()) == reference["holdings"] > 1000
    assert source.get_by_key("holdings", ("PF-0001",)) is None  # no primary key: nothing matches


def test_mandates_keep_every_composite_key_row(source, reference):
    rows = source.list_mandates()
    assert len(rows) == reference["mandates"] and len({(m.mandate_code, m.asset_class) for m in rows}) == len(rows)
    first = rows[0]
    assert source.get_by_key("mandates", (first.mandate_code, first.asset_class)) == first
    assert source.get_by_key("mandates", (first.mandate_code,)) is None  # wrong key length


def test_values_keep_their_types(source):
    c = source.get_client("CL-0001")
    assert isinstance(c, models.Client) and isinstance(c.kyc_review_due, date) and c.pep_status is False
    assert isinstance(c.total_aum_usd, float)
    assert any(x.age is None for x in source.list_clients())
    assert {i.concentration_limit_applies for i in source.list_instruments()} == {True, False}
    assert all(type(i.sustainability_excluded) is bool for i in source.list_instruments())


def test_look_ups_by_id_and_unknown_ids(source):
    assert source.get_portfolio("PF-0001").portfolio_id == "PF-0001" and source.get_portfolio("PF-NOPE") is None
    assert source.get_instrument("SYN-EQ-0001") is not None and source.get_rm_note("N-NOPE") is None
    assert all(p.client_id == "CL-0001" for p in source.portfolios_for_client("CL-0001"))
    h = source.list_holdings()[0]
    assert h in source.holdings_for(h.portfolio_id, h.snapshot_date)


def test_select_filters_count_and_paging(source):
    everyone = source.list_clients()
    mine = source.select("clients", {"client_id": "CL-0001"})
    assert [c.client_id for c in mine] == ["CL-0001"] and source.count("clients", {"client_id": "CL-0001"}) == 1
    assert source.select("clients", limit=3, offset=2) == everyone[2:5]
    flagged = source.select("clients", {"pep_status": "true"})
    assert flagged == [c for c in everyone if c.pep_status] and source.count("clients", {"pep_status": "true"}) == len(flagged)


def test_unknown_table_column_and_value(source):
    with pytest.raises(UnknownTableError):
        source.select("nope")
    with pytest.raises(UnknownColumnError):
        source.select("clients", {"nope": "x"})
    with pytest.raises(ValueParseError):
        source.select("clients", {"total_aum_usd": "abc"})


def test_there_is_no_write_path(source):
    verbs = ("put", "set", "insert", "update", "delete", "write", "create", "add", "remove", "save")
    public = [n for n in dir(source) if not n.startswith("_") and callable(getattr(source, n))]
    assert not [n for n in public if any(n == v or n.startswith(v + "_") for v in verbs)]
