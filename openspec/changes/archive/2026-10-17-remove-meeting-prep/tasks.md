# Tasks

## 1. Remove from the API

- [x] 1.1 In `src/rm_dashboard/api/overview.py` delete `MeetingItem`, `LatestNote`, `MeetingClient`, `MeetingPrep`, `meeting_prep()`, the window constant and the `meeting_prep` field/argument of `ApiOverview` and `build_overview`; remove imports left unused. Verify: `uv run ruff check src` is clean and `uv run pytest tests/test_api_overview.py -q` passes after step 1.2.
- [x] 1.2 In `tests/test_api_overview.py` and `tests/test_api_docs.py` remove the meeting prep tests and the `meeting_prep` key assertions. Verify: `uv run pytest -q` passes and `grep -rni meeting_prep src tests` finds nothing.
- [x] 1.3 In `docs/api.md` delete the "Meeting prep" section and drop `meeting_prep` from the `/api/overview` row and the heading "Overview, meeting prep, evidence". Verify: `grep -ni "meeting" docs/api.md` finds nothing.

## 2. Remove from the UI

- [x] 2.1 Delete `dashboard-ui/src/features/overview/MeetingPrep.tsx` and `MeetingPrep.test.tsx`; remove the import and the `<MeetingPrep>` usage from `OverviewPage.tsx`. Verify: the overview page renders without the section and `pnpm test` and `pnpm tsc --noEmit` in `dashboard-ui` pass.
- [x] 2.2 Regenerate `dashboard-ui/src/api/schema.ts` with `pnpm gen-api` against the running API. Verify: the diff only removes the meeting types and `grep -n Meeting dashboard-ui/src/api/schema.ts` finds nothing.
- [x] 2.3 Open the overview in the browser. Verify: no "Meeting prep" heading, the client matrix is the last section, no console errors.
