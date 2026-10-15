"""Request dependencies of the read API: the shared context and ``as_of`` resolution."""

from datetime import date
from typing import Annotated

from fastapi import Depends, HTTPException, Query, Request

from .context import ReadContext

BATCH_HINT = "run `rm-dashboard-analyse`, `rm-dashboard-actions` and `rm-dashboard-overview` to create a run"


def get_context(request: Request) -> ReadContext:
    return request.app.state.read


Ctx = Annotated[ReadContext, Depends(get_context)]


def resolve_as_of(ctx: Ctx, as_of: Annotated[str, Query(description="ISO date or 'latest'")] = "latest") -> date:
    dates = ctx.asof_index.dates()
    if as_of == "latest":
        if not dates:
            raise HTTPException(404, f"no persisted run found; {BATCH_HINT}")
        return dates[-1]
    try:
        d = date.fromisoformat(as_of)
    except ValueError:
        raise HTTPException(422, f"as_of must be an ISO date or 'latest', got {as_of!r}") from None
    if d not in dates:
        avail = ", ".join(x.isoformat() for x in dates) or "none"
        raise HTTPException(404, f"no run for {d}; available dates: {avail}")
    return d


AsOf = Annotated[date, Depends(resolve_as_of)]
