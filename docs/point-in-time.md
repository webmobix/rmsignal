# Point-in-time contract

`rm_dashboard.pit.PolarsPitRepository` is the only read path analysis code uses for wealth data.

- **`as_of` is mandatory.** Every method takes a keyword-only `as_of: date` with no default.
  A missing argument is a `TypeError`; `None`, strings or datetimes raise `AsOfError`.
  No module under `src/` reads the wall clock (enforced by `tests/test_pit.py`), so the same
  query returns the same answer on any calendar day.
- **Snapshot-dated data** (holdings, AUM, instrument prices, facility figures, market context)
  resolves to the latest snapshot on or before `as_of`. Results carry `effective_snapshot_date`
  and `gap_days`; a gap raises a `snapshot_lag` flag. Before the first snapshot the result is
  `insufficient_data` with no rows. Price, AUM and facility history return one row per snapshot
  up to the effective one.
- **Event-dated data** (transactions, events, RM notes) is returned only when its own date is
  on or before `as_of`.
- **Unversioned attributes** (risk profile, mandate bands, KYC review date, tax domicile,
  benchmark, instrument classification) are tagged `pit: current_only`, list the affected
  attributes in `current_only_attributes`, and raise a `current_only` flag.
- **Planned cash needs and commitments** have no creation date, only a future due window. Rule: a
  need without a recorded knowledge date is assumed to have existed since the start of the client
  relationship (`client_since`). It is available from that date onwards and is never dropped for a
  later `as_of`, so advice always sees the needs. Results carry an
  `assumed_known_since_relationship_start` flag and `pit: current_only`.

## Quality flags

| Code | Rule (see `pit/config.py`) |
|---|---|
| `stale_mark` | `valuation_date` earlier than `snapshot_date` |
| `missing_cost_basis` | no cost basis; position excluded from P&L |
| `mid_period_position` | position absent from the previous snapshot of a portfolio that existed then |
| `bond_nominal_unit` | quantity in units of 100 nominal |
| `subscription_currency_mismatch` | subscription settled in a currency other than the portfolio base |
| `facility_drawdown_mismatch` | rise in drawn amount between snapshots differs from booked drawdowns |
| `snapshot_lag` | `as_of` later than the effective snapshot |
| `current_only`, `assumed_known_since_relationship_start` | see above |

Flags state the facts and never alter the data. Thresholds and type names are configuration.

## Production path

Bitemporal storage (valid time plus knowledge time) would replace `current_only` tagging.
The `PitRepository` protocol lets a warehouse implementation replace the Polars one.
