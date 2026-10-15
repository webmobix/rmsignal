"""``/api/market-outlook`` and ``/api/events``: the market view and the event log with derived reach."""

import re
from datetime import date
from typing import Callable

import polars as pl
from fastapi import APIRouter
from pydantic import BaseModel

from rm_dashboard.outlook.contracts import MarketOutlook

from .clientdata import client_rows
from .context import ReadContext
from .deps import AsOf, Ctx
from .models import EventOut, HasGaps, gap

router = APIRouter(prefix="/api", tags=["market"])


class MarketOutlookResponse(HasGaps):
    as_of: date
    outlook: MarketOutlook | None = None


class ReachInstrument(BaseModel):
    instrument_id: str
    instrument_name: str
    held_usd: float


class ReachClient(BaseModel):
    client_id: str
    client_name: str
    held_usd: float


class EventReach(BaseModel):
    derived: bool = True
    matched_channels: list[str]
    unmatched_channels: list[str]
    instruments: list[ReachInstrument]
    clients: list[ReachClient]


class EventWithReach(EventOut):
    reach: EventReach


class EventsResponse(HasGaps):
    as_of: date
    events: list[EventWithReach]


def _blob(i: dict) -> str:
    return " ".join(str(i.get(k) or "") for k in ("instrument_name", "sector", "sub_asset_class", "underlying_reference")).lower()


def _has(*words: str) -> Callable[[dict], bool]:
    return lambda i: any(w in _blob(i) for w in words)


def _tech(i: dict) -> bool:
    return (i.get("sector") == "Information Technology" and i.get("region") == "North America") or "technology" in _blob(i)


def _fixed_income(i: dict) -> bool:
    return i.get("asset_class") == "Fixed Income"


# primary_transmission is free text. These rules link its comma separated channels to instrument attributes. A channel
# that no rule recognises is reported as unmatched; the first matching rule wins, so specific rules come before general ones; the link is a navigation aid and is always marked derived.
CHANNEL_RULES: list[tuple[re.Pattern, Callable[[dict], bool]]] = [
    (re.compile(r"gold|precious metals|inflation hedge|safe haven"), _has("gold", "precious")),
    (re.compile(r"energy|oil|lng"), lambda i: i.get("sector") == "Energy" or _has("energy", "oil", "lng")(i)),
    (re.compile(r"defen[cs]e"), _has("defen")),
    (re.compile(r"airline"), _has("airline", "aviation")),
    (re.compile(r"shipping|transport"), _has("shipping", "transport", "marine", "logistic")),
    (re.compile(r"insurance"), _has("insur")),
    (re.compile(r"em credit|gulf"), lambda i: _has("gulf", "emerging")(i) or (_fixed_income(i) and i.get("region") == "Emerging Markets")),
    (re.compile(r"technology|growth equity|concentrated equity"), _tech),
    (re.compile(r"european fixed income|eur assets"), lambda i: _fixed_income(i) and i.get("region") == "Europe"),
    (re.compile(r"duration|rate-sensitive|fixed income"), _fixed_income),
    (re.compile(r"private credit|semi-liquid|alternatives"), lambda i: i.get("asset_class") == "Alternatives"),
]


def reach_for(transmission: str, held: list[dict]) -> tuple[list[str], list[str], list[dict]]:
    """(matched channels, unmatched channels, held instrument rows reached)."""
    matched, unmatched, hit = [], [], {}
    for ch in [c.strip() for c in transmission.split(",") if c.strip()]:
        rule = next((p for pat, p in CHANNEL_RULES if pat.search(ch.lower())), None)  # first, most specific, rule wins
        found = [i for i in held if rule(i)] if rule else []
        (matched if found else unmatched).append(ch)
        for i in found:
            hit[i["instrument_id"]] = i
    return matched, unmatched, list(hit.values())


def event_rows(ctx: ReadContext, as_of: date) -> list[EventWithReach]:
    ev = ctx.repo.events(as_of=as_of).frame
    if ev.is_empty():
        return []
    h = ctx.repo.holdings(as_of=as_of).frame
    inst = ctx.repo.instruments(as_of=as_of).frame
    held: list[dict] = []
    by_inst: dict[str, pl.DataFrame] = {}
    if h.height and inst.height:
        value = h.group_by("instrument_id").agg(pl.col("market_value_usd").sum().alias("v"))
        vmap = {r["instrument_id"]: r["v"] for r in value.iter_rows(named=True)}
        held = [{**i, "held_usd": vmap[i["instrument_id"]]} for i in inst.iter_rows(named=True) if i["instrument_id"] in vmap]
        by_inst = {k[0]: g for k, g in h.group_by("instrument_id")}
    names = {cid: c["client_name"] for cid, c in client_rows(ctx, as_of).items()}
    out = []
    for e in ev.sort("event_date").iter_rows(named=True):
        matched, unmatched, hit = reach_for(e["primary_transmission"], held)
        per_client: dict[str, float] = {}
        for i in hit:
            for r in by_inst[i["instrument_id"]].iter_rows(named=True):
                per_client[r["client_id"]] = per_client.get(r["client_id"], 0.0) + r["market_value_usd"]
        reach = EventReach(
            matched_channels=matched, unmatched_channels=unmatched,
            instruments=[ReachInstrument(instrument_id=i["instrument_id"], instrument_name=i["instrument_name"], held_usd=i["held_usd"])
                         for i in sorted(hit, key=lambda x: -x["held_usd"])],
            clients=[ReachClient(client_id=c, client_name=names.get(c, c), held_usd=v)
                     for c, v in sorted(per_client.items(), key=lambda kv: -kv[1])])
        out.append(EventWithReach(**{k: e[k] for k in EventOut.model_fields}, reach=reach))
    return out


@router.get("/market-outlook")
def get_market_outlook(ctx: Ctx, as_of: AsOf) -> MarketOutlookResponse:
    outlook = ctx.outlooks.load_market(as_of)
    gaps = [] if outlook else [gap(f"no market outlook persisted at {as_of}; run `rm-dashboard-outlook`", "market")]
    return MarketOutlookResponse(as_of=as_of, outlook=outlook, gaps=gaps)


@router.get("/events")
def get_events(ctx: Ctx, as_of: AsOf) -> EventsResponse:
    rows = event_rows(ctx, as_of)
    return EventsResponse(as_of=as_of, events=rows, gaps=[] if rows else [gap(f"no events up to {as_of}", "events")])
