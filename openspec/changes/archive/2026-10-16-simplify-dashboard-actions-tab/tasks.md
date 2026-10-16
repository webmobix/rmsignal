## 1. Action selection logic

- [x] 1.1 Add `urgentActions(actions)` (importance in critical/high, horizon `immediate`, not `data_quality`) to `dashboard-ui/src/features/overview/actions.ts`; unit-test the mixed-importance, mixed-horizon and data-quality scenarios in `actions.test.ts` (`pnpm test`)
- [x] 1.2 Add a horizon filter to `splitActions` (applies to risks only) with tests that tier narrows the lane and horizon does not

## 2. Actions page and nav

- [x] 2.1 Create `features/actions/ActionsPage.tsx` with the tier (URL-backed), category and horizon filters, the full risk table and the data quality and coverage lane, reusing `ActionTable`/`TierFilter`; verify by component test for `?tier=low`, horizon filter and empty lane
- [x] 2.2 Add `routes/actions.tsx` with `validateSearch` for `tier`, regenerate `routeTree.gen.ts`, and add "Actions" to `NAV` in `TopBar.tsx`; verify the tab is active at `/actions` and the evidence drawer opens from a row

## 3. Dashboard simplification

- [x] 3.1 Reduce `ActionsPanel` to the urgent table, empty notice and "N more actions" link to `/actions`; remove filters and the data-quality lane from the home page; update the existing `ActionsPanel`/overview tests accordingly
- [x] 3.2 Add optional link support to `MetricStrip` and link each tier count in `OverviewPage` to `/actions?tier=<tier>`; verify the medium count navigates to the filtered Actions page in a test

## 4. Specs and docs

- [x] 4.1 Update any docs that describe the home page action list (grep `docs/` and `README.md` for "Next actions" / data-quality lane); run `pnpm lint`, `pnpm test` and `openspec validate simplify-dashboard-actions-tab`, and check the pages manually with the app running
