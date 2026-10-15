# Proposal

## Why

RM notes record what the client said and intends (e.g. "wants the bank relationship kept apart from the family mine", "needs SGD 9m in early 2027"). The relationship report already quotes some notes, but nothing checks whether what the notes say agrees with what the data shows. Contradictions between a client's stated intent and the book are exactly what an RM should act on, and they are lost if notes are only quoted.

## What Changes

- Add a **Note Reconciliation agent**, run per client after the batch analysis, that compares each RM note dated on or before `as_of` with the client's persisted report and evidence and gives a verdict per note: `consistent`, `contradicted` or `unverifiable`, each with the note and the evidence on both sides.
- Scope is **RM notes only**. Reconciling against the mandate (limits, bands, policy) is a different source of truth and will be added later as separate reconciliation capabilities; the output contract is shaped so those can sit beside it.
- Persist `reports/<as_of>/reconciliation/<client>.json` and add a CLI (`rm-dashboard-reconcile --as-of DATE`).
- Always delivered, evidence-grounded and pseudonymised like the analysts.

## Capabilities

### New Capabilities
- `note-reconciliation`: per-client verdicts on whether RM notes agree with the client report and its evidence, as of a date.

### Modified Capabilities
<!-- None: reports, analysts and the batch runner are unchanged; this stage only reads their output. -->

## Impact

- New code: `reconciliation` package (contracts, loader, guard), agent prompt and stub plan in `agents`, runner/CLI, docs, tests.
- Reads `reports/<as_of>/<client>.json`, `evidence/<client>.json` and notes through the existing `notes.list` tool/point-in-time repository; writes only under `reconciliation/`.
- No new dependencies. Out of scope: mandate/policy reconciliation, deriving actions (see `add-client-actions`), UI.
