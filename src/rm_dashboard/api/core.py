"""``/api/as-of`` and ``/api/rm``: which dates exist and who the dashboard is for."""

from fastapi import APIRouter, HTTPException

from rm_dashboard.overview.source import rms_at

from .deps import AsOf, Ctx
from .models import AsOfResponse, RmProfile

router = APIRouter(prefix="/api", tags=["core"])


@router.get("/as-of")
def as_of_dates(ctx: Ctx) -> AsOfResponse:
    dates = ctx.asof_index.dates()
    return AsOfResponse(as_of_dates=dates, latest=dates[-1] if dates else None)


@router.get("/rm")
def rm_profile(ctx: Ctx, as_of: AsOf) -> RmProfile:
    clients = ctx.repo.clients(as_of=as_of)
    rms = rms_at(ctx.repo, as_of)
    if not rms:
        raise HTTPException(404, f"no clients at {as_of}")
    rm = next(iter(rms.values()))
    rows = [r for r in clients.frame.iter_rows(named=True) if r["rm_id"] == rm.rm_id]
    return RmProfile(
        as_of=as_of, rm_id=rm.rm_id, rm_name=rm.rm_name, rm_desk=rows[0]["rm_desk"],
        booking_centres=sorted({r["booking_centre"] for r in rows}),
        client_count=len(rm.clients), total_aum_usd=sum(c.aum_usd for c in rm.clients),
    )
