## Purpose

Serves the book, each client with a consolidated view across all of their portfolios, portfolio detail, AuM history and snapshot comparison.

## ADDED Requirements

### Requirement: Client list
`GET /api/clients` SHALL list every client of the RM with id, name, wealth band, booking centre, risk profile, AuM at `as_of`, portfolio count, action count, highest urgency, report status and KYC due date.

#### Scenario: All clients
- **WHEN** a client requests `GET /api/clients` on the committed data
- **THEN** the response contains 20 rows, including clients that have no actions

### Requirement: Consolidated client detail
`GET /api/clients/{id}` SHALL return the client profile, a `consolidated` block computed across all of the client's portfolios, and a `portfolios` list. The consolidated block SHALL contain total AuM and its change since the previous snapshot, combined asset-class allocation, currency exposure, largest positions across portfolios, look-through exposure for structured products, liquidity against commitments and planned cash needs, and credit facilities with headroom.

#### Scenario: Multi-portfolio client
- **WHEN** a client with three portfolios is requested
- **THEN** `consolidated.total_aum_usd` equals the sum of the three portfolio AuMs and the allocation is computed over all holdings

#### Scenario: Single-portfolio client
- **WHEN** a client with one portfolio is requested
- **THEN** `portfolios` has one entry and the consolidated figures equal that portfolio's

### Requirement: Portfolio list on the client
Each entry of `portfolios` SHALL carry id, name, mandate code and name, service model, base currency, AuM at `as_of`, change since the previous snapshot, and a mandate status (`in_band`, `out_of_band`, or `no_mandate` for custody accounts).

#### Scenario: Custody account
- **WHEN** a client holds a custody portfolio
- **THEN** its mandate status is `no_mandate` and it is still included in the consolidated totals

### Requirement: Findings, actions and note checks on the client
The client detail SHALL include the client's actions, the findings of the report with their evidence ids, the note-reconciliation results (`consistent`, `contradicted`, `unverifiable`), and the report status and gaps.

#### Scenario: Contradicted note
- **WHEN** a note is contradicted by the report
- **THEN** the detail lists the note, the verdict, and the evidence ids behind it

### Requirement: AuM history
`GET /api/clients/{id}/aum-history` SHALL return AuM at every snapshot up to `as_of`, per portfolio and in total, and SHALL include the event-log events dated within the covered range, from the first snapshot up to the effective snapshot, both inclusive.

#### Scenario: Five snapshots
- **WHEN** `as_of` is 2026-08-26
- **THEN** the series has five points per portfolio and for the total, from 2025-12-31 to 2026-08-26

### Requirement: Portfolio detail
`GET /api/portfolios/{id}` SHALL return the portfolio header, AuM history, mandate bands (min, target, max) against the actual asset-class weights, holdings at `as_of` with weight, value, unrealised P&L and liquidity tier, the largest-position check against `max_single_position_pct`, and any credit facility secured on it with its LTV history and margin-call trigger.

#### Scenario: Out of band
- **WHEN** an asset class weight exceeds its max
- **THEN** that band is flagged `out_of_band` with the weight and the limit

#### Scenario: Unknown portfolio
- **WHEN** the id does not exist
- **THEN** the response is 404

### Requirement: Snapshot comparison
`GET /api/clients/{id}/snapshot-changes` SHALL accept `from` and `to` snapshot dates (default: previous snapshot and `as_of`) and return AuM change, unrealised P&L change, positions added, removed and resized per portfolio, and the events dated between the two snapshots with their transmission channels.

#### Scenario: Between snapshots
- **WHEN** comparing 2026-02-27 with 2026-03-31
- **THEN** the response lists the changes per portfolio and the Strait of Hormuz events dated in that range

#### Scenario: Invalid snapshot
- **WHEN** `from` or `to` is not a snapshot date or `from` is not before `to`
- **THEN** the response is 422
