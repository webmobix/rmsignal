# Tasks

## 1. Foundation and tooling

- [x] 1.1 Add `@tanstack/charts` and a dev-only OpenAPI type generator to `dashboard-ui`, configure the Vite `/api` proxy (base URL from env), remove the template's faker/demo content, and verify `pnpm build` and `pnpm check` succeed
- [x] 1.2 Add a script that generates `src/api/schema.ts` from the running API's `/openapi.json`, commit its output, and verify the file contains the overview, client and scenario types
- [x] 1.3 Prototype the two hardest charts with TanStack Charts (client matrix with `dot` marks and tier bands; stacked `areaY` history with `ruleX` event markers) against real API data, record in `design.md` whether the mark set covers hover, click and band ranges, and verify both render in the browser. If it falls short, update `design.md` with the fallback before continuing

## 2. Design system and shell

- [x] 2.1 Port the sample's palette, fonts (Source Serif 4, Public Sans via Google Fonts), spacing and rules into Tailwind v4 `@theme` tokens and a few `@layer components` classes in `styles.css`; verify no component uses a literal colour or font (grep)
- [x] 2.2 Build `api/client.ts` (typed fetch, `as_of` injection, typed errors) and query-key and hook helpers; verify with unit tests for URL building, `as_of` injection and error mapping
- [x] 2.3 Build `AppShell`, `TopBar` (Global WM Bank text mark, RMSignal, nav, as-of date) and `Avatar` fed by `/api/rm` and `/api/as-of`; verify in the browser that the bar shows "PO", the name, the role, "26 Aug 2026", and no Julius Baer name or logo (grep the source)
- [x] 2.4 Build the shared components `PageHeader`, `MetricStrip`, `TierBadge`, `Tabs`, `IdLink` (client, portfolio, instrument, evidence ids to routes or drawer), and `StateBoundary` (loading, error with retry, empty, gaps list, placeholder banner); verify with component tests for each state
- [x] 2.5 Build `DataTable` on TanStack Table (sort, filter, row link, custom cell) and `Drawer` (right slide-in, Escape, close control, outside click, URL-search-param driven); verify with component tests for sorting, Escape and outside click
- [x] 2.6 Build `ChartFrame` (client-only mount guard, token colours, log/sqrt scale helper, accessible label and non-colour tier encoding); verify the page server-renders without error and the chart appears after mount

## 3. Routes and overview

- [x] 3.1 Create the route files `/`, `/clients`, `/clients/$clientId`, `/portfolios/$portfolioId`, `/instruments`, `/instruments/$instrumentId`, `/market` with prefetch via the shared client and the top-level navigation; verify `pnpm generate-routes` and a build pass and each route loads
- [x] 3.2 Build the overview header: metric strip (clients, AuM, actions, tier counts), model summary and themes, status "partial" visible; verify against the 2026-08-26 run (20 clients, 33 actions)
- [x] 3.3 Build the action list with tier and category filters (dimmed counts for other tiers) and the separate data-quality lane; verify with a test that selecting "high" leaves only high actions
- [x] 3.4 Build the client matrix chart (AuM log/sqrt x, urgency y, tier colour and shape, tooltip, click opens the client, no-action clients on the baseline); verify 20 points appear once and a click navigates
- [x] 3.5 Build the evidence drawer content (what, why, category, importance, horizon, due, findings, evidence from `/api/evidence`, links to client, portfolio, instrument) and `?action=` deep linking; verify open, Escape close with list state unchanged, and a deep link in the browser
- [x] 3.6 Build the 14-day meeting prep panel (due actions, KYC due or overdue marked, latest RM note, links to clients); verify an overdue KYC shows marked with a link

## 4. Clients and portfolios

- [x] 4.1 Build the clients list with the sortable `DataTable` and the AuM-by-client bar chart sharing the sort order; verify sorting by AuM reorders rows and chart
- [x] 4.2 Build the consolidated client summary (total AuM and change, stacked AuM history with event markers, combined allocation, currency exposure, largest positions with look-through, liquidity, credit headroom) with per-section gap states; verify a three-portfolio client shows three series and a gap section leaves others rendered
- [x] 4.3 Build the client's portfolio list (name, mandate, service model, AuM, change, mandate status; custody shows "no mandate"; rows link to the portfolio) ; verify the single-portfolio and custody cases
- [x] 4.4 Build the portfolio health block (concentration, mandate, liquidity, credit, KYC status with figure and a link opening the drawer on the finding); verify a health item opens the drawer
- [x] 4.5 Build client actions and RM notes with reconciliation verdicts (contradicted marked, evidence opens from the note); verify a contradicted note is marked and opens evidence
- [x] 4.6 Build snapshot comparison (two pickers, per-portfolio AuM and P&L change, positions added, removed, resized, events between); verify 2026-02-27 against 2026-03-31 shows changes and events
- [x] 4.7 Build the portfolio view (header, AuM history, mandate bands as min-target-max with actual marked and out-of-band statement, holdings table with instrument links, LTV history with margin-trigger rule); verify an out-of-band weight is marked and a no-facility portfolio omits LTV

## 5. Instruments and market

- [x] 5.1 Build the instruments list with held filter and USD-by-asset-class chart; verify the held filter hides zero-held instruments
- [x] 5.2 Build the instrument view (master data with underlying, price path, holders linked to client and portfolio with USD-per-client chart, outlook with context and evidence or gap notice); verify an instrument without an outlook shows the gap and the rest renders
- [x] 5.3 Build the market view (outlook summary and views, changes since previous outlook, unaddressed events, evidence in the drawer); verify evidence opens the drawer
- [x] 5.4 Build the event timeline with severity, channels and derived reach (clients and instruments linked); verify selecting a client under an event opens the client view

## 6. Scenarios

- [x] 6.1 Build the scenario tab on the client view: picker from `/api/scenarios`, result layout (headline, reach, premise, mirrored event, caveat, collateral, bands crossed, position table), the "Illustrative, not computed" banner and neutral breach colours; verify no scenario names or premise text exist in the UI source (grep) and the banner shows for a placeholder payload

## 7. Integration and docs

- [x] 7.1 Document running the UI with the API (proxy, env, type generation, ports) in `dashboard-ui/README.md` and the root README, and verify the documented commands start both and load the overview
- [x] 7.2 End-to-end walkthrough in the browser against the 2026-08-26 run: overview to action to drawer to client to portfolio to instrument to market and back, with API-down and gap states checked; verify `pnpm check`, `pnpm build` and the unit tests pass and fix any broken link or console error found
