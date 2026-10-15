# Design

## Context

`Report` findings cite evidence ids; `evidence/<client>.json` holds every tool result behind a report. The Relationship Analyst already has `notes.list` and quotes notes, but never judges them against the data. The output guard (`agents/guard.py`) checks numbers against cited evidence; `register_people`/`RunContext` provide pseudonymisation, policy checkpoints and audit. See proposal.md.

## Goals / Non-Goals

**Goals:** a focused agent that does one thing — note vs data verdicts — with a contract that can later sit beside other reconciliation kinds.
**Non-Goals:** mandate/policy reconciliation, new data tools, deciding actions, changing the batch reports.

## Decisions

1. **Input is persisted artefacts plus notes.** The agent receives the client's report findings (flattened with stable refs, shared loader with `add-client-actions`), the evidence results, and the notes at `as_of`. It has no analytics tools. *Alternative:* delegate from the Relationship Analyst — rejected: it would lengthen the batch run and change report content/ids; a post-step keeps batch output stable.

2. **Notes come from the existing notes path** (`notes.list` through the point-in-time repository, `as_of` mandatory) so the date filter is enforced by the same code as elsewhere; the agent has only `notes.list` in its allow-list, evidence is supplied as input.

3. **Contract is kind-aware.** `Reconciliation{client_id, as_of, status, results[], gaps[]}` with `Result{kind: "rm_note", subject_ref (note id), verdict, rationale, note_quote, finding_refs[], evidence_ids[]}`. `kind` is a `Literal` with one value now; adding `mandate` later is an additive change. Output path `reconciliation/<client>.json`; a future mandate stage writes its own capability and file.

4. **Code decides what counts as a verdict.** Model returns `{note_id, verdict, rationale, finding_refs}`. Code resolves `finding_refs` to evidence ids, downgrades `consistent|contradicted` without resolvable evidence to `unverifiable`, drops results for unknown notes or notes after `as_of`, appends any note the model skipped as `unverifiable`, and checks numbers against cited evidence plus the note text (note numbers allowed only as quotes; rationale must not present them as data — enforced via prompt, noted as a limit).

5. **Same governance as analysts:** `RunContext` checkpoints, audit append, pseudonymised names, `StubChatModel` plan for tests, gateway model name `rm_dashboard` role `note_reconciler`.

6. **CLI** `rm-dashboard-reconcile --as-of DATE [--clients ...] [--db] [--reports-dir]`, batch with `RM_MAX_CONCURRENCY`, plus run summary in `reconciliation/summary.json`.

## Risks / Trade-offs

- [Verdicts are model judgements] → bounded to three values with mandatory evidence; unsupported verdicts downgrade to `unverifiable`.
- [A note legitimately refers to something outside the report] → `unverifiable` is a first-class outcome, not a failure.
- [Numbers in notes could launder into data claims] → rationale numbers must be in data evidence or quoted note text; residual limit documented.
- [Report fields are current-only for some attributes] → carried through as quality flags in the input.
