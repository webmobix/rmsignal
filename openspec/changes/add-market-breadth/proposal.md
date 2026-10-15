# Proposal

## Why

The market outlook sees index, rate, FX and commodity series and the event log, but not what the instruments themselves are doing. It cannot say that equities are up while the rise is narrow, or that the move is led by one sector. Feeding the instrument *outlooks* into the market outlook is not the answer: those views are conditioned on the market outlook, so the two would depend on each other (a cycle that needs iteration, is not reproducible and counts the same evidence twice). Feeding the instrument *prices*, as computed facts, closes the gap without a cycle: facts flow up, opinions flow down.

## What Changes

- Add a deterministic analytic and tool, `analytics.breadth`: for each asset class (and, within equities, each sector) of the instrument master with a price at `as_of`, the number of instruments, how many rose against the previous snapshot and against the first snapshot, the share that rose, the median change and the range. Groups with fewer than 3 instruments are marked small. With fewer than 2 snapshots it returns `insufficient_history`.
- Give the market outlook agent that tool and a prompt line: use breadth to say whether a market move is broad or narrow and where it is led, cite it like any other evidence, never infer it from instrument opinions.
- Guard: breadth figures are checked like every other cited figure; breadth counts as newer evidence when its latest snapshot is later than the previous outlook's; confidence is capped at `low` when breadth, like the trend, has too little history.
- State and test the flow rule: the market outlook has no tool that returns an instrument outlook or any aggregate of instrument opinions, and the universe is the instrument master, never holdings, so the market outlook stays independent of clients.
- Docs: methods (breadth), agents (the rule "facts up, opinions down").

## Capabilities

### New Capabilities
<!-- None -->

### Modified Capabilities
- `market-outlook`: breadth of the instrument universe is evidence for the view; the market outlook never reads instrument opinions.
- `agent-tools`: a deterministic breadth tool.

## Impact

- New code: `analytics/breadth.py`, the tool in `tools/analytics_tools.py`, the market agent's allow-list and prompt, the guard's newer-evidence and history rules, stub plan, docs, tests.
- Reads the instrument master and prices through the point-in-time repository; no holdings, no client data, no outlook files.
- Depends on `add-market-outlook` (archived). Independent of `add-instrument-outlook` and `use-outlook-in-analysis`; planned after them because nothing downstream waits for it.
- Out of scope: any use of instrument outlooks by the market outlook, weighting by holdings or AUM, sector views as separate market segments, iteration between the two outlooks.
