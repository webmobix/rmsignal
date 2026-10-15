# Agents

Three analysts (the Relationship Analyst is the RM's view of one client; it does not infer other persons), each a Deep Agents graph (LangGraph underneath) with a narrow tool allow-list:

```
Relationship Analyst  --task-->  Portfolio Analyst  --task-->  Instrument Analyst
 client, concentration,           composition, mandate bands,     reference data, price path,
 liquidity, credit, notes         P&L, change                     events, market context
```

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
4. The model's final answer is JSON: a summary and findings (`claim`, `confidence`, `evidence_ids`).
5. Deterministic code takes over: the **output guard** drops any finding that cites evidence not produced in this
   run or contains a number absent from the cited results (tolerance: 0.5% relative or the displayed rounding;
   ids, dates and pseudonyms are ignored; `%`, `m`, `bn`, `k` and thousands separators are normalised); gaps
   are collected (tool errors, denials, guard removals, `no_data` results); flags come from cited evidence;
   status derives from gaps (`complete`, `partial`; `insufficient_data` when core data is absent); report
   assembly checkpoints run; pseudonyms are restored last.
6. Whatever goes wrong inside (tool exception, policy denial, model failure, unparsable output), a `Report` is returned
   with the failure as a gap.

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
uv run rm-dashboard-analyse   --as-of 2026-08-26 --db rm.db --out reports      # <client>.json, evidence/
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
