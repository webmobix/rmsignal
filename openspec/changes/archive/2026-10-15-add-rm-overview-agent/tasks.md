# Tasks

## 1. Contracts and sources

- [x] 1.1 Create `rm_dashboard/overview` with `Overview`, `OverviewAction`, `CategoryGroup`; verify contract tests (round-trip, enums)
- [x] 1.2 Implement `ActionSource` protocol and folder implementation reading `actions/<cid>.json` and report files; verify tests with fixtures including missing folder and missing client files
- [x] 1.3 Scope by RM using the point-in-time repository (rm_id, name, AUM); verify a client of another RM is excluded

## 2. Aggregation in code

- [x] 2.1 Implement ranking with the documented sort key, `rank` and `by_category`; verify tests for mixed importance, horizon and AUM tie-breaks and rerun equality
- [x] 2.2 Implement link verification and carried-over gaps; verify tests for a broken finding ref and a client-stage gap yielding `partial`
- [x] 2.3 Implement coverage (`actions_missing`, `report_missing`, `no_action_needed`) with code-produced `data_quality` actions; verify tests for each case

## 3. Optional summary

- [x] 3.1 Add the summary prompt, top-N pseudonymised input, summary guard (action ids exist, numbers grounded) and stub plan; verify no real name reaches the stub model and a model reorder attempt changes nothing
- [x] 3.2 Wire the summary with `RunContext` checkpoints/audit and failure handling; verify a raising model gives `partial` with actions intact, and no actions skips the call

## 4. Runner and docs

- [x] 4.1 Add `rm-dashboard-overview` CLI and script entry writing `overview/<rm_id>.json`; verify `uv run rm-dashboard-overview --as-of 2026-08-26 --db rm.db` with the stub writes a file and a rerun is byte-identical
- [x] 4.2 Document the pipeline order (analyse → reconcile → actions → overview), output shape and sort rules in `docs/agents.md` and README; verify `tests/test_docs.py` and the documented commands pass
- [x] 4.3 Run `uv run pytest` and `openspec validate add-rm-overview-agent --strict`; verify both pass
