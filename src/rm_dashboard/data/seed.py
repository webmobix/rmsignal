"""Standalone seeder: load the dataset files into a SQLite database.

    python -m rm_dashboard.data.seed --db rm.db [--data-dir DIR] [--replace]

Uses only the standard library and never imports the app entry point.
"""

import argparse
import csv
import json
import sqlite3
import sys
from pathlib import Path

from . import schema
from .schema import ENTITIES, Entity, ValueParseError

DEFAULT_DATA_DIR = (
    Path(__file__).resolve().parents[3] / "sample" / "singhacks-jb-wealth-intelligence" / "data"
)


class SeedError(Exception):
    """The dataset could not be loaded."""


def _read_rows(entity: Entity, data_dir: Path) -> list[dict]:
    path = data_dir / entity.file
    if not path.is_file():
        raise SeedError(f"{entity.file}: file not found in {data_dir}")
    if path.suffix == ".json":
        try:
            rows = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise SeedError(f"{entity.file}: invalid JSON: {exc}") from None
        header = list(rows[0]) if rows else []
        for i, row in enumerate(rows, start=1):
            if set(row) != set(header):
                raise SeedError(f"{entity.file}: row {i} has different keys from row 1")
    else:
        with path.open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            header = list(reader.fieldnames or [])
            rows = list(reader)
    expected = [c.source for c in schema.columns(entity)]
    if set(header) != set(expected) or len(header) != len(expected):
        missing = sorted(set(expected) - set(header))
        extra = sorted(set(header) - set(expected))
        raise SeedError(f"{entity.file}: header mismatch (missing: {missing}, unexpected: {extra})")
    return rows


def _load(conn: sqlite3.Connection, entity: Entity, rows: list[dict]) -> int:
    cols = schema.columns(entity)
    sql = (
        f'INSERT INTO "{entity.table}" ({", ".join(chr(34) + c.name + chr(34) for c in cols)}) '
        f'VALUES ({", ".join("?" * len(cols))})'
    )
    values = []
    for n, row in enumerate(rows, start=1):
        record = []
        for c in cols:
            try:
                record.append(schema.to_storage(schema.parse_text(c, row[c.source])))
            except ValueParseError as exc:
                raise SeedError(f"{entity.file}: row {n}, column {c.source}: {exc}") from None
        values.append(record)
    try:
        conn.executemany(sql, values)
    except sqlite3.IntegrityError as exc:
        raise SeedError(f"{entity.file}: {exc}") from None
    return len(values)


def seed(db_path: str | Path, data_dir: str | Path = DEFAULT_DATA_DIR, replace: bool = False) -> dict[str, int]:
    """Create the schema and load every dataset file; return rows loaded per table."""
    data_dir, db_path = Path(data_dir), Path(db_path)
    parsed = {e.table: _read_rows(e, data_dir) for e in ENTITIES}  # fail before touching the db
    conn = sqlite3.connect(db_path, isolation_level=None)
    try:
        conn.execute("BEGIN")
        present = schema.existing_tables(conn)
        if present and not replace:
            raise SeedError(
                f"{db_path} already contains tables ({', '.join(sorted(present))}); use --replace to rebuild"
            )
        schema.drop_schema(conn)
        schema.create_schema(conn)
        counts = {e.table: _load(conn, e, parsed[e.table]) for e in ENTITIES}
        conn.execute("COMMIT")
        return counts
    except BaseException:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed a SQLite database from the dataset files.")
    parser.add_argument("--db", required=True, help="path of the SQLite database to create")
    parser.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR), help="directory with the dataset files")
    parser.add_argument("--replace", action="store_true", help="drop and rebuild existing tables")
    args = parser.parse_args(argv)
    try:
        counts = seed(args.db, args.data_dir, args.replace)
    except SeedError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    for table, n in counts.items():
        print(f"{table:<20} {n:>5} rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
