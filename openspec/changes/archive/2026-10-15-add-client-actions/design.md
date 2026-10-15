# Design

## Context

Inputs are the persisted `Report` tree (findings with evidence ids) and, optionally, the `Reconciliation` of `add-note-reconciliation`. Pseudonymisation, policy checkpoints, audit, stub model and the numeric guard exist. See proposal.md.

## Goals / Non-Goals

**Goals:** per-client actions with comparable importance and code-derived horizons, parallelisable.
**Non-Goals:** ranking across clients, RM summary, new data access, mandate reconciliation.

## Decisions

1. **No tools; digest input.** Flattened findings with stable refs (shared loader) plus reconciliation results (`N-001`) in one message. One model call per client, run in a thread pool like the batch.

2. **Model proposes, code decides.** Model returns `{category, importance, title, what, why, refs[]}` with `refs` mixing finding refs and note ids. Code validates enums, resolves refs to this client only, copies evidence ids from the sources, checks numbers against linked content (`agents.guard.extract_numbers`), and drops violators as `guard_removed` gaps.

3. **Rubric as data in code (`actions/rubric.py`).** A table of (category, condition → floor importance) applied after the model: e.g. KYC overdue → `critical`, concentration limit flagged → `high`, contradicted note on a flagged exposure → `medium`. Conditions are detected from linked evidence flags/fields, not from model prose. The model proposes; the floor can only raise importance. The same table is rendered into the prompt so the model aims at it. *Alternative:* trust the model's importance — rejected: separate per-client calls drift.

4. **Horizon from evidence (`actions/horizon.py`).** Collect ISO dates from the linked findings/evidence (`kyc_review_due`, cash-need and commitment dates); the action's due date is the earliest date `>= as_of`, or any earlier due date (overdue). Bucket by day difference: overdue or ≤7 → `immediate`, ≤30, ≤90, else `later`; no dates → `none`. The guard's date-skipping is unchanged; model dates are simply never read. *Alternative:* let the model state a horizon and check it — rejected: easy to forge and hard to verify.

5. **Dedupe** by (category, overlapping source sets): union links, max importance, keep the title of the higher-importance action.

6. **Contradicted notes** must be linked by some action or are listed in `not_actioned` (visible, not silently dropped).

7. **Ordering** by importance rank, horizon rank, due date, title; `rank` numbered per client. Cross-client ordering is the overview's job.

8. **Output** `actions/<client>.json`: `ClientActions{client_id, as_of, status, summary, actions[], not_actioned[], gaps[]}`; plus `actions/summary.json`. CLI `rm-dashboard-actions`.

## Risks / Trade-offs

- [Rubric conditions are brittle against evidence shapes] → conditions read documented flag codes/fields; unmatched conditions leave model importance untouched; tested against the sample reports.
- [Dates in findings are free text] → extracted from structured evidence first, finding text second; if ambiguous the horizon is `none` rather than guessed.
- [Reconciliation optional] → gap recorded so the RM sees notes were not considered.
- [Dependence on the loader from the reconciliation change] → whichever change is applied first creates it; the other reuses it.
