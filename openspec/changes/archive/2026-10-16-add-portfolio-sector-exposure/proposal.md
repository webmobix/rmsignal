# Proposal

## Why

An RM sees asset-class bands for a portfolio but not what sectors it is exposed to, and structured products hide their underlyings: a Conservative portfolio can hold 50% real estate, or a Growth portfolio 64% technology, without any view showing it. Look-through exists today only per client and per named entity (`analytics/concentration.py`), never as a sector view of one portfolio.

## What Changes

- Add a per-portfolio sector exposure calculation with two views: **direct** (each position by its instrument's `sector`) and **look-through** (structured products replaced by their referenced underlyings, each classified by the sector of the instrument it matches by normalised name).
- Underlyings that match no instrument, products whose underlying cannot be resolved, and positions with no sector go to an explicit `Unclassified (look-through)` / `unclassified` group. No sector data is added or hand-mapped.
- Sector labels in the data that are asset types rather than sectors (`Diversified`, `Corporate`, `Sovereign`, `Cash`, `Gold`, `Multi`, `Macro`) are shown as their own groups and are not remapped.
- Basket products attribute value equally to each underlying; the view states this as an assumption.
- `GET /api/portfolios/{id}` returns the sector exposure (direct and look-through) with its denominator and quality flags.
- The portfolio view shows a sector chart with a direct / look-through toggle.
- Informational only: no sector limits exist in the mandates, so nothing is checked against the mandate.
- Computed on demand from the seeded database; no batch runner and no new data columns.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `portfolio-analytics`: adds a per-portfolio sector exposure with look-through to structured-product underlyings.
- `client-portfolio-api`: the portfolio detail response includes the sector exposure.
- `client-portfolio-ui`: the portfolio view shows the sector chart with a direct / look-through toggle.

## Impact

- Code: `src/rm_dashboard/analytics/` (new sector look-through calculation reusing `parse_underlyings` and `normalise_name` from `concentration.py`), `src/rm_dashboard/api/portfolios.py` (response model and assembly), `dashboard-ui/src/features/portfolios/PortfolioPage.tsx` and a chart under `dashboard-ui/src/components/charts/`, regenerated API schema in `dashboard-ui/src/api/schema.ts`.
- API: additive fields on `PortfolioDetail`; no breaking change.
- Data: none. Reads `holdings` and `instruments` already seeded.
- Out of scope: sector limits or mandate checks, sector data for unmatched underlyings, outlook views per sector (covered later by the call sheet change).
