"""Reading and validating the dataset files, whatever the target: ``read_dataset`` checks the files and their headers,
``parse_rows`` turns a table's rows into typed records and checks the cells and primary keys. The seed command and the
loader both use these, so an input accepted or rejected by one is accepted or rejected by the other with the same message.

Uses only the standard library, so the seeder can run without the app.
"""

import csv
import json
from pathlib import Path

from . import schema
from .schema import ENTITIES, Entity, ValueParseError

DEFAULT_DATA_DIR = (
    Path(__file__).resolve().parents[3] / "sample" / "singhacks-jb-wealth-intelligence" / "data"
)


class DatasetError(Exception):
    """The dataset could not be read or does not validate. The message names the file, row and column."""


def read_rows(entity: Entity, data_dir: Path) -> list[dict]:
    path = data_dir / entity.file
    if not path.is_file():
        raise DatasetError(f"{entity.file}: file not found in {data_dir}")
    if path.suffix == ".json":
        try:
            rows = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise DatasetError(f"{entity.file}: invalid JSON: {exc}") from None
        header = list(rows[0]) if rows else []
        for i, row in enumerate(rows, start=1):
            if set(row) != set(header):
                raise DatasetError(f"{entity.file}: row {i} has different keys from row 1")
    else:
        with path.open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            header = list(reader.fieldnames or [])
            rows = list(reader)
    expected = [c.source for c in schema.columns(entity)]
    if set(header) != set(expected) or len(header) != len(expected):
        missing = sorted(set(expected) - set(header))
        extra = sorted(set(header) - set(expected))
        raise DatasetError(f"{entity.file}: header mismatch (missing: {missing}, unexpected: {extra})")
    return rows


def read_dataset(data_dir: str | Path = DEFAULT_DATA_DIR) -> dict[str, list[dict]]:
    """The raw rows of every table; fails on the first missing, unreadable or mis-headed file."""
    data_dir = Path(data_dir)
    return {e.table: read_rows(e, data_dir) for e in ENTITIES}


def parse_rows(entity: Entity, rows: list[dict]) -> list:
    """Typed records, in file order. Fails on the first bad cell or repeated primary key, naming file, row and column."""
    cols = schema.columns(entity)
    records = []
    for n, row in enumerate(rows, start=1):
        values = []
        for c in cols:
            try:
                values.append(schema.parse_text(c, row[c.source]))
            except ValueParseError as exc:
                raise DatasetError(f"{entity.file}: row {n}, column {c.source}: {exc}") from None
        records.append(entity.model(*values))
    if entity.primary_key:
        seen: set[tuple] = set()
        for rec in records:
            key = tuple(getattr(rec, k) for k in entity.primary_key)
            if key in seen:
                where = ", ".join(f"{entity.table}.{k}" for k in entity.primary_key)
                raise DatasetError(f"{entity.file}: UNIQUE constraint failed: {where}")
            seen.add(key)
    return records


def parse_dataset(data_dir: str | Path = DEFAULT_DATA_DIR) -> dict[str, list]:
    """Typed records per table for the whole dataset, fully validated."""
    raw = read_dataset(data_dir)
    return {e.table: parse_rows(e, raw[e.table]) for e in ENTITIES}
