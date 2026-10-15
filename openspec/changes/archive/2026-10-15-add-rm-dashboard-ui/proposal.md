# Proposal

## Why

An RM on the Asia desk has twenty clients and needs to know who to call first, why, and on what evidence, then drill into the client, portfolio, instrument and market behind each action. The analysis output exists but has no interface. The `sample/SY` app shows the intended feel (editorial, ivory and navy, evidence-first) but runs on a different data model; the bootstrapped TanStack Start app in `dashboard-ui/` is empty.

## What Changes

- Build **RMSignal**, the RM dashboard, in `dashboard-ui/` (TanStack Start, TanStack Router file routes, TanStack Query, Tailwind CSS v4). It is a client of the FastAPI read API from `add-rm-read-api`; no Server Functions, no authentication.
- **Design language** carried over from the sample: ivory canvas, deep navy ink, brick alert, Source Serif 4 headings with Public Sans body, flat surfaces, hairline rules, tabular numbers, single light theme. Expressed as Tailwind v4 theme tokens (`@theme`) and a reusable component library (page header, metric strip, tier badge, data table, chart frames, side drawer, tabs, empty and gap states).
- **Branding**: portal named *RMSignal*, bank named *Global WM Bank* (text mark, no Julius Baer logo or name). A mocked avatar in the top bar shows the initials and name of the RM from `/api/rm`.
- **Point in time**: every screen shows the data for the latest `as_of` returned by the API, displayed in the masthead.
- **Screens**
  - *Overview*: metric strip, ranked next actions filterable by tier and category, a data-quality lane kept apart from client risks, meeting prep for the next two weeks, and the **client matrix** (AuM against urgency, each client a point).
  - *Evidence drawer*: opens from the right on any action or finding, shows what, why, linked findings and the evidence behind them, with links onward to client, portfolio, instrument.
  - *Clients* list and *Client* view: a **consolidated summary across all portfolios** (total AuM, stacked AuM history with event markers, combined allocation, concentration and look-through, currency, liquidity, credit headroom) above the **list of the client's portfolios**; client actions, notes against data, snapshot comparison.
  - *Portfolio* view: AuM history, mandate bands against actual, holdings, LTV against the margin trigger.
  - *Instrument* view: price path, holders across the book, outlook where one exists.
  - *Market* view: market views and outlook, event timeline with channels and the clients and instruments they reach.
  - *Scenarios*: scenario picker and result layout from the sample, populated from the backend placeholder payloads and clearly marked "Illustrative, not computed".
- Everything is linked: an id in any view is a link to its view.

## Capabilities

### New Capabilities
- `dashboard-shell`: app frame, design tokens, branding, mocked RM avatar, navigation, data fetching conventions, loading, error and gap states, reusable components.
- `rm-overview-ui`: overview page, action list, client matrix, meeting prep, evidence drawer.
- `client-portfolio-ui`: clients list, client view with consolidated summary and portfolio list, portfolio view, snapshot comparison.
- `instrument-market-ui`: instrument view, market view and event timeline.
- `scenario-ui`: scenario picker and result view backed by placeholder data.

### Modified Capabilities
<!-- None -->

## Impact

- `dashboard-ui/`: routes, components, query layer, Tailwind theme, Vite dev proxy to the API. Adds `@tanstack/charts` for all charts as the only new runtime dependency.
- Depends on `add-rm-read-api`; implementation starts after it. No change to the Python analysis code.
- Out of scope: authentication, writing anything back (accepting or rejecting actions), real scenario results, dark theme, mobile-first layout (desktop and tablet are the targets), multiple RMs, internationalisation.
