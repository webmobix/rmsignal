"""Read-only Firestore datasource: one collection per table, the primary key as the document id, ``_seq`` for source file order.

Returns the same record types, values and order as ``SqliteDataSource``; the typed reads come from ``contract.TypedReads``.
It has no write operations: the tables are published by ``rm-dashboard-load source``."""

from rm_dashboard.firestore_client import open_client

from .contract import TypedReads, entity_for, parse_filters
from .schema import from_document

SEQ = "_seq"


class FirestoreDataSource(TypedReads):
    def __init__(self, client):
        self.client = client
        self._tables: dict[str, list] = {}

    def close(self) -> None:
        self.client.close()

    def __enter__(self) -> "FirestoreDataSource":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def _rows(self, table: str) -> list:
        """All rows of a table in source file order, read once per datasource."""
        if table not in self._tables:
            entity = entity_for(table)
            docs = self.client.collection(table).order_by(SEQ).stream()
            self._tables[table] = [from_document(entity, d.to_dict()) for d in docs]
        return self._tables[table]

    def _matching(self, table: str, filters: dict[str, str] | None) -> list:
        entity = entity_for(table)
        typed = parse_filters(entity, filters or {})
        rows = self._rows(table)
        return [r for r in rows if all(getattr(r, n) == v for n, v in typed.items())] if typed else rows

    def select(self, table: str, filters: dict[str, str] | None = None, limit: int | None = None, offset: int = 0) -> list:
        rows = self._matching(table, filters)
        return rows[offset:] if limit is None else rows[offset:offset + limit]

    def count(self, table: str, filters: dict[str, str] | None = None) -> int:
        return len(self._matching(table, filters))


def open_firestore_data_source(location: str) -> FirestoreDataSource:
    """``location`` is ``<project>[/<database>]``. Raises ImportError (naming the extra to install) without the client library."""
    return FirestoreDataSource(open_client(location))
