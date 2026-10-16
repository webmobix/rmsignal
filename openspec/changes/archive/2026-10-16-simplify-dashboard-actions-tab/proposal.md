## Why

The home page lists every next action (33 on the current data) with tier and category filters plus a data-quality lane, so the few calls that cannot wait are buried. The RM should open the dashboard and see only what needs doing now.

## What Changes

- The dashboard action table shows only actions that are `critical` or `high` importance **and** have horizon `immediate`. Data-quality actions never appear there.
- The dashboard's tier and category filters and the data-quality lane are removed from the home page.
- The metric strip keeps the total and per-tier counts. Medium and low tier counts link to the new Actions page filtered to that tier; critical and high counts link to the Actions page too, filtered likewise, so every number leads to its list.
- A line under the table shows how many further actions exist and links to the Actions page.
- New top-level **Actions** tab (`/actions`) in the primary nav, listing every action with the existing tier and category filters and a horizon filter, plus the data quality and coverage lane (moved from the dashboard).
- Tier filter state is held in the URL (`?tier=`) so metric-strip links and the back button work.

No API change: the overview payload already carries every action with importance, horizon and category.

## Capabilities

### New Capabilities
- `actions-ui`: the Actions page: all actions with filters, and the data quality and coverage lane.

### Modified Capabilities
- `rm-overview-ui`: the overview page shows only urgent actions, drops filters and the data-quality lane, and links tier counts and the remainder to the Actions page.

## Impact

- `dashboard-ui`: `features/overview/{OverviewPage,ActionsPanel,actions}.tsx|ts`, new `features/actions/ActionsPage.tsx` and `routes/actions.tsx`, `components/TopBar.tsx` nav, `components/MetricStrip.tsx` (optional link support), `routeTree.gen.ts` (regenerated), related tests.
- Backend, API and data: unchanged.
