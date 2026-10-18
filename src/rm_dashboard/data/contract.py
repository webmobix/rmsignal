"""The datasource contract: typed reads of the 12 source tables, whatever the backend.

``SqliteDataSource`` and ``FirestoreDataSource`` implement ``select``, ``count`` and ``get_by_key``; ``TypedReads`` derives the
typed list and look-up reads from ``select``, so every backend answers them the same way. Standard library only.
"""

from typing import Any, Protocol

from . import models
from .schema import ENTITIES, Entity, ValueParseError, columns, parse_text

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


def parse_filters(entity: Entity, filters: dict[str, str]) -> dict[str, Any]:
    """Exact-match filters as typed values; names are whitelisted. Raises UnknownColumnError or schema.ValueParseError."""
    by_name = {c.name: c for c in columns(entity)}
    out: dict[str, Any] = {}
    for name, text in filters.items():
        if name not in by_name:
            raise UnknownColumnError(name)
        col = by_name[name]
        text = _BOOL_WORDS.get(text.lower(), text) if col.type is bool else text
        out[name] = parse_text(col, text)
    return out


class DataSource(Protocol):
    """Read-only, typed access to the source tables. Records are in source file order."""

    def close(self) -> None: ...
    def select(self, table: str, filters: dict[str, str] | None = None, limit: int | None = None, offset: int = 0) -> list: ...
    def count(self, table: str, filters: dict[str, str] | None = None) -> int: ...
    def get_by_key(self, table: str, key: tuple[str, ...]): ...
    def list_clients(self) -> list[models.Client]: ...
    def list_portfolios(self) -> list[models.Portfolio]: ...
    def list_holdings(self) -> list[models.Holding]: ...
    def list_instruments(self) -> list[models.Instrument]: ...
    def list_mandates(self) -> list[models.Mandate]: ...
    def list_transactions(self) -> list[models.Transaction]: ...
    def list_credit_facilities(self) -> list[models.CreditFacility]: ...
    def list_commitments(self) -> list[models.Commitment]: ...
    def list_planned_cash_needs(self) -> list[models.PlannedCashNeed]: ...
    def list_market_context(self) -> list[models.MarketContext]: ...
    def list_events(self) -> list[models.Event]: ...
    def list_rm_notes(self) -> list[models.RMNote]: ...


class TypedReads:
    """The typed list and look-up reads, in terms of ``select`` and ``get_by_key``."""

    def select(self, table: str, filters: dict[str, str] | None = None, limit: int | None = None, offset: int = 0) -> list:
        raise NotImplementedError

    def _one(self, table: str, column: str, value: str):
        try:
            found = self.select(table, {column: value})
        except ValueParseError:  # a value that cannot be that column's type is the key of no row
            return None
        return found[0] if found else None

    def list_clients(self) -> list[models.Client]:
        return self.select("clients")

    def get_client(self, client_id: str) -> models.Client | None:
        return self._one("clients", "client_id", client_id)

    def list_portfolios(self) -> list[models.Portfolio]:
        return self.select("portfolios")

    def get_portfolio(self, portfolio_id: str) -> models.Portfolio | None:
        return self._one("portfolios", "portfolio_id", portfolio_id)

    def portfolios_for_client(self, client_id: str) -> list[models.Portfolio]:
        return self.select("portfolios", {"client_id": client_id})

    def list_holdings(self) -> list[models.Holding]:
        return self.select("holdings")

    def holdings_for(self, portfolio_id: str, snapshot_date) -> list[models.Holding]:
        return self.select("holdings", {"portfolio_id": portfolio_id, "snapshot_date": snapshot_date.isoformat()})

    def list_instruments(self) -> list[models.Instrument]:
        return self.select("instruments")

    def get_instrument(self, instrument_id: str) -> models.Instrument | None:
        return self._one("instruments", "instrument_id", instrument_id)

    def list_mandates(self) -> list[models.Mandate]:
        return self.select("mandates")

    def list_transactions(self) -> list[models.Transaction]:
        return self.select("transactions")

    def get_transaction(self, transaction_id: str) -> models.Transaction | None:
        return self._one("transactions", "transaction_id", transaction_id)

    def list_credit_facilities(self) -> list[models.CreditFacility]:
        return self.select("credit_facilities")

    def get_credit_facility(self, facility_id: str) -> models.CreditFacility | None:
        return self._one("credit_facilities", "facility_id", facility_id)

    def list_commitments(self) -> list[models.Commitment]:
        return self.select("commitments")

    def get_commitment(self, commitment_id: str) -> models.Commitment | None:
        return self._one("commitments", "commitment_id", commitment_id)

    def list_planned_cash_needs(self) -> list[models.PlannedCashNeed]:
        return self.select("planned_cash_needs")

    def get_planned_cash_need(self, need_id: str) -> models.PlannedCashNeed | None:
        return self._one("planned_cash_needs", "need_id", need_id)

    def list_market_context(self) -> list[models.MarketContext]:
        return self.select("market_context")

    def list_events(self) -> list[models.Event]:
        return self.select("event_log")

    def list_rm_notes(self) -> list[models.RMNote]:
        return self.select("rm_notes")

    def get_rm_note(self, note_id: str) -> models.RMNote | None:
        return self._one("rm_notes", "note_id", note_id)

    def get_by_key(self, table: str, key: tuple[str, ...]):
        """The row whose primary key equals ``key`` (source-form text), or None.

        A key of the wrong length, or a table without a primary key, matches nothing.
        """
        entity = entity_for(table)
        if not entity.primary_key or len(key) != len(entity.primary_key):
            return None
        found = self.select(table, dict(zip(entity.primary_key, key)))
        return found[0] if found else None
