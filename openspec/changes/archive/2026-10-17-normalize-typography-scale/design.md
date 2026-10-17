# Design

## Context

`dashboard-ui` is Tailwind v4 with tokens in `src/styles.css`. `body` sets `font-size: 15px`, `.eyebrow`, `.data-table th/td` and `.metric-value` hard-code px sizes, components use ~90 arbitrary `text-[..]` values, and chart configs hard-code `fontSize: 10`. Tailwind v4 exposes its scale as `--text-*` variables with matching `--text-*--line-height`. See proposal.md for motivation.

## Goals / Non-Goals

**Goals:**
- One size system: Tailwind scale plus one named fluid token.
- Prose never below normal; small sizes confined to labels.

**Non-Goals:**
- No colour, spacing, font-family or layout redesign beyond fixes for overflow caused by larger text.
- No change to data, API or test assertions.

## Decisions

**Base 16px.** Delete the `font-size: 15px` on `body` (keep `line-height: 1.6`). Normal then equals `text-base`, so `text-sm`/`text-xs` are genuinely smaller and the scale is coherent. Alternative: keep 15px and treat it as normal; rejected because `text-sm` (14px) would be near-identical to normal and `text-base` larger.

**Mapping.**

| Role | Before | After |
|---|---|---|
| Prose, list items, descriptions, wrappers around sentences, empty/loading messages | `13`, `13.5`, `14`, `12.5`, `16px`, `text-xs`, `text-sm` | no size class |
| UI chrome: nav, tabs, filter pills, labels, selects | `13px`, `text-xs` | `text-sm` |
| Badges, avatar, metric hints, tier glyph, uppercase `h3` eyebrows | `9`, `11px`, `text-xs` | `text-xs` |
| `h3` | `17`, `18px` | `text-lg` |
| Section `h2` | `22px` | `text-xl` |
| Page-section `h2` | `26px` | `text-2xl` |
| Big numerals | `20`, `22px` | `text-xl` |
| Top bar brand mark | `17px` | `text-lg` |
| `.metric-value` | `34px` | `text-4xl` (36px) |
| `.data-table td` / `th` | `13.5px` / `10.5px` | `text-sm` / `text-xs` |
| `.eyebrow` | `10.5px` | `text-xs` |
| Chart axis `fontSize` | `10` | `12` |

The 22 and 26px headings shrink slightly (to 20 and 24px); accepted as the cost of using the standard scale. Where a utility and a component class both set size (e.g. `.eyebrow`), use `@apply text-xs` in the component class rather than a px literal.

**Headline token.** Add to `@theme`:
```css
--text-display: clamp(var(--text-3xl), 3.6vw, var(--text-4xl));
--text-display--line-height: 1.12;
```
`PageHeader` h1 uses `text-display`; the `leading-[1.12]` arbitrary value is dropped. Alternative: inline `text-[clamp(var(--text-3xl),...)]`; rejected as it keeps an arbitrary value in markup.

**Edge cases.** The `max-w-[900px]`-style arbitrary widths and `shadow-[..]` values are not text sizes and are left alone. Muted-colour captions keep their colour classes; only size is removed.

## Risks / Trade-offs

- Text grows ~7% and prose grows more (13px to 16px) → dense views (call sheet, client matrix, evidence drawer, data tables, scenario tab) may wrap or overflow; verify visually in the browser at desktop and narrow widths and adjust layout where needed.
- Hierarchy previously carried by size in muted notes now relies on colour → acceptable; keep `text-ink-muted`/`text-ink-2`.
- Overlap with in-flight `add-market-breadth` on `MarketPage.tsx` → land one first or rebase; edits are class-level only.
