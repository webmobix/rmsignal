# Proposal

## Why

The meeting prep panel at the bottom of the overview repeats what the RM already has elsewhere. Its three parts each have a home: actions falling due are in the client's Actions tab and the urgent-action table, the KYC review date is in the client's health view and the clients table, and the latest RM note is in the portfolio call sheet ("When did we last speak?") and the client's notes tab. A fourth, separate block of talking points on the overview adds length and no information.

## What Changes

- Remove the meeting prep section from the overview page.
- **BREAKING** Remove the `meeting_prep` block from `GET /api/overview`.
- Nothing is added to the client view or the clients page: the content of the panel is not different from what the client view and the portfolio call sheet already show, so there is nothing to move. The existing KYC, actions and notes views stay as they are.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `rm-overview-ui`: the "Meeting prep" requirement is removed; the metric strip description no longer lists meeting prep.
- `overview-api`: the "Meeting prep" requirement is removed; the purpose line no longer mentions preparing meetings.

## Impact

- `src/rm_dashboard/api/overview.py` (models `MeetingItem`, `LatestNote`, `MeetingClient`, `MeetingPrep`, function `meeting_prep`, the `meeting_prep` field, the window constant), `tests/test_api_overview.py`, `tests/test_api_docs.py`.
- `dashboard-ui/src/features/overview/MeetingPrep.tsx` and its test, `OverviewPage.tsx`, `dashboard-ui/src/api/schema.ts` (regenerated).
- `docs/api.md` (the "Meeting prep" section and the endpoint table row).
- Persisted `reports/**` are unaffected: meeting prep was computed at request time, not stored.
