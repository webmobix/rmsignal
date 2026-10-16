## Context

Today `OverviewPage` renders `ActionsPanel`, which owns tier and category state, a `TierFilter`, the risk table and a collapsed data-quality lane, all fed by `splitActions` in `features/overview/actions.ts`. `ActionTable` and `TierFilter` are already reusable. The evidence drawer is mounted in the root route and driven by the `action` search param, so it works on any route. Horizon `immediate` is already a first-class value (`HORIZON_ORDER`), computed by the backend as due within 7 days.

## Goals / Non-Goals

**Goals:**
- Home page shows only urgent actions; everything else is reachable in one click.
- Reuse `ActionTable`, `TierFilter`, `splitActions` rather than rewrite.

**Non-Goals:**
- No backend or API change, no change to how importance or horizon are computed.
- No change to the client matrix, meeting prep or evidence drawer.

## Decisions

- **Urgent = (critical or high) AND horizon immediate.** The request says "high and higher importance that need immediate action"; both conditions apply. Implemented as `urgentActions(actions)` in `actions.ts`, driven by a constant tier set so a future tier above critical needs one edit. Alternative (OR) would still list ~every high action and not shrink the table.
- **Data quality excluded from the home page entirely**, even if critical/immediate: it moves wholesale to the Actions page. Its count stays visible via the link line.
- **Tier filter in the URL** as `tier` on the `/actions` route (`validateSearch`), because metric-strip links need to target it. Category and horizon filters stay local component state; they are not link targets. Alternative: all filters in the URL — rejected as more surface than needed.
- **Metric strip links:** extend `MetricStrip` metrics with an optional `to`/`search`; tier metrics link to `/actions?tier=<tier>`. Critical/high link too for consistency, since their counts include non-immediate actions the home table omits.
- **Remainder link** below the table: "N more actions" where N = total − urgent shown, linking to `/actions`.
- **Component split:** `ActionsPanel` becomes the small urgent table + link; the filtered list and data-quality lane move to `features/actions/ActionsPage.tsx`, sharing `/overview` data via the existing `useData("/overview")` query (cached, so no extra request).

## Risks / Trade-offs

- [Counts on the strip exceed rows in the table] → the remainder line and linked counts make the difference explicit.
- [Few or no actions are ever "immediate", leaving the home table mostly empty] → empty notice states nothing is urgent and links onward; threshold (7 days) is existing behaviour and unchanged.
- [Existing tests assert the filters and lane on the home page] → move/rewrite them for the Actions page.
