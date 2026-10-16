# Agents

Client analysis is done by two analysts (the Relationship Analyst is the RM's view of one client; it does not infer other persons), each a Deep Agents graph (LangGraph underneath) with a narrow tool allow-list:

```
Relationship Analyst  --task-->  Portfolio Analyst  --reads-->  instrument outlooks (once per date, shared)
 client, concentration,           composition, mandate bands,    market outlook
 liquidity, credit, notes,        P&L, change, the bank's view
 the market outlook               of its largest positions
```

The Portfolio Analyst no longer delegates to an Instrument Analyst: what is known about an instrument is written once per
date by the outlook stage (see *Instrument outlook* below) and read by every client analysis. The `instrument_analyst`
role still exists for interactive sessions and A2A.

The whole landscape (every agent, the runners that call them, tools per agent and A2A) is mapped in [architecture.md](architecture.md).

Code: `rm_dashboard.agents` (`analyst.py` builds, runs and assembles; `stubplans.py` scripts the test model).

## How a run works

1. `analyse(role, subject, scope, models)` takes a subject and the run's `as_of`. The date is part of the
   run (`RunContext.as_of`); the model never sees a date parameter and cannot choose one.
2. Entitlement checkpoint, then a check that data exists at `as_of`. If not, a report with status
   `insufficient_data` is returned and no model is called.
3. The agent is compiled with: the allow-listed tools (one LangChain tool per `ToolSpec`, routed through
   `Toolbox.call` so policy, audit and the evidence store apply), `AllowListMiddleware` (the model sees only the
   allow-list plus `task`; Deep Agents' filesystem, planning and general-purpose tools are never shown or
   executed), `PrivacyMiddleware` (every model call passes the PII checkpoint and the pseudonymiser, tool
   results included), and one `CompiledSubAgent` per delegate that runs the child analyst through the same pipeline.
   Events and news from tools are treated as established facts: used and cited as reasons, weighted by severity. The
   curated event log is the MVP news source (`news.list`); an external feed can later be added behind the same tool.
4. The model's final answer is JSON: a summary and findings (`claim`, `confidence`, `evidence_ids`).
5. Deterministic code takes over: the **output guard** drops any finding that cites evidence not produced in this
   run or contains a number absent from the cited results (tolerance: 0.5% relative or the displayed rounding;
   ids, dates and pseudonyms are ignored; `%`, `m`, `bn`, `k` and thousands separators are normalised); gaps
   are collected (tool errors, denials, guard removals, `no_data` results); flags come from cited evidence;
   status derives from gaps (`complete`, `partial`; `insufficient_data` when core data is absent); report
   assembly checkpoints run; pseudonyms are restored last.
6. Whatever goes wrong inside (tool exception, policy denial, model failure, unparsable output), a `Report` is returned
   with the failure as a gap.

## Outlooks in the client analysis

The outlook stage runs first; the client analysts only read its files:

```
rm-dashboard-outlook -> rm-dashboard-analyse -> rm-dashboard-reconcile -> rm-dashboard-actions -> rm-dashboard-overview
```

- **Tools.** `outlook.market` (Relationship and Portfolio Analyst) and `outlook.instrument` (Portfolio Analyst) are
  read-only: they never start an outlook run and accept no path. They return the latest outlook **not after the run's
  `as_of`** (a later one is never used) with the date it is effective from; an older one carries a `stale_outlook` flag.
- **Evidence continuity.** The tool result carries the view, drivers and risks, and the evidence the outlook cites is
  made resolvable in the run (same ids), so a finding can cite the outlook result or the reason behind it, and the output
  guard still checks every figure.
- **The bank's view, not a fact.** Every outlook result carries a `house_view` flag, which reaches the report through the
  evidence a finding cites. Findings state it as "the bank's view as of <date>" with direction, horizon and confidence.
- **Missing outlook.** `no_data` with the instrument named and a pointer to the command; the report is `partial` with one
  gap per missing outlook and states no forward-looking view for it.
- **No effect on actions.** The importance rubric reads only structured evidence (KYC, LTV, liquidity, mandate,
  concentration), so an outlook can never raise an action's importance.

## LLM call log

Every runner logs each model call and a closing summary, to the console (stderr) and to `run.log` beside its `audit.jsonl`
(`reports/<as_of>/run.log`, `.../reconciliation/`, `.../actions/`, `.../overview/`, `.../outlook/`). Python's standard
`logging` is used; `RM_LOG_LEVEL` sets the level (default `INFO`). Code: `rm_dashboard/llmlog.py`.

```
2026-10-16 08:07:13,270 INFO llm_call runner=analyse run_id=run_ca8fb555680b thread_id=thread_dfcaecf5d2d1 agent=relationship_analyst subject=CL-0001 ms=1 in=670 out=276 total=946 outcome=ok
2026-10-16 08:07:13,453 INFO llm_summary runner=analyse elapsed_s=0.253 llm_s=0.001 calls=21 failed=0 in=51789 out=4055 total=55844 without_usage=0
```

- **Grouping.** `thread_id` is created once per top-level graph run (per client, per instrument, per interactive session) and is
  shared by its sub-agents and anything called from its tools: filter by it to see one run's calls. `run_id` is the audit run id.
- **Summary.** Elapsed wall time, calls, failures, input/output/total tokens, the slowest call and the same per agent
  (`llm_summary*` lines). Tokens a provider did not report show as `n/a` and are counted in `without_usage`, never as zero.
  A `WARNING` line is added when a call failed or reported no usage.
- **`summary.json`** gets an `llm` object with the counts and tokens only. Durations stay in the log so that a rerun on the same
  inputs is byte-identical. A run with no model call (an unchanged outlook) prints its summary to the console and leaves `run.log` as it was.
- **No content.** Prompts, responses and tool arguments are never logged, only ids, durations and counts. The audit trail is unchanged.

## Note reconciliation

A second stage, run after the batch, checks what the RM's notes say about a client against what the client's report
shows. It is not an analyst: it has no analytics tools and does not change the batch reports.

- **Scope is RM notes only.** Every result has `kind: "rm_note"`. Mandate, limit and policy compliance are not
  assessed here; they are a different source of truth and will be reconciled by separate capabilities later,
  writing their own files (`kind` is a closed set so those can be added without changing this output).
- **Input:** the client's persisted `reports/<as_of>/<client>.json` flattened to findings with stable refs
  (`CL-0001#f7`, `CL-0001/PF-0001#f3`), its `evidence/<client>.json`, and the notes dated on or before `as_of`
  read through the `notes.list` tool (point-in-time, policy and audit apply). One model call per client; names are
  pseudonymised before the call and restored in the output.
- **Output:** `reports/<as_of>/reconciliation/<client>.json`, one result per note: `consistent`, `contradicted` or
  `unverifiable`, the note quote (taken from the data, never from the model), a rationale, the finding refs and the
  evidence ids. `summary.json` and `audit.jsonl` sit beside them.
- **Code decides what a verdict may rest on** (`reconciliation/guard.py`): refs must resolve to findings of this
  client; evidence ids are copied from those findings, not from the model; `consistent` or `contradicted` without
  resolvable evidence becomes `unverifiable`; a figure in the rationale must appear in the cited evidence or in the note
  itself (a note's figure may be quoted, never used as data), otherwise the assessment is replaced by `unverifiable`
  and a `guard_removed` gap is recorded; results for unknown notes or notes after `as_of` are dropped; a note the model
  skipped is added as `unverifiable`.
- **Always delivered:** model failure or unparsable output gives every note `unverifiable` and a `partial` status; a
  missing report or evidence file gives `insufficient_data`; a client with no notes at `as_of` gives an empty, `complete`
  reconciliation.

```sh
uv run rm-dashboard-analyse --as-of 2026-08-26 --db rm.db --out reports
uv run rm-dashboard-reconcile --as-of 2026-08-26 --db rm.db --reports-dir reports
```

## Client actions

A third stage turns one client's report (and, when present, its note reconciliation) into the concrete next steps for
the RM. It has no tools, sees only that client's content, and runs per client in parallel like the batch.

- **Output:** `reports/<as_of>/actions/<client>.json`: actions with `title`, `what`, `why`, `category`, `importance`,
  `horizon`, `due_date` and `sources` (finding refs such as `CL-0001#f7` and note ids such as `N-001`, each with the
  evidence ids copied from that source), plus `not_actioned` and `gaps`; `summary.json` and `audit.jsonl` beside them.
  Without a reconciliation file, actions come from the report alone and a gap says notes were not reconciled.
- **Categories:** `compliance_kyc`, `concentration_risk`, `mandate_drift`, `liquidity_cash_needs`, `credit_collateral`,
  `client_contact`, `data_quality`.
- **The model proposes, code decides.** Actions are removed (a `guard_removed` gap, status `partial`) when the category
  or importance is invalid, a reference does not exist for this client, or a figure in `title`/`what`/`why` is absent
  from the content it links to. Actions of the same category that share a source are merged (union of sources, highest
  importance). A contradicted note with no action is listed in `not_actioned`.
- **Importance rubric** (`actions/rubric.py`; a floor read from the linked evidence, the model may rate higher; a raise
  is recorded in `importance_raised_from`):

  | Condition | Category | Floor |
  |---|---|---|
  | KYC review overdue | `compliance_kyc` | critical |
  | KYC review due within 30 days / 90 days | `compliance_kyc` | high / medium |
  | Lombard LTV above its trigger / within 5 points | `credit_collateral` | critical / high |
  | Daily-liquid assets short of needs in the horizon | `liquidity_cash_needs` | high |
  | Mandate band or single-position limit breached | `mandate_drift` | high |
  | A single name is at least 25% of the client's assets | `concentration_risk` | high |
  | Any action resting on a contradicted note | any | medium |

- **Horizon** (`actions/horizon.py`) comes from dates in the linked evidence (KYC review date, cash-need start) and, as
  a fallback, future ISO dates written in linked findings; past dates in prose are history and ignored. An overdue
  structured date wins, otherwise the earliest upcoming one. Buckets by days from `as_of`: up to 7 `immediate`
  (overdue included), up to 30 `within_30_days`, up to 90 `within_90_days`, beyond `later`, no date `none`. A date or
  horizon written by the model is never read.
- **Order** within a client: importance, horizon, due date, title; `rank` is 1..n. Cross-client order is the overview's job.

```sh
uv run rm-dashboard-actions --as-of 2026-08-26 --db rm.db --reports-dir reports
```

## RM overview

The last stage builds what the dashboard shows an RM: the next actions across all of their clients, ranked, grouped and
linked. It is mostly code; the only model call is an optional short briefing.

**Pipeline** (each stage reads the files of the one before, for one `as_of`):

```sh
uv run rm-dashboard-outlook   --as-of 2026-08-26 --db rm.db --reports-dir reports   # outlook/market.json, outlook/instruments/
uv run rm-dashboard-analyse   --as-of 2026-08-26 --db rm.db --out reports      # <client>.json, evidence/ (reads the outlooks)
uv run rm-dashboard-reconcile --as-of 2026-08-26 --db rm.db                     # reconciliation/<client>.json
uv run rm-dashboard-actions   --as-of 2026-08-26 --db rm.db                     # actions/<client>.json
uv run rm-dashboard-overview  --as-of 2026-08-26 --db rm.db                     # overview/<rm_id>.json
```

- **Scope:** clients are grouped by `rm_id` from the database (reports carry no RM); one file per RM:
  `reports/<as_of>/overview/<rm_id>.json` (plus `summary.json`, `audit.jsonl`).
- **Output shape:** `actions` (flat list, each with `rank`, `action_id`, client id and name, `title`, `what`, `why`,
  `category`, `importance`, `horizon`, `due_date`, `sources` = finding refs and note ids with evidence ids),
  `by_category` (counts and action ids), `clients_without_actions` (with a reason), `gaps`, and the optional `summary` and
  `themes`. `what`, `why`, category and importance are copied from the client action, never rewritten.
- **Sort order:** importance (`critical` first), horizon (`immediate` first, `none` last), due date, client AUM
  (descending), client id, title. `rank` is 1..n and the order is the same on every run.
- **Coverage:** every client of the RM is either in `actions` or in `clients_without_actions`
  (`actions_missing`, `report_missing`, `no_action_needed`). A missing report or missing actions also produce a
  `data_quality` action (importance `high`) made by code, so a failed earlier stage is visible at the top.
- **Links** are re-checked against the report and reconciliation files; a broken link is a `link_broken:` gap and the
  action stays visible. Gaps of the client stages are carried over with the client id, so the overview is `partial`
  whenever an earlier stage was (for example when notes were not reconciled). Without any client actions for the date the
  overview is `insufficient_data` with a gap and no actions.
- **Briefing (optional):** one model call over the top 20 actions with pseudonymised names. Figures must appear in the
  actions; themes must group at least two existing action ids. A rejected, failed or denied briefing leaves the actions
  and order untouched and marks the overview `partial`; the model cannot add, drop or reorder actions.

## Market outlook

The bank's house view of the market: where markets are heading and why, independent of any client or portfolio. One
agent (`outlook_analyst`, a Deep Agents graph; for the market it has five tools: `market.history`, `analytics.market_trend`, `events.list`,
`news.list`, `outlook.previous_market`) writes it once per `as_of`; code then decides what the views may rest on.

- **Contract** (`outlook/contracts.py`): `MarketOutlook` with a `View` for `overall` and for every market category in the
  data (`equity`, `rates`, `fx`, `commodities`, `volatility`). A view has `direction` (`positive`, `neutral`, `negative`),
  `horizon` (`1m`, `3m`, `6m`; default `3m`), `confidence`, a rationale, `drivers` and `risks` (a claim, the evidence ids it
  rests on and the events it names by `event_id`), `would_change_if` and a `change`. There is no numeric forecast field.
- **Events are the reasons.** Events and news are treated as established facts. `events.list` and `news.list` give every
  event a stable `event_id` (`EVT-<date>-<n>`); a driver names the events it rests on in `event_refs` and code copies the
  evidence ids of the tool results that returned them. High and Severe events in the window since the previous outlook that
  no view cites are listed in `unaddressed_events` (informational).
- **Changes only with new data.** Each outlook records `inputs` (effective market snapshot date, latest event date, event
  count). When they equal the previous outlook's, the views are carried forward without a model call (`carried_forward_from`,
  every view `unchanged`). Otherwise a new outlook is written and each view says `new`, `unchanged`, `upgraded` or
  `downgraded` against the previous one. Earlier outlooks stay on disk as the reference; only an outlook with a strictly
  earlier `as_of` is ever used as previous (no look-ahead, so a past date can be rebuilt after later ones exist).
- **The model proposes, code decides** (`outlook/guard.py`): values must come from the closed sets, otherwise the view is
  removed; every driver and risk must cite evidence produced in this run (not the previous outlook, not another date) and
  each figure must exist in the cited evidence, otherwise it is removed; a rationale or `would_change_if` with an
  unsupported figure is blanked; the change kind and previous direction are derived by code, and a direction change must
  cite evidence newer than the previous outlook (a later event or a later market snapshot), otherwise the previous direction
  is kept and a gap records it; confidence is capped at `medium` for a view that cites no event and at `low` when the
  market history is too short for a trend; a segment without a valid view keeps its previous view (gap) or is a gap.
- **Always delivered.** Model failure, unparsable output, a policy denial or missing data give an outlook with a gap
  (`partial`, or `insufficient_data` without market data), with the previous views carried forward when there are any.

```sh
uv run rm-dashboard-outlook --as-of 2026-08-26 --db rm.db --reports-dir reports   # [--force] regenerates without new data
```

Output: `reports/<as_of>/outlook/market.json`, `evidence/market.json`, `summary.json` and `audit.jsonl`. Running the same
date again with the same inputs changes nothing.

## Instrument outlook

The same agent, with a different prompt and a narrower tool set (`instruments.context`, `events.relevant`, `outlook.market`,
`outlook.previous_instrument`; the market-only tools are refused and the other way round), writes the house view of one
instrument: where it stands against its peers and the market and where it is heading. It is independent of clients and
portfolios and is computed **once per instrument and date**; every client analysis reads the same file.

- **Which instruments.** Every instrument held in any portfolio at the snapshot effective at `as_of`, or the ones named with
  `--instruments`. An instrument held nowhere gets no outlook; one without a price at `as_of` is `insufficient_data` without a
  model call.
- **Context, computed by code.** `instruments.context` returns the reference data, the price path with percent changes, the
  peers (same sector, or the same sub-asset class when the sector is generic, region first, at most 8) with the group average
  and the relative performance in percentage points, and which risk statistics the history allows. `events.relevant` offers
  candidate events with what each matched on: a regional event matches an instrument of that region, any event matches when a
  word of its transmission appears in the instrument's sector, asset class, sub-asset class, name or underlying reference.
  It is lexical and says so; the model picks the events that really bear on the instrument and cites them by `event_id`.
  The market segments that bear on the instrument (`overall`, its asset class's segment, `fx` for a non-USD instrument) are
  copied from the market outlook by code into `market_context`; the model does not write them.
- **Contract** (`InstrumentOutlook`): the instrument, `price_path`, `unavailable_statistics`, `market_context`,
  `relevant_events` (the ones cited), one `InstrumentView` (direction, horizon, confidence, rationale, drivers, risks,
  would-change-if, change), `inputs`, `previous_as_of`, `carried_forward_from`, `unaddressed_events`, gaps.
- **Computed once.** `inputs` = latest price snapshot, ids of the relevant events and the digest of the market outlook used.
  When they equal the previous outlook's the view is carried forward without a model call; the stage also leaves an existing
  outlook of the same date alone. A new event regenerates only the instruments it bears on. (An unchanged market view with a
  later date is not news.)
- **Same guard as the market outlook** (closed sets, evidence of this run, no previous outlook as support, grounded figures,
  derived change kind, a direction change needs newer evidence: a later price, a relevant event after the previous date or a
  changed market outlook), plus confidence caps: `low` while a risk statistic is unavailable for lack of history (with five
  snapshots that is every instrument) or the price path is insufficient, `medium` when the view cites neither an event nor a
  peer comparison.
- **No client data.** Positions are read only to know which instruments exist, never quantities or owners.

```sh
uv run rm-dashboard-outlook --as-of 2026-08-26 --db rm.db --reports-dir reports [--instruments SYN-EQ-0001,SYN-CM-0401] [--force]
```

The command writes the market outlook first, then the instruments in parallel (`--concurrency`):
`reports/<as_of>/outlook/instruments/<id>.json`, `evidence/instruments/<id>.json` and a `summary.json` with the status of
every instrument. `audit.jsonl` is append-only across runs. A failure of one instrument is a gap in its own outlook only.

## Models

`build_model(settings)` returns `ChatOpenAI` for any OpenAI-compatible gateway (`RM_GATEWAY_URL`,
`RM_GATEWAY_API_KEY`, `RM_MODEL_NAME`). `RM_MODEL_NAME=stub` selects `StubChatModel`, a deterministic scripted
model with failure modes (`uncited_number`, `raise`) used by the tests and the default batch run. Agent logic names no provider.

## Interactive use

`AnalystSession(role, subject, scope, models)`: `start()` runs the standard analysis, `ask(question)` follows up.
Messages persist per `thread_id` (LangGraph `InMemorySaver`; a durable checkpointer can replace it), the evidence store
persists with the scope, and `as_of` stays fixed until `set_as_of(date)`.

## Add an analyst

1. Write a prompt in `agents/prompts.py` (start from `COMMON_RULES`).
2. Add its tool names to `tools/allowlists.py` (names must exist in the registry).
3. Register an `AnalystSpec` in `ANALYSTS` (subject pattern, delegates) and an agent card (`a2a/cards.py`, `SKILLS`).
4. Add a plan to `stubplans.py` for tests (optional for real models).

No other code changes: tools, policy and the guard apply automatically.
