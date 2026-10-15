# instrument-market-api Specification

## Purpose

Serves instruments with what the book holds, the market outlook, and the event log with derived reach to instruments and clients.

## Requirements

### Requirement: Instrument list
`GET /api/instruments` SHALL list the instruments of the master with id, name, asset class, sub-asset class, sector, region, currency, liquidity tier, latest price and change since the previous snapshot, the number of the RM's portfolios holding it and the total USD held, and whether an outlook exists for the `as_of`.

#### Scenario: Held and outlooked
- **WHEN** the list is requested on the committed data
- **THEN** every instrument appears, `has_outlook` is true for the two outlooked instruments, and `held_usd` is zero for instruments no portfolio holds

### Requirement: Instrument detail
`GET /api/instruments/{id}` SHALL return master data including `underlying_reference` and the sustainability and concentration flags, the price path over all snapshots, the holders (client, portfolio, weight, value), and the instrument outlook when one exists, with its market-outlook context and evidence ids.

#### Scenario: Structured product
- **WHEN** a structured product is requested
- **THEN** its `underlying_reference` is present, as are the holders

#### Scenario: No outlook
- **WHEN** no outlook was persisted for the instrument
- **THEN** `outlook` is null and a gap `outlook_missing` is listed

#### Scenario: Unknown instrument
- **WHEN** the id does not exist
- **THEN** the response is 404

### Requirement: Market outlook
`GET /api/market-outlook` SHALL return the persisted market outlook for the `as_of`: summary, views, the inputs it used, what changed since the previous outlook, events not yet addressed, gaps and evidence ids.

#### Scenario: Committed run
- **WHEN** requested on the 2026-08-26 run
- **THEN** the response contains the summary and views of `outlook/market.json`

### Requirement: Event log with reach
`GET /api/events` SHALL return the event log up to `as_of` with date, type, region, description, severity and transmission channels, and for each event the clients and instruments it plausibly reaches, derived from the channel text and the holdings, marked as `derived`.

#### Scenario: Linked
- **WHEN** an event names an energy channel
- **THEN** it lists the held instruments tagged to that channel and their clients, with `derived: true`
