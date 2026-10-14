import sqlite3
from datetime import date

import pytest

from rm_dashboard.data import models, schema
from rm_dashboard.data.schema import ENTITIES, Column, ValueParseError


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    schema.create_schema(c)
    yield c
    c.close()


def test_twelve_tables_with_model_columns(conn):
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert tables == {e.table for e in ENTITIES} and len(tables) == 12
    for e in ENTITIES:
        got = [r[1] for r in conn.execute(f'PRAGMA table_info("{e.table}")')]
        assert got == [c.name for c in schema.columns(e)]


def test_no_foreign_keys_and_join_keys_indexed(conn):
    for e in ENTITIES:
        assert conn.execute(f'PRAGMA foreign_key_list("{e.table}")').fetchall() == []
    idx = {r[1] for r in conn.execute("PRAGMA index_list('holdings')")}
    assert "idx_holdings_snapshot_date_portfolio_id" in idx


def test_orphan_reference_loads(conn):
    conn.execute(
        "INSERT INTO commitments VALUES ('C1','CL-MISSING','PF-MISSING','Fund','USD',1,0,1,'2026')"
    )


def test_bool_column_rejects_other_values(conn):
    cols = [c.name for c in schema.columns(ENTITIES[3])]
    values = ["x"] * len(cols)
    values[cols.index("sustainability_excluded")] = 2
    values[cols.index("concentration_limit_applies")] = 0
    for n in ("price_2025_12_31", "price_2026_02_27", "price_2026_03_31", "price_2026_06_30", "price_2026_08_26"):
        values[cols.index(n)] = 1.0
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(f"INSERT INTO instruments VALUES ({','.join('?' * len(cols))})", values)


def c(type_, nullable=False):
    return Column("f", "f", type_, nullable)


def test_parse_text():
    assert schema.parse_text(c(date), "2026-11-30") == date(2026, 11, 30)
    assert schema.parse_text(c(bool), "Y") is True
    assert schema.parse_text(c(bool), "No") is False
    assert schema.parse_text(c(float), "46571821.48") == 46571821.48
    assert schema.parse_text(c(int, True), "") is None
    assert schema.parse_text(c(str, True), "") is None


@pytest.mark.parametrize(
    "type_, text", [(date, "2026-13-45"), (date, "31/12/2026"), (bool, "Maybe"), (float, "abc"), (int, "1.5")]
)
def test_parse_rejects_invalid(type_, text):
    with pytest.raises(ValueParseError):
        schema.parse_text(c(type_), text)


def test_empty_required_rejected():
    with pytest.raises(ValueParseError):
        schema.parse_text(c(str), "")


def test_storage_roundtrip():
    assert schema.to_storage(date(2026, 1, 2)) == "2026-01-02"
    assert schema.to_storage(False) == 0 and schema.to_storage(False) is not False
    assert schema.from_storage(c(bool), 0) is False
    assert schema.from_storage(c(date), "2026-01-02") == date(2026, 1, 2)
    assert schema.from_storage(c(int, True), None) is None
