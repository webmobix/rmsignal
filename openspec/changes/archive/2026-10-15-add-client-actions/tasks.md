# Tasks

## 1. Contracts and inputs

- [x] 1.1 Create `rm_dashboard/actions` with `ClientActions`, `Action`, `SourceRef`, category/importance/horizon `Literal`s; verify contract tests (enum rejection, round-trip)
- [x] 1.2 Ensure the shared report/evidence loader exists (`FolderReportSource`, from `add-note-reconciliation` or added here) and load optional `reconciliation/<cid>.json`; verify tests for present, absent (gap) and missing report
- [x] 1.3 Implement horizon derivation from linked findings/evidence dates; verify tests for overdue, ≤7, ≤30, ≤90, later, none, and a model-supplied date being ignored

## 2. Rubric, guard, dedupe

- [x] 2.1 Implement the importance rubric table with floors and detection from evidence flags/fields; verify tests that equal conditions in two clients give equal importance and a lower proposal is raised and recorded
- [x] 2.2 Implement the guard (enums, refs resolve to this client, evidence ids copied, numbers grounded); verify one test per drop reason producing `guard_removed` gaps and status `partial`
- [x] 2.3 Implement dedupe/merge and `not_actioned` for contradicted notes, plus deterministic ordering; verify tests for merge, unactioned contradiction and rerun equality

## 3. Agent

- [x] 3.1 Add the `client_actions` prompt (what/why, categories, rubric table, JSON schema, cite only supplied refs) and digest builder with pseudonymised names; verify no real name reaches the stub model's seen messages
- [x] 3.2 Add stub plans (normal, uncited-number, bad-ref, unparsable, raise); verify via the guard tests
- [x] 3.3 Implement `derive_actions(...)` wiring model call, parse, guard, rubric, horizon, dedupe, name restoration, policy checkpoints and audit; verify tests for model failure and missing report (`insufficient_data`)

## 4. Runner and docs

- [x] 4.1 Add `rm-dashboard-actions` CLI and script entry writing `actions/<cid>.json` and `summary.json`; verify `uv run rm-dashboard-actions --as-of 2026-08-26 --db rm.db` with the stub writes files and reruns are byte-identical
- [x] 4.2 Document the stage, rubric and horizon rules in `docs/agents.md` and README; verify `tests/test_docs.py` and the documented command pass
- [x] 4.3 Run `uv run pytest` and `openspec validate add-client-actions --strict`; verify both pass
