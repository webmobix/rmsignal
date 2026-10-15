# Design

## Context

Per-client outputs exist in `reports/<as_of>/`: `<client>.json`, `reconciliation/`, `actions/`. Reports have no RM; `clients.rm_id/rm_name/total_aum_usd` give scoping (sample: one RM, `RM-SG-014`, 20 clients). See proposal.md.

## Goals / Non-Goals

**Goals:** a reliable aggregate where the only judgement left is an optional summary.
**Non-Goals:** re-judging importance, re-ranking by a model, serving over HTTP, desk rollups.

## Decisions

1. **Aggregation is code.** `overview/build.py` loads each client's `ClientActions` through a `ActionSource` protocol with a folder implementation (swappable for a store later), joins client name/AUM from the point-in-time repository and ranks. *Alternative:* an agent that also ranks — rejected: it would undo the rubric and make order irreproducible.

2. **Sort key** (importance rank, horizon rank, due date or max, −AUM, client id, title). `by_category` is a derived view with counts; no content is rewritten.

3. **Link verification in code.** Report path, finding refs and note ids are re-resolved against the files at build time; a failed link marks the action `link_broken` in gaps rather than silently dropping it (the action is still shown, since it was validated upstream).

4. **Coverage.** Clients absent from the actions folder get `actions_missing` (or `report_missing` if the report is also absent) plus a code-produced `data_quality` action; clients with an actions file and zero actions are listed `no_action_needed`.

5. **Optional summary.** One call with the ranked top-N actions (pseudonymised), returning `{summary, themes[{title, action_ids[]}]}`; guard: action ids exist, numbers present in referenced actions. Reuses `StubChatModel` plan, gateway role `rm_overview_summary`, and `RunContext` checkpoints/audit. Skipped when there are no actions.

6. **Status.** `complete` if no gaps; `partial` for any gap (client-stage or summary); `insufficient_data` if no client outputs. Sample reports being `partial` by design do not by themselves degrade the overview.

7. **Output** `overview/<rm_id>.json`: `Overview{rm_id, rm_name, as_of, status, summary, themes, actions[], by_category, clients_without_actions[], gaps[], inputs}`; CLI `rm-dashboard-overview --as-of DATE [--rm] [--db] [--reports-dir]`.

## Risks / Trade-offs

- [Upstream stages missing] → coverage rules and gaps make this visible instead of empty.
- [Many actions overwhelm the view] → `top_n` is a dashboard concern; the file keeps all actions with rank so any cut is trivial.
- [Reports lack an RM field] → scoping depends on the database; a later change may add `rm_id` to `Report`.
