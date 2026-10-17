# Tasks

## 1. Foundation in styles.css

- [x] 1.1 Remove `font-size: 15px` from `body` and add the `--text-display` / `--text-display--line-height` tokens to `@theme` in `dashboard-ui/src/styles.css`; verify `pnpm build` succeeds and `text-display` is generated
- [x] 1.2 Convert `.eyebrow`, `.data-table th/td` and `.metric-value` to scale values (`text-xs`, `text-xs`, `text-sm`, `text-4xl`) via `@apply`; verify `grep -nE 'font-size: [0-9]' dashboard-ui/src/styles.css` returns nothing

## 2. Shared components

- [x] 2.1 Update `PageHeader` (h1 to `text-display`, lede to no size class), `TopBar`, `Tabs`, `Avatar`, `TierBadge`, `MetricStrip`, `ViewCard`, `Drawer`, `ChartFrame`, `StateBoundary`, `DataTable` per the design mapping; verify `git grep -nE 'text-\[' dashboard-ui/src/components` returns nothing
- [x] 2.2 Bump chart axis `fontSize` from 10 to 12 in `LineTrend.tsx` and `ClientMatrix.tsx`; verify charts render without clipped labels

## 3. Feature pages

- [x] 3.1 Update overview, actions and market features (`OverviewPage`, `ActionsPanel`, `ActionList`, `MeetingPrep`, `ClientMatrix`, `EvidenceDrawer`, `ActionsPage`, `MarketPage`); verify no `text-[` remains in those files
- [x] 3.2 Update client and instrument features (`ClientsPage`, `ClientPage`, `Summary`, `Health`, `PortfolioList`, `ActionsNotes`, `SnapshotCompare`, `InstrumentsPage`, `InstrumentPage`); verify no `text-[` remains in those files
- [x] 3.3 Update portfolio and scenario features (`PortfolioPage`, `BreachSection`, `SectorSection`, `CallSheet`, `callsheetSections`, `ScenarioTab`); verify no `text-[` remains in those files

## 4. Prose audit and verification

- [x] 4.1 Audit remaining `text-xs` / `text-sm` on `<p>`, `<li>`, `<blockquote>` and sentence wrappers and remove them; verify `git grep -nE '<p[^>]*text-(xs|sm)' dashboard-ui/src` returns nothing and any remaining `text-xs`/`text-sm` is a label, badge, chip or table cell
- [x] 4.2 Verify `git grep -nE 'text-\[' dashboard-ui/src` returns nothing, and `pnpm test`, `pnpm lint` and `pnpm build` pass in `dashboard-ui`
- [x] 4.3 Visually check the overview, client, portfolio call sheet, evidence drawer, scenario tab and tables in the browser at desktop and narrow widths; fix any overflow or wrapping regressions and confirm prose is never smaller than body text
- [x] 4.4 If `add-market-breadth` has landed or is in progress, reconcile `MarketPage.tsx` so its new markup follows the same scale; verify no arbitrary text sizes were reintroduced
