"""Domain tools: structured, dated data for clients, portfolios, positions, markets, text and credit."""

from rm_dashboard.domain import Party, QualityFlag

from .envelope import build_result, rows
from .spec import (AsOfOnly, ClientParams, InstrumentParams, Params, PortfolioParams, ToolContext, ToolSpec)

ORGANISATION_MARKER = ("gender", "Entity")
NO_PERSON_SOURCE = "no person source is configured: persons, beneficial owners and family members are unavailable"
NO_RELATIONSHIP_SOURCE = "no related-party source is configured: relationships beyond the client's own portfolios are unavailable"
NO_NEWS_SOURCE = "no news source is configured; curated dated events are returned in data.curated_events"


def _client_rows(ctx: ToolContext, p):
    return ctx.repo.clients(as_of=p.as_of, client_id=p.client_id)


def clients_get(ctx: ToolContext, p: ClientParams):
    pit = _client_rows(ctx, p)
    data = rows(pit)[0] if pit.frame.height else None
    why = None if data else (pit.reason or f"client {p.client_id} not found at {p.as_of}")
    return build_result(tool="clients.get", version="1", params=p, as_of=p.as_of, pits=[pit],
                        data={"client": data, "current_only_attributes": pit.current_only_attributes},
                        status=None if data else "no_data", reason=why)


def clients_list(ctx: ToolContext, p: AsOfOnly):
    pit = ctx.repo.clients(as_of=p.as_of)
    keep = ["client_id", "client_name", "base_currency", "wealth_band", "risk_profile"]
    data = [{k: r[k] for k in keep} for r in rows(pit)]
    return build_result(tool="clients.list", version="1", params=p, as_of=p.as_of, pits=[pit], data=data)


def parties_get(ctx: ToolContext, p: ClientParams):
    pit = _client_rows(ctx, p)
    if not pit.frame.height:
        return build_result(tool="parties.get", version="1", params=p, as_of=p.as_of, pits=[pit], data=None,
                            status="no_data", reason=f"client {p.client_id} not found at {p.as_of}")
    r = rows(pit)[0]
    col, val = ORGANISATION_MARKER
    kind = "organisation" if r.get(col) == val else "individual"
    party = Party(party_id=r["client_id"], kind=kind, name=r["client_name"], country=r["country_of_residence"])
    return build_result(
        tool="parties.get", version="1", params=p, as_of=p.as_of, pits=[pit],
        data={"party": party.model_dump(mode="json"), "relationships": [],
              "relationships_status": "unavailable", "relationships_reason": NO_RELATIONSHIP_SOURCE},
        extra_flags=[QualityFlag(code="related_parties_unavailable", message=NO_RELATIONSHIP_SOURCE)],
    )


def relationships_list(ctx: ToolContext, p: ClientParams):
    return build_result(tool="relationships.list", version="1", params=p, as_of=p.as_of, data=[],
                        status="no_data", reason=NO_RELATIONSHIP_SOURCE)


def persons_list(ctx: ToolContext, p: ClientParams):
    return build_result(tool="persons.list", version="1", params=p, as_of=p.as_of, data=[],
                        status="no_data", reason=NO_PERSON_SOURCE)


def portfolios_list(ctx: ToolContext, p: ClientParams):
    pit = ctx.repo.portfolios(as_of=p.as_of, client_id=p.client_id)
    return build_result(tool="portfolios.list", version="1", params=p, as_of=p.as_of, pits=[pit], data=rows(pit))


def portfolios_get(ctx: ToolContext, p: PortfolioParams):
    pit = ctx.repo.portfolios(as_of=p.as_of, portfolio_id=p.portfolio_id)
    data = rows(pit)[0] if pit.frame.height else None
    return build_result(tool="portfolios.get", version="1", params=p, as_of=p.as_of, pits=[pit], data=data,
                        status=None if data else "no_data",
                        reason=None if data else f"portfolio {p.portfolio_id} not found at {p.as_of}")


POSITION_COLS = [
    "portfolio_id", "instrument_id", "instrument_name", "asset_class", "sub_asset_class", "sector", "region",
    "instrument_ccy", "quantity", "price_local", "market_value_base", "market_value_usd", "weight_pct",
    "cost_basis_base", "unrealised_pnl_base", "lending_value_base", "liquidity_tier", "valuation_date",
    "snapshot_date",
]


def positions_list(ctx: ToolContext, p: PortfolioParams):
    pit = ctx.repo.holdings(as_of=p.as_of, portfolio_id=p.portfolio_id)
    data = [{k: r[k] for k in POSITION_COLS} for r in rows(pit)]
    return build_result(tool="positions.list", version="1", params=p, as_of=p.as_of, pits=[pit], data=data)


def instruments_get(ctx: ToolContext, p: InstrumentParams):
    pit = ctx.repo.instruments(as_of=p.as_of, instrument_ids=[p.instrument_id])
    data = rows(pit)[0] if pit.frame.height else None
    return build_result(tool="instruments.get", version="1", params=p, as_of=p.as_of, pits=[pit], data=data,
                        status=None if data else "no_data",
                        reason=None if data else f"instrument {p.instrument_id} not found")


def instruments_prices(ctx: ToolContext, p: InstrumentParams):
    pit = ctx.repo.instrument_prices(as_of=p.as_of, instrument_id=p.instrument_id)
    return build_result(tool="instruments.prices", version="1", params=p, as_of=p.as_of, pits=[pit], data=rows(pit))


def market_snapshot(ctx: ToolContext, p: AsOfOnly):
    pit = ctx.repo.market_context(as_of=p.as_of)
    return build_result(tool="market.snapshot", version="1", params=p, as_of=p.as_of, pits=[pit], data=rows(pit))


def events_list(ctx: ToolContext, p: AsOfOnly):
    pit = ctx.repo.events(as_of=p.as_of)
    return build_result(tool="events.list", version="1", params=p, as_of=p.as_of, pits=[pit], data=rows(pit))


def news_list(ctx: ToolContext, p: AsOfOnly):
    pit = ctx.repo.events(as_of=p.as_of)
    return build_result(tool="news.list", version="1", params=p, as_of=p.as_of, pits=[pit],
                        data={"news": [], "curated_events": rows(pit)}, status="no_data", reason=NO_NEWS_SOURCE)


def notes_list(ctx: ToolContext, p: ClientParams):
    pit = ctx.repo.notes(as_of=p.as_of, client_id=p.client_id)
    data = [{"note_id": r["note_id"], "note_date": r["note_date"], "channel": r["channel"],
             "quote": r["note"], "source_type": "quoted_text"} for r in rows(pit)]
    return build_result(tool="notes.list", version="1", params=p, as_of=p.as_of, pits=[pit], data=data)


def credit_facilities(ctx: ToolContext, p: ClientParams):
    pit = ctx.repo.facility_snapshots(as_of=p.as_of, client_id=p.client_id)
    terms = ctx.repo.facility_terms(as_of=p.as_of, client_id=p.client_id)
    return build_result(tool="credit.facilities", version="1", params=p, as_of=p.as_of, pits=[terms, pit],
                        data={"facilities": rows(terms), "snapshots": rows(pit)})


def cash_needs_list(ctx: ToolContext, p: ClientParams):
    pit = ctx.repo.cash_needs(as_of=p.as_of, client_id=p.client_id)
    return build_result(tool="cash_needs.list", version="1", params=p, as_of=p.as_of, pits=[pit], data=rows(pit))


def commitments_list(ctx: ToolContext, p: ClientParams):
    pit = ctx.repo.commitments(as_of=p.as_of, client_id=p.client_id)
    return build_result(tool="commitments.list", version="1", params=p, as_of=p.as_of, pits=[pit], data=rows(pit))


def _s(name, desc, params, fn):
    return ToolSpec(name, desc, params, fn, "domain")


DOMAIN_TOOLS = [
    _s("clients.get", "Client profile as of a date. Unversioned attributes are tagged current_only.", ClientParams, clients_get),
    _s("clients.list", "Clients that exist at a date, with a few identifying fields.", AsOfOnly, clients_list),
    _s("parties.get", "The client as a party (individual or organisation) with its relationships list.", ClientParams, parties_get),
    _s("relationships.list", "Related parties of a client. Currently no data source: returns no_data.", ClientParams, relationships_list),
    _s("persons.list", "Persons linked to a client. Currently no data source: returns no_data.", ClientParams, persons_list),
    _s("portfolios.list", "Portfolios of a client with AUM at the effective snapshot.", ClientParams, portfolios_list),
    _s("portfolios.get", "One portfolio with AUM at the effective snapshot.", PortfolioParams, portfolios_get),
    _s("positions.list", "Positions of a portfolio at the effective snapshot, with data-quality flags.", PortfolioParams, positions_list),
    _s("instruments.get", "Instrument reference data.", InstrumentParams, instruments_get),
    _s("instruments.prices", "Instrument price history, one row per snapshot up to as_of.", InstrumentParams, instruments_prices),
    _s("market.snapshot", "Market series (indices, rates, FX, commodities) at the effective snapshot.", AsOfOnly, market_snapshot),
    _s("events.list", "Curated dated events up to as_of.", AsOfOnly, events_list),
    _s("news.list", "News for the period. Currently no news source: returns no_data plus curated events.", AsOfOnly, news_list),
    _s("notes.list", "Relationship-manager notes up to as_of, as dated quoted text.", ClientParams, notes_list),
    _s("credit.facilities", "Credit facilities of a client with figures per snapshot up to as_of.", ClientParams, credit_facilities),
    _s("cash_needs.list", "Planned cash needs of a client with stated certainty.", ClientParams, cash_needs_list),
    _s("commitments.list", "Private-markets commitments of a client.", ClientParams, commitments_list),
]
