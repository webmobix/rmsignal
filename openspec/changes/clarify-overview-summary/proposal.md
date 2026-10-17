# Proposal

## Why

The summary at the top of the overview is useful, but it is one undifferentiated paragraph: the RM has to hunt for who to call and what to do. Making each client and each recommended action visually distinct turns it into a scannable briefing.

## What Changes

- The summary marks every client it mentions with the client id; the dashboard renders it as the client's name, in **bold**, linking to the client view.
- The summary marks the action to take for each client; the dashboard renders it in *italic*.
- The summary prompt asks for that structure (only the two or three most pressing clients: who, then the action, within two to four sentences), and the guard validates the markup.
- A summary with a malformed or unknown client reference is rejected as today (summary removed, gap recorded, overview `partial`).
- The persisted `summary` stays a string; no API shape change.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `rm-overview`: the optional model summary may carry client and action markup, which is validated; figures inside client ids are not treated as claims.
- `rm-overview-ui`: the overview page renders the summary with bold linked client names and italic actions.

## Impact

- `src/rm_dashboard/agents/prompts.py` (RM_OVERVIEW_SUMMARY), `src/rm_dashboard/overview/summary.py` (input carries `client_id`; guard), `src/rm_dashboard/agents/stubplans.py` (stub emits markup).
- `dashboard-ui/src/features/overview/OverviewPage.tsx` plus a small summary renderer; `PageHeader` lede already accepts a node.
- Existing `reports/**/overview/*.json` with plain summaries keep rendering as plain text; a rerun of the overview runner produces the marked-up form.
- Tests: `tests/test_overview_core.py`, UI tests for the renderer. Docs: `docs/agents.md`.
