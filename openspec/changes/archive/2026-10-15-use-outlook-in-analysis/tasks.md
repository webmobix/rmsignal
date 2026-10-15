# Tasks

## 1. Read tools

- [x] 1.1 Implement `outlook.market` and `outlook.instrument` in `tools/outlook_tools.py` (latest outlook not after `as_of`, effective date, source file, `house_view` flag, evidence inserted into the run store); verify returned, none, later-only and earlier-only cases
- [x] 1.2 Register the tools and update allow-lists (relationship: market; portfolio: market and instrument); verify the instrument analyst cannot call them and the registry tests still pass

## 2. Agents

- [x] 2.1 Remove `instrument_analyst` from the portfolio analyst's delegates; update prompts for the outlook rules (bank's view with date, no extension beyond horizon, missing outlook means no forward claim); verify the portfolio run makes no child runs
- [x] 2.2 Update stub plans to read outlooks; verify findings that cite outlook results are kept by the guard, the report carries the `house_view` flag, and an outlook-only finding does not raise an action importance floor
- [x] 2.3 Verify missing outlooks give `partial` with a gap per missing outlook and no forward-looking finding, and that reconciliation, actions and overview still run on reports without instrument children

## 3. Pipeline and docs

- [x] 3.1 Update existing tests that assume instrument child reports; verify the full suite
- [x] 3.2 Document the pipeline order `outlook -> analyse -> reconcile -> actions -> overview`, the new tools and the house-view flag in `docs/agents.md`, `docs/contracts.md` and the README; verify `tests/test_docs.py`
- [x] 3.3 Run the pipeline end to end on the seeded sample database for two `as_of` dates with the stub model; verify the second outlook shows its changes and the client reports cite them
