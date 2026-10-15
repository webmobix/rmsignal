# Proposal

## Why

Reports are long and descriptive. An RM needs, per client, the concrete next steps — what to do, why, how urgent and by when. Doing this per client keeps the agent's context small, lets it run in parallel like the batch, and keeps importance judged against one coherent set of facts.

## What Changes

- Add a **Client Actions agent**, run per client, that reads the client's persisted report and, when present, its note reconciliation, and produces next actions: title, `what`, `why`, `category`, `importance`, a **time horizon**, and links to the findings and reconciliation results that justify it.
- Importance follows a **fixed rubric** (conditions, not feel) so it is comparable across clients that are processed separately.
- The horizon bucket and date are **derived in code** from dates present in the linked findings/evidence, never taken from the model.
- Duplicate actions (e.g. a contradicted note and a report finding about the same issue) are merged.
- Persist `reports/<as_of>/actions/<client>.json` and add a CLI (`rm-dashboard-actions --as-of DATE`).
- Works without reconciliation files (actions then come from the report alone).

## Capabilities

### New Capabilities
- `client-actions`: per-client prioritised, categorised, time-bounded next actions linked to report findings and note reconciliation.

### Modified Capabilities
<!-- None -->

## Impact

- New code: `actions` package (contracts, rubric, horizon derivation, guard, dedupe), agent prompt and stub plan, CLI, docs, tests. Reuses the report/evidence loader from `add-note-reconciliation` (if that change is not yet applied, the loader task is done here first).
- Reads `reports/<as_of>/<client>.json`, optional `reconciliation/<client>.json`; writes `actions/`.
- Consumed by `add-rm-overview-agent`. Out of scope: cross-client ranking, RM-level summary, UI, mandate reconciliation.
