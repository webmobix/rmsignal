"""Read-only SQLite datasource returning typed records; the typed reads come from ``contract.TypedReads``."""

import sqlite3
from pathlib import Path

from .contract import TypedReads, UnknownColumnError, UnknownTableError, entity_for, parse_filters
from .schema import ENTITIES, Entity, columns, from_storage, to_storage

__all__ = ["SqliteDataSource", "UnknownColumnError", "UnknownTableError", "entity_for"]

_BY_TABLE = {e.table: e for e in ENTITIES}


class SqliteDataSource(TypedReads):
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
        typed = parse_filters(entity, filters)
        return " AND ".join(f'"{n}" = ?' for n in typed), tuple(to_storage(v) for v in typed.values())

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
