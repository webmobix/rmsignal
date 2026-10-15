"""Read-only debug endpoints over the dataset tables: ``/api/sources``."""

from contextlib import contextmanager
from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder

from ..data.datasource import (
    SqliteDataSource, UnknownColumnError, UnknownTableError, entity_for,
)
from ..data.schema import ENTITIES, ValueParseError, columns

router = APIRouter(prefix="/api/sources", tags=["sources"])

DEFAULT_LIMIT = 100
MAX_LIMIT = 1000
_PAGING = {"limit", "offset"}


@contextmanager
def _datasource(request: Request):
    # Opened inside the endpoint so the sqlite connection stays in one thread.
    ds = SqliteDataSource(request.app.state.db_path)
    try:
        yield ds
    except UnknownTableError as exc:
        names = ", ".join(e.table for e in ENTITIES)
        raise HTTPException(404, f"unknown table {exc.args[0]!r}; valid tables: {names}") from None
    except UnknownColumnError as exc:
        raise HTTPException(422, f"unknown filter parameter {exc.args[0]!r}") from None
    except ValueParseError as exc:
        raise HTTPException(422, str(exc)) from None
    finally:
        ds.close()


def _row(record) -> dict:
    return jsonable_encoder(asdict(record))


@router.get("")
def list_sources(request: Request) -> list[dict]:
    with _datasource(request) as ds:
        return [
            {
                "table": e.table,
                "columns": [
                    {"name": c.name, "type": c.type.__name__, "nullable": c.nullable}
                    for c in columns(e)
                ],
                "primary_key": list(e.primary_key),
                "count": ds.count(e.table),
            }
            for e in ENTITIES
        ]


@router.get("/{table}")
def list_rows(
    request: Request,
    table: str,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict:
    filters = {k: v for k, v in request.query_params.items() if k not in _PAGING}
    with _datasource(request) as ds:
        rows = ds.select(table, filters, limit, offset)
        return {
            "table": table,
            "total": ds.count(table, filters),
            "limit": limit,
            "offset": offset,
            "rows": [_row(r) for r in rows],
        }


@router.get("/{table}/{key:path}")
def get_row(request: Request, table: str, key: str) -> dict:
    with _datasource(request) as ds:
        entity_for(table)
        record = ds.get_by_key(table, tuple(key.split("/")))
        if record is None:
            raise HTTPException(404, f"no row {key!r} in {table}")
        return _row(record)
