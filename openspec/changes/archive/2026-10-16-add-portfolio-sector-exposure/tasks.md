# Tasks

## 1. Sector look-through calculation

- [x] 1.1 Add `sector_look_through` in `src/rm_dashboard/analytics/` returning direct and look-through groups over one denominator, reusing `parse_underlyings` and `normalise_name`; verify with unit tests for the direct view, a matched underlying, an unmatched underlying, an unresolvable reference, a missing sector and asset-type labels passing through unchanged
- [x] 1.2 Add equal-split basket attribution with the shared `basket_attribution_assumption` flag; verify with a three-underlying test (each gets one third) and that both views sum to 100 within 0.01
- [x] 1.3 Register the method text and document it in `docs/methods.md`; verify the registered method appears where other methods are listed and the doc describes the unclassified groups

## 2. API

- [x] 2.1 Add the `sector_exposure` model and populate it in `get_portfolio` in `src/rm_dashboard/api/portfolios.py`, mapping flags to gaps and handling a portfolio with no positions; verify with API tests for a normal portfolio, one holding structured products, an empty portfolio and an unknown id (404)
- [x] 2.2 Check against the seeded sample at 2026-08-26 that PF-0017 and PF-0023 (which hold structured products) return an `Unclassified (look-through)` group and that every portfolio sums to 100; verify with a test over all portfolios
- [x] 2.3 Regenerate the OpenAPI schema and `dashboard-ui/src/api/schema.ts`; verify the new fields appear and the UI type check passes
- [x] 2.4 Document the new field in `docs/api.md`; verify it matches the response of the running API

## 3. Portfolio view

- [x] 3.1 Add a sector bar chart component under `dashboard-ui/src/components/charts/` with a neutral unclassified bar and no limit marker; verify with a component test for ordering, labels and the unclassified bar
- [x] 3.2 Add the section with a direct / look-through toggle and the unclassified note to `PortfolioPage.tsx`; verify with a test that toggling switches the data and that an empty exposure shows the empty state
- [x] 3.3 Run the dashboard against the seeded database and look at PF-0013, PF-0003 and PF-0017; verify the chart renders, the toggle works and the page has no console errors

## 4. Integration

- [ ] 4.1 Run the Python test suite and the dashboard tests, lint and type check; verify all pass
