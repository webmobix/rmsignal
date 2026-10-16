# Proposal

## Why

Mandate breaches are computed but the RM's own knowledge of them is not: a client who asked for a gold overweight with a waiver (N-010) and a client who never knew about an excluded energy fund (N-008) produce the same `mandate_drift` action as a breach nobody has discussed. The binding sustainability exclusions of the Sustainable Balanced mandate are not checked at all: PF-0007 holds Global Energy Majors Equity Fund (11.1%) and Sunrise Palm Resources (10.2%) with no breach raised.

## What Changes

- Compute a **sustainability-exclusion breach** deterministically in the analysis stage: a managed portfolio whose mandate carries binding exclusions that holds an instrument flagged `sustainability_excluded` (directly or through a structured product's underlying) is a breach with its own evidence, reported in the client report and raising a `mandate_drift` action. Flagged instruments in mandates without binding exclusions are not breaches.
- Add a **separate mandate-reconciliation stage** (`rm-dashboard-mandate-reconcile`), run after note reconciliation and before actions. Per portfolio and per computed breach (asset-class band, single-position limit, exclusion) it reads the client's RM notes up to `as_of` and assigns one status:
  - `no_note`: nothing in the notes bears on the breach. This is the neutral baseline, not a finding.
  - `acknowledged`: a note shows the RM and client know of the breach.
  - `client_directed`: a note shows the client asked for something outside the mandate (including a claimed waiver). Flagged and given a review action; the breach stays flagged and the waiver is quoted, never evidence.
  - `contradicted`: a note says the book is aligned or within limits and the computed evidence disagrees.
- The model only classifies notes against breaches the system computed; every result cites a breach evidence id and a note id. Notes are matched to the right portfolio of a multi-portfolio client, or reported as ambiguous.
- The actions stage reads the mandate-reconciliation result: status sets the importance floor and wording of `mandate_drift` actions (`no_note` unchanged at high; `acknowledged` a follow-up at medium; `client_directed` a review at high; `contradicted` critical; an exclusion breach is at least high).
- API and UI: the mandate status of a portfolio carries the reconciliation status and the notes behind it (for example "Out of band, waiver claimed (N-010)").
- Narrow the note-reconciliation rule "SHALL NOT assess mandate, limit or policy compliance" so that it names the new stage as the owner of that assessment. The notes-are-quoted rule is kept.

## Capabilities

### New Capabilities

- `mandate-reconciliation`: reconciles computed mandate, position-limit and exclusion breaches with what the RM's notes say about them, per portfolio, with a status per breach.

### Modified Capabilities

- `portfolio-analytics`: adds the sustainability-exclusion breach calculation.
- `note-reconciliation`: the scope rule points mandate assessment to the new stage.
- `client-actions`: actions also read the mandate reconciliation; the importance rubric for `mandate_drift` depends on its status.
- `client-portfolio-api`: the portfolio list entry and portfolio detail carry the reconciliation status per breach.
- `client-portfolio-ui`: the mandate badge and the portfolio view show the status and the notes behind it.

## Impact

- Code: new `analytics` exclusion calculation and an analytics tool in the portfolio analyst's allow-list and prompt; new `mandate_reconciliation` package and runner (`runners/`, `pyproject.toml` script); `actions/` (agent input, rubric, source kinds, guard); `reportsource`/overview reading of the new files; `api/portfolios.py` and `api/clients.py`; dashboard `PortfolioList.tsx`, `status.ts`, `PortfolioPage.tsx`, regenerated `schema.ts`.
- Pipeline: `outlook` → `analyse` → `reconcile` → `mandate-reconcile` → `actions` → `overview`. The new stage needs a model, like `reconcile`.
- Output: `reports/<as-of>/mandate-reconciliation/<client>.json` and `summary.json`.
- Data: none added; reads RM notes, mandates and `sustainability_excluded` already seeded.
- Docs: README pipeline and `docs/agents.md`, `docs/methods.md`.
- Out of scope: sector limits, verifying a waiver against any record (none exists in the data), the call-sheet view.
