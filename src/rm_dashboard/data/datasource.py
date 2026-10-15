"""Read-only SQLite datasource returning typed records."""

import sqlite3
from pathlib import Path

from . import models
from .schema import ENTITIES, Entity, columns, from_storage, parse_text, to_storage

_BY_TABLE = {e.table: e for e in ENTITIES}
_BOOL_WORDS = {"true": "Y", "false": "N"}


class UnknownTableError(LookupError):
    """The name is not one of the dataset tables."""


class UnknownColumnError(LookupError):
    """The name is not a column of the table."""


def entity_for(table: str) -> Entity:
    try:
        return _BY_TABLE[table]
    except KeyError:
        raise UnknownTableError(table) from None


class SqliteDataSource:
    """Typed, read-only access to a database created by the seeder."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        if not self.path.is_file():
            raise FileNotFoundError(
                f"database not found: {self.path} (create it with `rm-dashboard-seed --db {self.path}`)"
            )
        self.connection = sqlite3.connect(f"{self.path.resolve().as_uri()}?mode=ro", uri=True)

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> "SqliteDataSource":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def _select(self, table: str, where: str = "", params: tuple = (), order: str = "") -> list:
        entity: Entity = _BY_TABLE[table]
        cols = columns(entity)
        names = ", ".join(f'"{c.name}"' for c in cols)
        sql = f'SELECT {names} FROM "{table}"'
        if where:
            sql += f" WHERE {where}"
        sql += f" ORDER BY {order or 'rowid'}"
        rows = self.connection.execute(sql, params).fetchall()
        return [entity.model(*(from_storage(c, v) for c, v in zip(cols, row))) for row in rows]

    def _filter(self, entity: Entity, filters: dict[str, str]) -> tuple[str, tuple]:
        """WHERE clause for exact matches; names are whitelisted, values are bound."""
        by_name = {c.name: c for c in columns(entity)}
        clauses, params = [], []
        for name, text in filters.items():
            if name not in by_name:
                raise UnknownColumnError(name)
            col = by_name[name]
            text = _BOOL_WORDS.get(text.lower(), text) if col.type is bool else text
            clauses.append(f'"{name}" = ?')
            params.append(to_storage(parse_text(col, text)))
        return " AND ".join(clauses), tuple(params)

    def select(
        self, table: str, filters: dict[str, str] | None = None,
        limit: int | None = None, offset: int = 0,
    ) -> list:
        """Rows of any table in storage order; filter values are source-form text.

        Raises UnknownTableError, UnknownColumnError or schema.ValueParseError.
        """
        entity = entity_for(table)
        where, params = self._filter(entity, filters or {})
        rows = self._select(table, where, params)
        return rows[offset:] if limit is None else rows[offset:offset + limit]

    def count(self, table: str, filters: dict[str, str] | None = None) -> int:
        entity = entity_for(table)
        where, params = self._filter(entity, filters or {})
        sql = f'SELECT COUNT(*) FROM "{table}"' + (f" WHERE {where}" if where else "")
        return self.connection.execute(sql, params).fetchone()[0]

    def get_by_key(self, table: str, key: tuple[str, ...]):
        """The row whose primary key equals ``key`` (source-form text), or None.

        A key of the wrong length, or a table without a primary key, matches nothing.
        """
        entity = entity_for(table)
        if not entity.primary_key or len(key) != len(entity.primary_key):
            return None
        found = self.select(table, dict(zip(entity.primary_key, key)))
        return found[0] if found else None

    def _get(self, table: str, key: str, value: str):
        found = self._select(table, f'"{key}" = ?', (value,))
        return found[0] if found else None

    # clients
    def list_clients(self) -> list[models.Client]:
        return self._select("clients")

    def get_client(self, client_id: str) -> models.Client | None:
        return self._get("clients", "client_id", client_id)

    # portfolios
    def list_portfolios(self) -> list[models.Portfolio]:
        return self._select("portfolios")

    def get_portfolio(self, portfolio_id: str) -> models.Portfolio | None:
        return self._get("portfolios", "portfolio_id", portfolio_id)

    def portfolios_for_client(self, client_id: str) -> list[models.Portfolio]:
        return self._select("portfolios", '"client_id" = ?', (client_id,))

    # holdings
    def list_holdings(self) -> list[models.Holding]:
        return self._select("holdings")

    def holdings_for(self, portfolio_id: str, snapshot_date) -> list[models.Holding]:
        return self._select(
            "holdings", '"portfolio_id" = ? AND "snapshot_date" = ?',
            (portfolio_id, snapshot_date.isoformat()),
        )

    # instruments
    def list_instruments(self) -> list[models.Instrument]:
        return self._select("instruments")

    def get_instrument(self, instrument_id: str) -> models.Instrument | None:
        return self._get("instruments", "instrument_id", instrument_id)

    # mandates
    def list_mandates(self) -> list[models.Mandate]:
        return self._select("mandates")

    # transactions
    def list_transactions(self) -> list[models.Transaction]:
        return self._select("transactions")

    def get_transaction(self, transaction_id: str) -> models.Transaction | None:
        return self._get("transactions", "transaction_id", transaction_id)

    # credit facilities
    def list_credit_facilities(self) -> list[models.CreditFacility]:
        return self._select("credit_facilities")

    def get_credit_facility(self, facility_id: str) -> models.CreditFacility | None:
        return self._get("credit_facilities", "facility_id", facility_id)

    # commitments
    def list_commitments(self) -> list[models.Commitment]:
        return self._select("commitments")

    def get_commitment(self, commitment_id: str) -> models.Commitment | None:
        return self._get("commitments", "commitment_id", commitment_id)

    # planned cash needs
    def list_planned_cash_needs(self) -> list[models.PlannedCashNeed]:
        return self._select("planned_cash_needs")

    def get_planned_cash_need(self, need_id: str) -> models.PlannedCashNeed | None:
        return self._get("planned_cash_needs", "need_id", need_id)

    # market context
    def list_market_context(self) -> list[models.MarketContext]:
        return self._select("market_context")

    # events
    def list_events(self) -> list[models.Event]:
        return self._select("event_log")

    # RM notes
    def list_rm_notes(self) -> list[models.RMNote]:
        return self._select("rm_notes")

    def get_rm_note(self, note_id: str) -> models.RMNote | None:
        return self._get("rm_notes", "note_id", note_id)
