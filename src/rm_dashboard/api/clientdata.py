"""Client facts shared by the read endpoints, taken from the point-in-time repository."""

from datetime import date

from .context import ReadContext


def client_rows(ctx: ReadContext, as_of: date) -> dict[str, dict]:
    """client_id -> row (profile fields plus ``aum_usd`` at the effective snapshot)."""
    f = ctx.repo.clients(as_of=as_of).frame
    return {r["client_id"]: r for r in f.iter_rows(named=True)} if f.height else {}
