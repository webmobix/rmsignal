# Tasks

## 1. Contracts and inputs

- [x] 1.1 Create `rm_dashboard/reconciliation` with `Reconciliation`, `Result` (`kind` Literal `rm_note`, verdict Literal) and gap handling; verify contract tests (enum rejection, JSON round-trip)
- [x] 1.2 Add a shared report/evidence loader (`FolderReportSource`) that flattens a report tree to stable finding refs (`CL-0001#f7`, `CL-0001/PF-0001#f3`) and loads `evidence/<cid>.json`; verify tests on the `reports/2026-08-26` fixtures including missing report/evidence
- [x] 1.3 Load notes at `as_of` for a client via the point-in-time repository; verify test that a note dated after `as_of` is excluded and a client without notes yields an empty list

## 2. Guard

- [x] 2.1 Implement the result guard (unknown/later notes dropped, evidence ids resolved from finding refs, unsupported verdicts downgraded, missing notes appended as `unverifiable`, numbers checked against evidence and note quote); verify one unit test per rule and status `partial` on removals
- [x] 2.2 Verify scope: add a test that a mandate breach with no note produces no result (source kind only `rm_note`)

## 3. Agent

- [x] 3.1 Add the `note_reconciler` prompt (verdict definitions, notes are quoted not trusted, cite only supplied refs, JSON schema) and input builder with pseudonymised names; verify a test that no real name reaches the stub model's seen messages
- [x] 3.2 Add stub plans (normal, uncited-number, bad-ref, unparsable, raise); verify via guard tests
- [x] 3.3 Implement `reconcile(...)` wiring model call, parse, guard, name restoration, policy checkpoints and audit, always returning a `Reconciliation`; verify tests for model failure, missing report and idempotent rerun

## 4. Runner and docs

- [x] 4.1 Add `rm-dashboard-reconcile` CLI and script entry writing `reconciliation/<cid>.json` and `summary.json`; verify `uv run rm-dashboard-reconcile --as-of 2026-08-26 --db rm.db` with the stub writes files and a rerun is byte-identical
- [x] 4.2 Document the stage, contract and "notes only, mandate later" boundary in `docs/agents.md` and README; verify `tests/test_docs.py` and the documented command pass
- [x] 4.3 Run `uv run pytest` and `openspec validate add-note-reconciliation --strict`; verify both pass
