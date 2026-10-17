# Design

## Context

See proposal.md. `meeting_prep` is computed on each request in `api/overview.py` from the overview's actions, `client_rows` and the notes repository, and rendered only by `MeetingPrep.tsx`. Nothing else reads it. The same facts are served elsewhere: actions by `ClientDetail.actions`, KYC by `ClientDetail.profile.kyc_review_due` and the clients list, notes by `ClientDetail.notes` and the call sheet's conversation section.

## Goals / Non-Goals

**Goals:**
- Remove the panel and its backend block completely, leaving no dead code.

**Non-Goals:**
- No new client-view or clients-page content. Checked: every item of the panel is already shown there, so moving would duplicate it.
- No change to the overview summary, action table, client matrix or the call sheet.

## Decisions

- **Remove the API block too, not only the UI.** Only the panel consumes it and it costs a notes and KYC scan per request. Alternative: keep the field for other consumers; rejected as there are none and it keeps the contract larger than needed.
- **Do not relocate.** The request was to move it only if different from the call sheet. It is not different, so the change is a pure deletion. If a distinct need appears later (for instance a 14-day agenda across clients), it is a new proposal.

## Risks / Trade-offs

- [An external consumer of `meeting_prep` breaks] → none known in this repository; the change is marked breaking in the proposal.
- [Reviewer expects the cross-client agenda back] → removed deliberately: it mixed actions, KYC and notes from many clients in one place and forced constant context switches. Per-client views already cover each part.
