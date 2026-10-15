# Proposal

## Why

With market and instrument outlooks produced once per date (`add-market-outlook`, `add-instrument-outlook`), the client analysis should use them instead of delegating each position to an instrument analyst again. This removes repeated work, makes every client report reason about an instrument the same way, and brings the bank's forward view and its stated reasons (events) into portfolio and relationship findings.

## What Changes

- The **Portfolio Analyst no longer delegates** to the Instrument Analyst. It reads the persisted outlook of its largest positions through a read-only tool and cites it.
- The **Relationship Analyst** and the **Portfolio Analyst** can read the market outlook of the run's `as_of`.
- New read tools `outlook.instrument` and `outlook.market` (the same tool family the outlook stage uses, allow-listed for the client analysts). Each result copies the outlook's evidence into the run's evidence store, so citations and the output guard keep working, and carries a `house_view` flag: a dated, forward-looking opinion, not a fact.
- A missing outlook for the date is a gap (`no_data`) with a pointer to the command; the analysis still completes (`partial`). The batch does not run the outlook stage itself; the pipeline order becomes `outlook -> analyse -> reconcile -> actions -> overview`.
- Prompts: forward-looking statements must come from the outlook and be worded as the bank's view with its date, horizon and confidence; reasons stay tied to cited events.
- Reports lose instrument child reports; position-level insight lives in the instrument outlook files. Interactive and A2A use of the existing `instrument_analyst` is unchanged.

## Capabilities

### New Capabilities
<!-- None -->

### Modified Capabilities
- `analysis-agents`: the delegation chain ends at the portfolio analyst; instrument insight comes from outlooks; forward-looking statements are bound to the outlook.
- `agent-tools`: read tools for the persisted market and instrument outlooks.

## Impact

- Code: `agents/analyst.py` (`ANALYSTS` delegates), `tools/allowlists.py`, new tools in `tools/outlook_tools.py`, prompts, stub plans, runner docs, tests that assume instrument children.
- Reads `reports/<as_of>/outlook/**`. No change to reconciliation, actions or overview contracts; the importance rubric still rests on structured evidence, not on outlooks.
- Depends on `add-market-outlook` and `add-instrument-outlook`.
- Out of scope: showing outlooks on the dashboard, using outlooks in the action rubric, retiring the `instrument_analyst` role, A2A exposure.
