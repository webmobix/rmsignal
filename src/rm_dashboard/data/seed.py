"""Standalone seeder: load the dataset files into a SQLite database.

    python -m rm_dashboard.data.seed --db rm.db [--data-dir DIR] [--replace]

Uses only the standard library and never imports the app entry point.
"""

import argparse
import sqlite3
import sys
from pathlib import Path

from . import schema
from .dataset import DEFAULT_DATA_DIR, DatasetError, parse_dataset
from .schema import ENTITIES, Entity

SeedError = DatasetError
"""The dataset could not be loaded."""


def _load(conn: sqlite3.Connection, entity: Entity, records: list) -> int:
    cols = schema.columns(entity)
    sql = (
        f'INSERT INTO "{entity.table}" ({", ".join(chr(34) + c.name + chr(34) for c in cols)}) '
        f'VALUES ({", ".join("?" * len(cols))})'
    )
    values = [[schema.to_storage(getattr(rec, c.name)) for c in cols] for rec in records]
    try:
        conn.executemany(sql, values)
    except sqlite3.IntegrityError as exc:
        raise SeedError(f"{entity.file}: {exc}") from None
    return len(values)


def seed(db_path: str | Path, data_dir: str | Path = DEFAULT_DATA_DIR, replace: bool = False) -> dict[str, int]:
    """Create the schema and load every dataset file; return rows loaded per table."""
    data_dir, db_path = Path(data_dir), Path(db_path)
    parsed = parse_dataset(data_dir)  # fail on a bad file, cell or key before touching the db
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
