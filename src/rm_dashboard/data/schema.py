"""Table schema, value codecs and file registry for the dataset.

The SQLite schema is derived from the dataclasses in ``models`` so the two cannot
drift. Only the standard library is used, so the seeder can run without the app.
"""

import re
import sqlite3
import types
import typing
from dataclasses import dataclass, fields
from datetime import date

from . import models

_DATE_SUFFIX = re.compile(r"_(\d{4})_(\d{2})_(\d{2})$")
_TRUE = {"Y", "Yes"}
_FALSE = {"N", "No"}
_SQL_TYPES = {str: "TEXT", int: "INTEGER", float: "REAL", bool: "INTEGER", date: "TEXT"}


class ValueParseError(ValueError):
    """A source cell could not be converted to its field type."""


@dataclass(frozen=True)
class Entity:
    """Maps one dataset file to its table and record type."""

    file: str
    table: str
    model: type
    primary_key: tuple[str, ...] = ()
    indexes: tuple[tuple[str, ...], ...] = ()


ENTITIES: tuple[Entity, ...] = (
    Entity("clients.csv", "clients", models.Client, ("client_id",)),
    Entity(
        "portfolios.csv", "portfolios", models.Portfolio, ("portfolio_id",),
        (("client_id",), ("mandate_code",)),
    ),
    Entity(
        "holdings.csv", "holdings", models.Holding, (),
        (("snapshot_date", "portfolio_id"), ("client_id",), ("instrument_id",)),
    ),
    Entity("instruments.csv", "instruments", models.Instrument, ("instrument_id",)),
    Entity("mandates.csv", "mandates", models.Mandate, ("mandate_code", "asset_class")),
    Entity(
        "transactions.csv", "transactions", models.Transaction, ("transaction_id",),
        (("portfolio_id",), ("client_id",), ("instrument_id",)),
    ),
    Entity(
        "credit_facilities.csv", "credit_facilities", models.CreditFacility,
        ("facility_id",), (("client_id",), ("collateral_portfolio_id",)),
    ),
    Entity(
        "commitments.csv", "commitments", models.Commitment, ("commitment_id",),
        (("client_id",), ("portfolio_id",)),
    ),
    Entity(
        "planned_cash_needs.csv", "planned_cash_needs", models.PlannedCashNeed,
        ("need_id",), (("client_id",),),
    ),
    Entity(
        "market_context.csv", "market_context", models.MarketContext,
        ("snapshot_date", "series_id"),
    ),
    Entity("event_log.csv", "event_log", models.Event, (), (("event_date",),)),
    Entity("rm_notes.json", "rm_notes", models.RMNote, ("note_id",), (("client_id",),)),
)


@dataclass(frozen=True)
class Column:
    name: str  # field / table column name
    source: str  # column name in the source file
    type: type  # str, int, float, bool or date
    nullable: bool


def source_column(field_name: str) -> str:
    """``aum_2026_08_26`` -> ``aum_2026-08-26``; other names are unchanged."""
    return _DATE_SUFFIX.sub(r"_\1-\2-\3", field_name)


def columns(entity: Entity) -> list[Column]:
    hints = typing.get_type_hints(entity.model)
    result = []
    for f in fields(entity.model):
        hint = hints[f.name]
        nullable = False
        if isinstance(hint, types.UnionType):
            args = [a for a in typing.get_args(hint) if a is not type(None)]
            nullable = len(args) < len(typing.get_args(hint))
            hint = args[0]
        result.append(Column(f.name, source_column(f.name), hint, nullable))
    return result


def parse_text(column: Column, text: str | None):
    """Convert a source cell (CSV text or JSON value) to the column's Python type."""
    if text is None or text == "":
        if column.nullable:
            return None
        raise ValueParseError("empty value in a required column")
    try:
        if column.type is bool:
            if text in _TRUE:
                return True
            if text in _FALSE:
                return False
            raise ValueError("expected Y/N or Yes/No")
        if column.type is date:
            return date.fromisoformat(text)
        if column.type is int:
            return int(text)
        if column.type is float:
            return float(text)
    except ValueError as exc:
        raise ValueParseError(f"cannot parse {text!r} as {column.type.__name__}: {exc}") from None
    return text


def to_storage(value):
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, date):
        return value.isoformat()
    return value


def from_storage(column: Column, value):
    if value is None:
        return None
    if column.type is bool:
        return bool(value)
    if column.type is date:
        return date.fromisoformat(value)
    return value


def create_table_sql(entity: Entity) -> str:
    defs = []
    for c in columns(entity):
        sql = f'"{c.name}" {_SQL_TYPES[c.type]}'
        if not c.nullable:
            sql += " NOT NULL"
        if c.type is bool:
            sql += f' CHECK ("{c.name}" IN (0, 1))'
        defs.append(sql)
    if entity.primary_key:
        defs.append("PRIMARY KEY (" + ", ".join(f'"{k}"' for k in entity.primary_key) + ")")
    return f'CREATE TABLE "{entity.table}" (\n  ' + ",\n  ".join(defs) + "\n)"


def index_sql(entity: Entity) -> list[str]:
    return [
        f'CREATE INDEX "idx_{entity.table}_{"_".join(cols)}" '
        f'ON "{entity.table}" ({", ".join(chr(34) + c + chr(34) for c in cols)})'
        for cols in entity.indexes
    ]


def existing_tables(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    return {r[0] for r in rows} & {e.table for e in ENTITIES}


def drop_schema(conn: sqlite3.Connection) -> None:
    for e in ENTITIES:
        conn.execute(f'DROP TABLE IF EXISTS "{e.table}"')


def create_schema(conn: sqlite3.Connection) -> None:
    for e in ENTITIES:
        conn.execute(create_table_sql(e))
        for stmt in index_sql(e):
            conn.execute(stmt)
