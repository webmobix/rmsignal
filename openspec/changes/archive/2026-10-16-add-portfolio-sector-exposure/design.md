# Design

## Context

Look-through exists only in `analytics/concentration.py`: `client_concentration` aggregates named entities across a client's portfolios and has no sector dimension. `analytics/exposure.py` already groups positions by a column (including `sector`) with an `unclassified` group and a stated denominator, but it works on holdings only and does not see structured-product underlyings. `api/portfolios.py` assembles `PortfolioDetail` from holdings and the instrument master. The portfolio page renders sections with charts from `components/charts/`. See proposal.md for motivation.

Checked against the sample data: of six structured products, underlying names resolve for five, and of those underlyings Helios Cloud Systems (Information Technology), Golden Harbour Properties (Real Estate), Pacific Orient Shipping (Industrials) and Bara Nusantara Energy (Energy) match an instrument by normalised name. Global Energy Majors ADR, Gulf Marine Services and XAU spot match none, and SYN-SP-0506 ("Asia Banks Basket") is not resolvable. So the unclassified group is real and expected, not an edge case.

## Goals / Non-Goals

**Goals:**
- One pure function that returns direct and look-through sector exposure for one portfolio's positions, both over the same denominator.
- Reuse the existing underlying parser and name normaliser so the portfolio view and the client look-through agree on what an underlying is.
- Make everything that is not classified visible, with a flag per cause.

**Non-Goals:**
- No sector limits, breaches or mandate comparison.
- No new data columns, no sector mapping table, no fuzzy or manual matching beyond the existing name normalisation.
- No change to the client-level concentration result or its HHI.
- No batch runner, report file or model call.

## Decisions

**New calculation `sector_look_through` in `analytics/`, beside `exposure.py`.** It takes the portfolio's positions and the instrument master and returns a `Calc` with `direct` and `look_through` group lists. Alternative: extend `client_concentration`; rejected because it is keyed by entity and client scope, and sector grouping would complicate its HHI and single-name outputs.

**Direct view reuses `exposures()`.** Same grouping, same `unclassified` handling and flag, so the two stay consistent. The look-through view starts from the same positions and only replaces structured products.

**Classify an underlying by name match against non-structured instruments.** Build a lookup `normalise_name(instrument_name) -> sector` from the instrument master excluding structured products. A match with a null or empty sector is unclassified. Alternative: an explicit `underlying_sector` column; rejected, as the proposal adds no data.

**Group names.** Value that cannot be classified is reported as `Unclassified (look-through)` in the look-through view and `unclassified` in the direct view (the existing constant). In the look-through view, a position whose own sector is missing stays `unclassified`. Asset-type labels pass through unchanged.

**Basket attribution equal-weight, stated.** Same assumption and flag code (`basket_attribution_assumption`) as the client concentration, so the wording is shared.

**Denominator is portfolio value in the portfolio's base currency (`market_value_base`)**, matching the mandate bands on the same page, and is returned with its label.

**API: add a `sector_exposure` object to `PortfolioDetail`** with `denominator`, `denominator_label`, `direct`, `look_through` (each a list of `{name, value, exposure_pct, positions, contributors?}`) and quality flags mapped to the existing gaps mechanism. Additive; the OpenAPI schema and `dashboard-ui/src/api/schema.ts` are regenerated.

**UI: one horizontal bar chart (the `BarList` pattern) with a toggle**, direct by default. Bars rather than a donut: more than ten groups occur and bars stay legible. Unclassified is drawn in a neutral tone and labelled; no limit marker.

## Risks / Trade-offs

- [Name matching misses an underlying, e.g. "Global Energy Majors ADR" vs the fund "Global Energy Majors Equity Fund"] → reported as unclassified with a flag naming it; the user chose not to add mapping data.
- [Equal basket split misstates real sensitivity] → stated in the response and the UI note; same assumption as the client view.
- [Non-sector labels (Corporate, Sovereign, Diversified) dominate the chart and make "sector" look incomplete] → shown as their own groups per the proposal; a short note under the chart says they are asset-type labels in the source data.
- [Look-through attribution to an unclassified bucket can make large products look like missing data] → the unclassified amount is stated in the chart note.
