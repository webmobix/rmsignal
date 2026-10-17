# Read API

Read-only HTTP API for the RM dashboard, next to the raw table endpoints under `/api/sources`.
Interactive documentation with every response schema is served at `/docs`; the OpenAPI document
(used to generate the UI types) at `/openapi.json`.

```sh
uv run rm-dashboard-serve --db rm.db --reports reports            # port 8000
RM_DASHBOARD_DB=rm.db RM_DASHBOARD_REPORTS=reports uv run rm-dashboard-serve
```

`--reports` (default `reports`, or `$RM_DASHBOARD_REPORTS`) is the folder of persisted runs,
`<reports>/<as_of>/...`. The server exits with a message naming the folder when it does not exist.
There is no CORS and no authentication: the UI reaches the API through a dev proxy or the same origin.

## Conventions

- **`as_of`.** Every endpoint except `/api/sources` takes `?as_of=<ISO date>|latest` (default `latest`).
  `latest` is the newest run folder under the reports folder; the wall clock is never read. An unknown
  date answers 404 and lists the available dates; with no runs at all the data endpoints answer 404 and
  name the batch commands.
- **Read-only.** Only GET exists. POST, PUT, PATCH and DELETE answer 405.
- **Gaps are data.** A section that cannot be produced (missing report, missing outlook, too little
  history) is returned empty with an entry in `gaps` (`kind`, `description`, `subject`). The endpoint does
  not answer 500 and no value is invented.
  A gap is a note about what the analysis could not do or had to drop, not an error of the dashboard. `kind`
  is one of `no_data` (the input was absent at `as_of`), `tool_error` (a computation failed or got invalid
  arguments), `policy_denied` (a policy checkpoint refused the step), `guard_removed` (the output guard removed
  a model claim, action or theme that lacked evidence, a valid figure or a rationale), `agent_error` (the model
  step failed or returned unusable output) and `other`. The UI shows them as a quiet "Data gap" list at the
  end of the page (on the call sheet, at the end of the affected section), after the content they qualify.
- **Placeholders.** A payload that is not computed by the analysis layer carries `"status": "placeholder"` at
  its top level. A UI must mark it as illustrative.
- **Point in time.** Figures are read through the point-in-time repository with an explicit `as_of`, so
  they equal what the analysis layer saw on that date.

## Core

| Endpoint | Returns |
|---|---|
| `GET /api/as-of` | `{"as_of_dates": [...], "latest": "2026-08-26"}` |
| `GET /api/rm` | RM id, name, desk, booking centres, client count and total AuM for the avatar and masthead |

```sh
curl localhost:8000/api/rm
# {"as_of":"2026-08-26","rm_id":"RM-SG-014","rm_name":"Priscilla Ong","rm_desk":"...","booking_centres":["Hong Kong","Singapore"],...}
```

## Overview, meeting prep, evidence

| Endpoint | Returns |
|---|---|
| `GET /api/overview` | the persisted RM overview plus `client_rows`, `total_aum_usd` and `meeting_prep` |
| `GET /api/evidence/{evidence_id}` | the stored tool result and everything that cites it |

`/api/overview` returns the overview of `reports/<as_of>/overview/<rm>.json` unchanged in content (summary, themes, ranked
`actions`, `by_category`, `clients_without_actions`, `gaps`). Each action additionally carries:

- `client_aum_usd` and `wealth_band` of its client, so a chart needs no second request;
- `urgency`, a number from 4 to 98 (below);
- `refs`: its source references resolved to `client_id`, optional `portfolio_id`, the finding's `claim` and `evidence_ids`.
  `CL-0001/PF-0001#f8` arrives as client `CL-0001`, portfolio `PF-0001`; nothing needs parsing.

`client_rows` has one row per client (also those without actions): `aum_usd`, `wealth_band`, `action_count`,
`top_importance` and `max_urgency` (0 when there is no action). These count only the client's own actions
(`origin: "client_actions"`). For a client without persisted actions the overview adds one placeholder action (`origin: "coverage"`,
id `CL-xxxx-COVER`, "Missing next actions despite an analysis report"): it stays in `actions`, since the overview contains all
actions, but it is not counted, so such a client has `action_count` 0 and sits at the baseline of a chart. When no overview was persisted for the date the
response is still delivered with `status: "insufficient_data"` and a gap naming `rm-dashboard-overview`.

### Urgency

`urgency` spreads a chart axis; it does not reorder the overview, whose rank is the persisted one. It is the importance base
plus the horizon bonus plus a due-date term of 0 to 3 that fades linearly to zero over 365 days (overdue and same-day take all 3)
plus a rank term of 0 to 9, from 9 for the first action of its importance tier in the persisted overview down to 0 for the last, which separates actions of the same tier and horizon.

| importance | base | | horizon | bonus |
|---|---|---|---|---|
| `critical` | 76 | | `immediate` | 10 |
| `high` | 52 | | `within_30_days` | 7 |
| `medium` | 28 | | `within_90_days` | 4 |
| `low` | 4 | | `later`, `none` | 0 |

Tiers are 24 apart and the additions total at most 22, so a higher tier always scores higher.

### Meeting prep

`meeting_prep` covers the 14 days after `as_of` (`from_date`, `to_date`). A client is listed with its `items` when an action
has horizon `immediate` or a due date up to the end of the window (overdue ones included), or its KYC review is due by then
(`status` is `due` or `overdue`), together with its most recent RM note (`note_id`, `note_date`, `channel`, `note`).

### Evidence

`GET /api/evidence/{evidence_id}` searches the stored evidence of the date (client evidence and outlook evidence) and returns
`result` (the `ToolResult`: tool, parameters, data, sources, flags) and `cited_by`, the findings, actions and market or
instrument views that cite it, each with its reference and, where it has them, `client_id`, `portfolio_id`, `instrument_id`.
An unknown id answers 404.

## Clients, portfolios, snapshot comparison

| Endpoint | Returns |
|---|---|
| `GET /api/clients` | one row per client of the RM |
| `GET /api/clients/{client_id}` | profile, `consolidated` block, `portfolios` list, actions, findings, notes |
| `GET /api/clients/{client_id}/aum-history` | AuM at every snapshot, per portfolio and in total, with the events in range |
| `GET /api/clients/{client_id}/snapshot-changes` | what changed between two snapshots (`?from=&to=`) |
| `GET /api/portfolios/{portfolio_id}` | header, AuM history, mandate bands, holdings, sector exposure, position limit, facilities |
| `GET /api/portfolios/{portfolio_id}/call-sheet` | seven sections for a client call: performance, mandate, ownership, bank view, events, cash and credit, conversation |

**Currency.** The dataset's `aum_<date>` per portfolio is in the portfolio's base currency, so portfolios of one client cannot be
added up. Every sum across portfolios in the API is of `market_value_usd` and named `*_usd`; `aum_base` and `base_currency` are
given beside it. Profit and loss stays in the portfolio base currency (`pnl_base_*`), per portfolio, and is never summed.

**`/api/clients`.** `client_id`, `client_name`, `wealth_band`, `booking_centre`, `risk_profile`, `aum_usd`, `portfolio_count`,
`action_count`, `top_importance`, `max_urgency`, `report_status` (`complete`, `partial`, `insufficient_data` or `missing`),
`kyc_review_due`, `kyc_overdue`. All clients are listed, also those without actions.

**`/api/clients/{id}`.** The `consolidated` block is computed over all of the client's portfolios, custody included:

| Field | Meaning |
|---|---|
| `total_aum_usd`, `previous_aum_usd`, `change_usd`, `change_pct` | against the previous snapshot |
| `allocation`, `currency_exposure` | slices (`key`, `value_usd`, `weight_pct`) by asset class and instrument currency |
| `top_positions` | the ten largest instruments across portfolios, with the portfolios holding them |
| `look_through`, `hhi` | exposure per entity with structured products looked through to their underlyings (`via_look_through`), from the `concentration` analytic |
| `liquidity` | assets by liquidity tier, planned cash needs and uncalled commitments within 365 days, coverage and shortfall, from the `liquidity_coverage` analytic |
| `facilities` | credit facilities with the current point, the gap to the margin-call trigger (`ltv_gap_pp`) and the LTV history |

`portfolios[]` has one entry per portfolio: `aum_usd`, `aum_base`, `change_pct` against the previous snapshot, `mandate_status`
(`in_band`, `out_of_band`, or `no_mandate` for custody accounts, which are not measured against a mandate) and `breach_count`
(band, single-position and exclusion breaches). `breach_reconciliation[]` lists, from the persisted
`mandate-reconciliation/<client>.json`, each breach of the portfolio as `kind` (`band`, `position`, `exclusion`), `key`, `status`
(`no_note`, `acknowledged`, `client_directed`, `contradicted`) and `note_ids`; it is empty, with a gap
(`no mandate reconciliation persisted for <client>`), when no file exists for the date.
A client with one portfolio has a list of one and consolidated figures equal to it.
`actions` (a client without persisted actions has a gap whose description starts with `actions_missing`), `findings` (flattened report findings with `client_id`, `portfolio_id`, `evidence_ids`) and `notes` follow. A note
carries the reconciliation `verdict` (`consistent`, `contradicted`, `unverifiable`) with its `finding_refs` and `evidence_ids`;
without a persisted reconciliation the verdict is null and a gap says so. Anything that cannot be produced is a gap, not an error.

**`/api/clients/{id}/aum-history`.** `total` and one series per portfolio (`points` of `snapshot_date`, `aum_usd`), and the
`events` dated from the first snapshot up to the effective one, both inclusive.

**`/api/clients/{id}/snapshot-changes`.** `from` and `to` must be snapshot dates with `from` before `to` and `to` not after the
effective snapshot; anything else is 422. Without them the comparison is the previous snapshot against the effective one.
Per portfolio: `aum_usd_from/to`, `change_usd`, `pnl_base_from/to`, and `positions` that were `added`, `removed` or `resized`
(unchanged positions are left out). `events` are those dated after `from` up to and including `to`.

**`/api/portfolios/{id}`.** `bands` give `min_pct`, `target_pct`, `max_pct` and the actual `weight_pct`; `out_of_band` is true
when the weight is outside them (`breach` says which side). `position_limit` has the mandate's `max_single_position_pct`, the
largest position, and the positions over the limit (only instruments flagged `concentration_limit_applies` are compared). A custody
account has no bands and says why. `holdings` are the positions at the effective snapshot, `facilities` those secured on the
portfolio, with the LTV history.

`exclusion_breaches[]` lists the instruments the mandate's binding exclusions rule out (`instrument_id`, `instrument_name`, `held`
= `direct` or `look_through` with `via_instrument_*`, `value`, `weight_pct`) with their reconciliation `status` and `note_ids`;
it is empty for mandates without binding exclusions and for custody accounts. `breach_reconciliation[]` repeats the portfolio's
breach statuses and adds, per breach, its `description`, the `rationale`, `waiver_claimed` and the quoted `notes`
(`note_id`, `note_date`, `quote`). A waiver is the RM's claim: the breach stays listed and `out_of_band`.

`sector_exposure` has `denominator` (the portfolio value in base currency) with its `denominator_label`, and two lists of groups,
`direct` (each position by its instrument's sector) and `look_through` (structured products replaced by their underlyings, each
classified by the sector of the instrument it matches by normalised name). A group has `name`, `value`, `exposure_pct`, `positions`
and, in the look-through view, the `contributors` (structured products) behind it. Both lists sum to 100. Value that cannot be
classified is `unclassified` (position without a sector) or `Unclassified (look-through)` (underlying matching no instrument, or
a product whose underlying is not identifiable); a gap names each product and underlying. Sector labels that are asset types
(`Diversified`, `Corporate`, `Sovereign`, `Cash`, `Gold`, `Multi`, `Macro`) are their own groups. `basket_attribution_assumption`
is true when a basket product's value was split equally across its underlyings. Informational: no sector limit exists in the
mandates. A portfolio without positions has empty lists and a gap.

**`/api/portfolios/{id}/call-sheet`.** Everything for a client call about one portfolio in one read-only response, built from
the seeded data and persisted output; no model is called and no batch stage is started. It returns the portfolio header and
seven sections, each with its own `gaps`; a section that cannot be built is empty with a gap and the others are unchanged.
An unknown portfolio is 404.

| Section | Content |
|---|---|
| `performance` | value and change since the previous snapshot, `contributors` (up to five positions with the largest value change, with amounts), report `findings` that concern the portfolio (with refs), `events` dated between the two snapshots; no persisted report gives no findings and a gap |
| `mandate` | `bands`, `position_limit`, `exclusion_breaches`, `breach_reconciliation` (status, note ids, quoted notes, `waiver_claimed`) and `open_actions` linked to the portfolio; a custody account has `applicable: false` and a `statement`; without a mandate reconciliation file a gap says none was persisted |
| `ownership` | `sector_exposure` (direct and look-through, the same object as the portfolio detail) and the unclassified share of each view |
| `bank_view` | one `entries[]` item for **every** position: `outlook` is the instrument outlook dated `as_of` or the latest earlier one (`as_of` of the outlook, `older_than_as_of`, `view` with direction, horizon, confidence, reasons, and the stored `market_context`), or `null` with an `outlook_missing` gap. These are the bank's view as of their date, not advice |
| `events` | events up to `as_of` matching a held instrument (region, sector, asset class, sub-asset class, name or underlying), grouped by event with the `instruments` concerned and what each `matched_on`; ordered by severity, then date |
| `cash_credit` | `facilities` secured on the portfolio (LTV, trigger, headroom) and `client_liquidity` against planned needs and commitments, marked client level in `client_level_note` |
| `conversation` | the client's latest `notes` (newest first, up to `note_limit`, out of `note_total`; none after `as_of`; none is not a gap) and open `commitments`, marked client level |


## Instruments, market outlook, events

| Endpoint | Returns |
|---|---|
| `GET /api/instruments` | every instrument of the master with what the book holds |
| `GET /api/instruments/{instrument_id}` | master data, price path, holders and the outlook where one exists |
| `GET /api/market-outlook` | the persisted market outlook |
| `GET /api/events` | the event log up to `as_of`, each event with its derived reach |

**`/api/instruments`.** `instrument_id`, `instrument_name`, `asset_class`, `sub_asset_class`, `sector`, `region`, `currency`,
`liquidity_tier`, `latest_price`, `previous_price`, `price_change_pct` (against the previous snapshot), `holder_portfolios`,
`holder_clients`, `held_usd` (across the RM's book, zero when nobody holds it) and `has_outlook`.

**`/api/instruments/{id}`.** The row as `instrument`, plus `underlying_reference` (for a structured product, what it is
actually exposed to), `sustainability_excluded`, `concentration_limit_applies`, `price_path` (every snapshot up to the
effective one), `holders` (client, portfolio, `quantity`, `value_usd`, `weight_pct`) and `outlook`, the persisted
instrument outlook with its market context and evidence ids. Without an outlook, `outlook` is null and a gap whose description starts
with `outlook_missing` says so. An unknown id answers 404.

**`/api/market-outlook`.** `{"as_of", "outlook", "gaps"}`: `outlook` is the persisted market outlook unchanged (`summary`, `views`
with drivers, risks and what would change them, `inputs`, `changes_summary`, `unaddressed_events`, `evidence_ids`); it is null
with a gap when none was persisted for the date.

**`/api/events`.** Each event has `event_date`, `event_type`, `region`, `description`, `severity`, `primary_transmission` and
`reach`. `primary_transmission` is free text, so the reach is derived: each comma separated channel is matched to instrument
attributes by the first rule of the table below that recognises it (specific rules come first, so "European fixed income" does not also
reach all fixed income) and to the instruments the book holds at the effective snapshot; `clients` are the holders of
those instruments with the USD they hold. `reach` has `derived` (always true), `matched_channels` and `unmatched_channels`
(which channels were recognised), `instruments` and `clients`. It is a navigation aid, not analysis.

| Channel text contains | Instruments reached |
|---|---|
| gold, precious metals, inflation hedge, safe haven | name, sector or sub-asset class mentions gold or precious |
| energy, oil, lng | sector Energy, or the name or underlying mentions energy, oil or LNG |
| defence | mentions defence |
| airline | mentions airline or aviation |
| shipping, transport | mentions shipping, transport, marine or logistics |
| insurance | mentions insurance |
| EM credit, Gulf | mentions Gulf or emerging, or Emerging Markets fixed income |
| technology, growth equity, concentrated equity | North American Information Technology, or mentions technology |
| European fixed income, EUR assets | fixed income in Europe |
| duration, rate-sensitive, fixed income | asset class Fixed Income |
| private credit, semi-liquid, alternatives | asset class Alternatives |

## Scenarios (placeholder)

| Endpoint | Returns |
|---|---|
| `GET /api/scenarios` | the scenario catalogue |
| `GET /api/clients/{client_id}/scenarios` | one result per catalogue scenario for the client |

There is no scenario engine yet. These endpoints return fixed placeholder data in the final contract shape so that a UI can be built
now. Every payload carries `"status": "placeholder"` and a `note` saying the content is illustrative; a UI must mark it so and must
not style it as a real breach. The values are **not** computed from the client's holdings: two clients get identical results.

Scenario names, premises and caveats are defined by the backend only. The catalogue holds `scenario_id`, `name`, `premise`,
`mirrors` (the event-log entry the scenario is drawn from, as `Event log <date>: ...`) and `caveat`.

A result adds, per scenario: `status`, `note`, `before_usd`, `after_usd`, `delta_usd`, `delta_pct`, `reached_pct` (share of
wealth the stated channels reach), `untouched_count` (holdings no channel reaches), `collateral` (per facility `ltv_before_pct`,
`ltv_after_pct`, `trigger_pct`, `breaches`, `shortfall_usd`), `bands` (mandate bands crossed: `before_pct`, `after_pct`,
`band_min_pct`, `band_max_pct`, `crosses` as `out` or `in`) and `positions` (`instrument`, `asset_class`, `weight_pct`,
`move_pct`, `delta_usd` and the `channels` it moved down, each with `channel`, `pct`, `why`).

The producer is a `ScenarioProvider` (`catalogue(as_of)`, `for_client(client_id, as_of)`, and a `status`), passed to `create_app`.
`PlaceholderScenarioProvider` is the default. A computed provider with `status = "computed"` replaces it without a change to
routes or response models; the top-level `status` then reads `computed` and the `note` is empty.
