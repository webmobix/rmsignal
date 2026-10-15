# Design

## Context

`ANALYSTS["portfolio_analyst"].delegates = ("instrument_analyst",)`; `_child_runner` runs a full child analysis with its own tool calls and model runs, appends the child report to `scope.children`, and the parent cites its evidence ids. The tool layer already supports tools that return evidence envelopes with flags (`QualityFlag`), and `assemble_report` collects flags from cited evidence. See proposal.md.

## Goals / Non-Goals

**Goals:** client analyses reuse the persisted outlooks; citations, policy, audit and the output guard behave as before.
**Non-Goals:** UI, changing action importance, deleting the instrument analyst.

## Decisions

1. **Read tools, not delegation.** `outlook.instrument(instrument_id, as_of)` and `outlook.market(as_of)` in `tools/outlook_tools.py`, added to `RELATIONSHIP_ANALYST` (market only) and `PORTFOLIO_ANALYST` (both) allow-lists; removed from the portfolio analyst's `delegates`. They go through `Toolbox.call`, so policy, audit and the point-in-time rule (an outlook with `as_of` later than the run's is never returned; the latest earlier one is returned with its own `as_of` stated) apply. *Alternative:* keep delegation and let the child read the outlook: rejected, it keeps an unneeded model run per position.

2. **Evidence continuity.** The tool result's `data` is the outlook's view, drivers and risks with their evidence ids, and the cited evidence results of the outlook are inserted into the run's `EvidenceStore` (same ids, since ids are content hashes). A client finding may then cite the outlook result id, or the underlying event or price evidence ids; both resolve, and number grounding sees the same numbers. The tool result `sources` names the outlook file and its `as_of`.

3. **House-view flag.** The result carries a `QualityFlag` `house_view` ("forward-looking view dated D, horizon H, confidence C; not a fact"). Because flags flow from cited evidence into the report, a client report that relies on an outlook shows the flag without extra code.

4. **Missing or stale outlook.** Absent for the date and no earlier one: `no_data` with reason "no outlook for <as_of>; run rm-dashboard-outlook" and a gap. An earlier outlook is returned with `effective_as_of` and a `stale_days` gap measure, consistent with how snapshots report effective dates. The batch stays decoupled from the outlook stage (like reconcile and actions), so each stage can be rerun independently.

5. **Prompts.** `PORTFOLIO_ANALYST`: for each of the largest positions read the instrument outlook instead of delegating; state outlooks as "the bank's view as of <date>"; do not extend the view beyond its horizon or confidence; do not mix a view with facts. `RELATIONSHIP_ANALYST`: read the market outlook once and relate it to the client's concentrations and needs where the outlook supports it. Events remain the cited reasons.

6. **Report shape.** `Report.children` no longer holds instrument reports for portfolio runs; `evidence_ids` includes the outlook evidence. Nothing downstream reads instrument children (reconciliation and actions work from findings and evidence ids; verify in tests).

7. **Refinements made during implementation.**
   - *Where the batch finds the outlooks:* `run_batch` points the tools at its own output folder when none is configured, so `rm-dashboard-analyse --out reports` finds `reports/<as_of>/outlook/` without extra wiring.
   - *One gap per missing outlook:* the `no_data` reason names the instrument (also when no reports folder exists), because the report collapses gaps with the same tool and reason.
   - *Evidence in the run store:* the evidence an outlook cites is added to the run's store (the tool context now carries the store). Report evidence files therefore also hold the evidence behind the outlooks that were read.
   - *The importance rubric is unchanged and a test pins that outlook results match none of its conditions.*

## Risks / Trade-offs

- [Forward views leak into client actions as facts] → flag on cited evidence; the action rubric reads only structured evidence; a test asserts a finding based only on an outlook cannot raise an action's importance floor.
- [Outlooks missing when the batch runs] → partial reports with a precise gap, never failure; docs fix the pipeline order.
- [Older tests assume instrument children] → updated in tasks; the instrument analyst remains available for interactive sessions.
- [Latest earlier outlook is old] → effective date and staleness are visible to the model and in the gap.
