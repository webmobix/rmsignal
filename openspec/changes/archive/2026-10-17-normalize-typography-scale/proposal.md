# Proposal

## Why

Text sizing in `dashboard-ui` is inconsistent. About 90 components use arbitrary `text-[13px]`, `text-[22px]` and similar values, the body overrides Tailwind's 16px base with 15px, and roughly 40 `<p>` blocks (descriptions, rationales, notes) use `text-xs` or `text-sm`, which is smaller than body text. Prose is hard to read and the scale cannot be reasoned about.

## What Changes

- Remove the `font-size: 15px` override on `body`, so normal text is Tailwind's 16px (`text-base`).
- Replace every arbitrary `text-[..]` size with either no size class (inherit normal) or a Tailwind scale class (`text-xs`, `text-sm`, `text-lg`, `text-xl`, `text-2xl`, ...).
- Blocks of text (paragraphs, list items, descriptions, rationales, notes, captions, empty and loading messages) use no size class and are never smaller than normal.
- UI chrome (nav, tabs, filter pills, form labels and inputs) uses `text-sm`. Badges, avatar initials, metric hints and uppercase eyebrow headings use `text-xs`.
- Headings map to the scale: `h3` to `text-lg`, section `h2` to `text-xl` / `text-2xl`, big numerals to `text-xl`.
- Add a `--text-display` theme token (`clamp(var(--text-3xl), 3.6vw, var(--text-4xl))`, line-height 1.12) for the page `h1`, replacing the arbitrary clamp and `leading-[1.12]`.
- Convert hard-coded CSS sizes in `styles.css` (`.eyebrow`, `.data-table th/td`, `.metric-value`) to Tailwind scale values; bump chart axis font sizes from 10 to 12.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `dashboard-shell`: adds a typography requirement to the design language (Tailwind scale only, no arbitrary sizes, prose never below normal, 16px base).

## Impact

- `dashboard-ui/src/styles.css` (body size, `@theme` token, component classes).
- Components and pages under `dashboard-ui/src/components` and `dashboard-ui/src/features` that carry `text-[..]`, `text-xs` or `text-sm`.
- Chart configs in `LineTrend.tsx` and `ClientMatrix.tsx` (axis `fontSize`).
- Overall text grows about 7%; dense views (call sheet, client matrix, evidence drawer, tables) need a visual check for overflow.
- May overlap with the in-flight `add-market-breadth` change on `MarketPage.tsx`.
- No API, data or test-assertion changes (existing tests do not assert text sizes).
