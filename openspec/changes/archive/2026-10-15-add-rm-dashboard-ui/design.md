# Design

## Context

`dashboard-ui/` is a bootstrapped TanStack Start app (React 19, Router file routes, Query 5, Tailwind 4, Vite 8, Biome) with an empty home route. `sample/SY/app` supplies the look and layout ideas (editorial masthead, serif metric strip, tier filters, risk map, right-hand drawer); its data model and logic are not reused. All data comes from the FastAPI API in `add-rm-read-api`.

## Decisions

**SPA-style Start app, no server functions.** Routes render on the client and fetch through TanStack Query; SSR may render shells, but loaders only prefetch through the same API client (`ensureQueryData`) so the router and query cache stay one mechanism. The dev server forwards `/api` to the FastAPI server through Nitro `routeRules` in `vite.config.ts` (Vite's own `server.proxy` is bypassed by Start's server handler); the target is configurable with `RM_API_URL`.

**Types from OpenAPI.** TypeScript types are generated from the API's `/openapi.json` (a script checked in, output committed) so the UI follows Pydantic. A single `api/client.ts` wraps fetch, injects `as_of`, and throws typed errors.

**Routes.**
```
/                         overview (+ ?action=<id> opens the drawer)
/clients                  list
/clients/$clientId        consolidated summary, portfolios, health, actions/notes, snapshots, scenarios
/portfolios/$portfolioId  portfolio view
/instruments              list
/instruments/$instrumentId
/market                   outlook + event timeline
```
The drawer is URL state (search param), so any evidence view is linkable and the back button closes it.

**Design tokens.** The sample's CSS variables become Tailwind v4 `@theme` entries (`--color-canvas`, `--color-surface`, `--color-navy-950`, `--color-alert`, `--font-serif`, `--font-sans`, ...). Fonts load from Google Fonts as in the sample. Components use utilities and a few `@layer components` classes for the editorial pieces (eyebrow, metric, rule). Biome formatting applies.

**Components** (`src/components/`): `AppShell`, `TopBar`, `Avatar`, `PageHeader`, `MetricStrip`, `TierBadge`, `DataTable` (TanStack Table), `ChartFrame`, `Drawer`, `Tabs`, `IdLink`, `StateBoundary` (loading, error, empty, gaps, placeholder banner). Feature components compose these.

**Charts.** Use TanStack Charts (`@tanstack/charts`, `@tanstack/charts/react` `Chart` component, stable 1.0 API), wrapped in `ChartFrame` so styling is token-driven and the library stays contained. Mapping:
- client matrix: `dot` marks (AuM x, urgency y), `ruleY`/`ruleX` for tier bands, `text` for labels
- AuM history (client, portfolio): stacked `areaY` or `lineY` per portfolio, event markers as `ruleX` plus `text`
- mandate bands: horizontal range marks with a `dot` for actual weight
- LTV history: `lineY` with a `ruleY` at the margin-call trigger
- AuM by client / asset class / instrument: bar marks, price path: `lineY`

Chart colours come from the theme's CSS variables. The AuM scale is log or sqrt because the book spans roughly USD 8m to 88m. Charts must be legible without colour alone (shape or label for tier). SSR support is not documented, so charts render client-only behind a mount guard in `ChartFrame`; the rest of the page still server-renders. The matrix and the stacked history are the first things prototyped, to confirm the mark set covers them before the other views build on it.

**Matrix y-axis.** The API's `urgency` (finer than the two tiers present in the data) drives the y-axis; tier drives colour. This avoids a two-row chart.

**Placeholders.** `StateBoundary` renders the banner for `status: "placeholder"`; the scenario tab neutralises breach colours so a placeholder can never look like a real alert.

**Data volume.** 20 clients and about 1,000 holdings: no virtualisation, client-side sort and filter.

## Risks and trade-offs

- Coupled to the API contract: mitigated by generated types and by building after the API change lands.
- Several views depend on sections that may be gaps in the current run (3 clients with action files, 2 instrument outlooks): every region must render its gap state; verified against the committed run.
- TanStack Charts is new to this project and its SSR story is undocumented; contained behind `ChartFrame` with client-only rendering.

## Prototype findings (task 1.3)

Prototyped against the real API on 2026-08-26 data:
- Matrix: `dot` on a `d3-scale` `scaleLog` x axis, `ruleY` tier lines and `text` labels render; hover shows a tooltip and `onSelect` on the `Chart` returns the clicked datum (click navigation is feasible). The default tooltip lists channels (AuM, urgency) and not the client name, so `ChartFrame` uses `@tanstack/charts/react/tooltip` with `renderTooltipBody` for names.
- Stacked history: `areaY` with `layout: stack()` and `color` per portfolio on a `scaleUtc` x axis, with `ruleX` event markers, renders correctly.
- `d3-scale` is added as a direct dependency (log, UTC scales). Default colours are the library palette, so `ChartFrame` passes an explicit tier colour domain and range.
- Not yet verified: min-target-max band ranges for the mandate view. They are checked in task 4.7, with `barX` intervals or `link` segments as the intended marks.

## Open questions

- Whether the overview should offer a print or export view for meeting prep (deferred).
