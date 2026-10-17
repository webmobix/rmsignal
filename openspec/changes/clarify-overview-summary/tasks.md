# Tasks

## 1. Summary generation and guard

- [x] 1.1 Add `client_id` to the actions in `build_input` and rewrite `RM_OVERVIEW_SUMMARY` to request `[[client_id]]` and `_action_` markup, covering only the two or three most pressing clients; verify with a prompt/input test in `tests/test_overview_core.py`
- [x] 1.2 In `guard_summary`, strip client tokens before the numeric check and reject (gap, empty summary) tokens naming clients not in `top`; verify with tests for kept markup and unknown client
- [x] 1.3 Make the stub plan emit the markup for the first action and update the existing stub-based assertions; verify `uv run pytest tests/test_overview_core.py tests/test_runners.py` passes
- [x] 1.4 Document the markup in `docs/agents.md` (overview agent section) and verify `tests/test_docs.py` passes

## 2. Dashboard rendering

- [x] 2.1 Add a summary renderer in `dashboard-ui/src/features/overview/` that splits on `[[id]]` and `_..._` into bold `Link` (name from `client_rows`) and `<em>`, plain text otherwise; verify with unit tests for linked client, italic action, unknown id, no markup
- [ ] 2.2 Use it as the `PageHeader` lede in `OverviewPage.tsx`; verify in the running app (chrome-devtools) that names are bold links and actions italic, and `pnpm test` and `pnpm biome check` pass

## 3. Integration

- [ ] 3.1 Rerun the overview runner with the stub model and verify the persisted summary is deterministic and renders correctly on the home page
