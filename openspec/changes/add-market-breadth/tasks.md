# Tasks

## 1. Breadth

- [ ] 1.1 Verify that the instrument price snapshots equal the market snapshots in the sample data (so `OutlookInputs` already covers breadth); if not, add the price snapshot date to the inputs
- [ ] 1.2 Implement `analytics/breadth.py` (groups by asset class and by sector within equities, up/unchanged rule, median, range, `small`, statuses) with a registered method string; verify tests on the sample (equities, cash all unchanged, a group under three), one snapshot and none
- [ ] 1.3 Add `analytics.breadth` to the tools (as_of only); verify the envelope, sources, no look-ahead and that the tool reads no holdings

## 2. Market outlook

- [ ] 2.1 Add the tool to the market allow-list only and the breadth rule to the market prompt; add a test that the market allow-list contains no tool that returns instrument outlooks or instrument views
- [ ] 2.2 Extend the guard: breadth counts as newer evidence by its latest snapshot, and `insufficient_history` of breadth caps confidence at `low`; verify one test per rule and that unsupported breadth figures remove the driver
- [ ] 2.3 Add breadth to the stub plan so a driver cites it; verify the market outlook for the sample cites breadth and that the breadth figure is grounded

## 3. Docs and checks

- [ ] 3.1 Document breadth (method, tool row, guard rules) in `docs/analytics.md`, `docs/methods.md` and the "facts up, opinions down" rule in `docs/agents.md`; verify `tests/test_docs.py`
- [ ] 3.2 Verify the universe is independent of clients: breadth and the market outlook's inputs are unchanged when the set of held instruments changes
- [ ] 3.3 Run the outlook command for two dates and verify the second market outlook states a change that cites breadth when prices moved
