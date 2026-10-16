# Design

## Context

Observed in the code:
- `analytics/mandate.py` `mandate_drift` returns band breaches and single-position breaches. It is exposed as the tool `analytics.mandate_drift`, in the Portfolio Analyst's allow-list. It never reads `sustainability_excluded`, which is only carried on the instrument model and API.
- Mandates have no structured exclusion list. `mandates.csv` carries only `mandate_notes` text; for `SUSBAL` it says "binding exclusions: ...".
- The stages after `analyse` each read persisted files: `reconcile` writes `reconciliation/<client>.json` (one model call per client, guard in code), `actions` reads report, evidence and reconciliation, then merges, applies the rubric floor (`actions/rubric.py`, which can only raise importance and reads only evidence of the linked sources), derives horizons and ranks. The API reads persisted files through `ctx.overviews`.
- `SourceRef.kind` is `finding` or `note`; the `Action` model has no way to link a mandate result.

At 2026-08-26 the sample data has breaches in 13 managed portfolios, the exclusion breach in PF-0007 (SUSBAL) and notes bearing on a few of them (N-008 PF-0007, N-010 PF-0009, N-013 PF-0011, N-024 PF-0022). See proposal.md for motivation.

## Goals / Non-Goals

**Goals:**
- A deterministic exclusion breach with evidence, in the report like any other breach.
- A reconciliation stage that mirrors `reconcile`: one model call per client, deterministic subject, guarded output, always delivered.
- A status that changes the wording and importance of mandate actions in a defined, testable way.

**Non-Goals:**
- No change to how a band or position breach is computed.
- No verification of a waiver (no waiver record exists); no change to computed results because of a note.
- No change to the existing note reconciliation verdicts.

## Decisions

**Exclusion check as a new calculation `exclusion_breaches` in `analytics/`, exposed as the tool `analytics.exclusion_breaches`**, added to the Portfolio Analyst's allow-list and prompt (call it for every managed portfolio next to `analytics.mandate_drift`). Binding exclusions are derived from data: a mandate is bound when its `mandate_notes` state "binding exclusions". Alternative: a code constant `{"SUSBAL"}`; rejected, as a new sustainable mandate in the data would silently be unchecked. Look-through reuses `parse_underlyings` and `normalise_name` against the excluded instruments' names. Weight is of the portfolio total in base currency, as for bands.

**The new stage reads breaches from persisted evidence, not from the report text.** It collects `analytics.mandate_drift` and `analytics.exclusion_breaches` results from `evidence/<client>.json` and turns each breach into a subject with a stable key `(portfolio_id, kind, key)` where key is the asset class, instrument id or excluded instrument id. Alternative: re-run the analytics in the stage; rejected, as the evidence ids that actions must link to would not exist in the client's evidence. Consequence: a managed portfolio whose check is missing from the evidence is a gap, not silent.

**One model call per client, and none when there is nothing to judge.** No breaches, or no notes up to `as_of`, gives a deterministic result (`no_note` for all) without a model call. Otherwise the model receives the breach subjects and the notes and returns, per breach, a status, note ids and a rationale. It cannot add a breach.

**Statuses: `no_note`, `acknowledged`, `client_directed`, `contradicted`.** Definitions in the spec. `client_directed` includes a claimed waiver; there is no separate waiver status, since the claim is unverified either way. Precedence when several notes bear on one breach: `contradicted` > `client_directed` > `acknowledged` > `no_note`, so the most consequential reading wins and all cited notes are kept.

**Attribution of notes to portfolios.** Notes carry only the client id. The model must name the portfolio and the breach; the guard checks that the cited note text mentions something that bears on that breach (asset class, instrument name or portfolio name, case-insensitive) when the client has more than one managed portfolio, and otherwise moves the note to an `ambiguous_notes` list. Alternative: attribute to every portfolio with a breach; rejected, as it would put N-010's gold waiver on a second portfolio.

**Guard like the existing reconcile guard.** Cited evidence id must exist in the client's evidence and be the breach's own; cited notes must exist and be dated on or before `as_of`; numbers in rationales must equal evidence or be quoted from the note. Failures reset the entry to `no_note` and add a gap. Names are pseudonymised on the way in and restored on the way out, with the existing `RunContext`, policy checkpoints and audit log. No new checkpoint.

**Output** in `reports/<as-of>/mandate-reconciliation/<client>.json`, plus `summary.json` and `audit.jsonl` in that folder. New script `rm-dashboard-mandate-reconcile` with the same arguments as `rm-dashboard-reconcile`.

**Actions: the status feeds the rubric through the linked source.** Add a source kind `mandate` (ref `<portfolio_id>/<kind>/<key>`) so an action can link a mandate result and the breach evidence id. The rubric's `mandate_drift` condition becomes status-aware:

| Breach | `no_note` | `acknowledged` | `client_directed` | `contradicted` |
|---|---|---|---|---|
| band or position | high | medium | high | critical |
| exclusion | high | high | high | critical |

Because the floor can only raise a proposed importance, an action with no mandate source keeps today's flat `high` for any breach, and an action that links a result takes the status floor. `RUBRIC_TEXT` and `docs/agents.md` render the same table. The prompt tells the model the wording per status. `not_actioned` also lists contradicted mandate results. Merge keeps its rule: actions of one category sharing a source become one at the highest importance.

**API and UI.** `PortfolioRow` gains `breach_reconciliation: list[{portfolio_id, kind, key, status, note_ids}]`, read from the persisted file; absent means empty plus a gap. The detail response adds the quoted note text. `MandateStatus` shows a short label per worst status ("waiver claimed (N-010)", "contradicted"); `no_note` adds nothing.

## Risks / Trade-offs

- [The Portfolio Analyst does not call `analytics.exclusion_breaches`] → prompt requires it for managed portfolios; a missing result is a gap in the mandate reconciliation and the client report; tests with the scripted model assert the call.
- [Exclusion text rule misfires on a mandate whose notes mention "binding exclusions" in another sense] → only `SUSBAL` has it in the data; covered by a test on the seeded mandates.
- [Model misreads a note as acknowledging a breach] → guard requires a cited note and an evidence id, rationale numbers are checked, and the status never changes a computed breach.
- [A lower floor for `acknowledged` hides a breach] → the breach and its figures stay in the report, the action is still produced, and exclusion breaches never go below high.
- [Note attribution heuristic rejects a valid note] → it lands in `ambiguous_notes` and the breach keeps `no_note`, which is the conservative reading.
- [Stage ordering: `actions` run without mandate reconciliation] → a gap is recorded and every mandate action is treated as `no_note`, equal to today's behaviour.

## Migration Plan

Additive. Run the new stage between `reconcile` and `actions`; existing batch output keeps working without it. Re-run `analyse` to get exclusion evidence for dates already analysed.
