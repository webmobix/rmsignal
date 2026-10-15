# RMSignal (dashboard-ui)

The RM dashboard for the Asia desk of Global WM Bank: a TanStack Start app (TanStack Router file routes, TanStack Query, TanStack Table, TanStack Charts, Tailwind CSS v4). It is a client of the FastAPI read API in `src/rm_dashboard/api` (see `../docs/api.md`) and shows the data for the latest `as_of`. There is no sign-in; the avatar is mocked from `/api/rm`.

## Run it

The UI needs the API running, which needs a seeded database and a persisted run folder (`reports/<as_of>/`, produced by the analysis batch; see the root README).

```bash
# 1. API, from the repository root (port 8765 is what the UI proxy expects)
uv run rm-dashboard-serve --db rm.db --port 8765

# 2. UI, from dashboard-ui/
pnpm install
pnpm dev            # http://localhost:3000
```

`/api` is forwarded to the API by Nitro `routeRules` in `vite.config.ts` (Vite's `server.proxy` is bypassed by Start's server handler). Point it elsewhere with `RM_API_URL`:

```bash
RM_API_URL=http://127.0.0.1:8000 pnpm dev
```

## Types from the API

TypeScript types come from the API's OpenAPI schema and are committed in `src/api/schema.ts`. Regenerate them with the API running:

```bash
pnpm gen-api        # reads $RM_API_URL or http://127.0.0.1:8765/openapi.json
```

## Scripts

| Command | Does |
| --- | --- |
| `pnpm dev` | dev server on port 3000 |
| `pnpm build` | production build |
| `pnpm test` | unit and component tests (vitest) |
| `pnpm check` | Biome format, lint and import order |
| `pnpm generate-routes` | regenerate `src/routeTree.gen.ts` |

## Structure

- `src/routes/`: file routes `/`, `/clients`, `/clients/$clientId`, `/portfolios/$portfolioId`, `/instruments`, `/instruments/$instrumentId`, `/market`. The evidence drawer is URL state on every route: `?action=`, `?evidence=` or `?finding=`.
- `src/api/`: typed fetch client (`client.ts`), query helpers (`queries.ts`; every query key starts with the `as_of`), generated `schema.ts`.
- `src/components/`: shared components (shell, table, drawer, tabs, state boundary, `ChartFrame` and `charts/`).
- `src/features/`: one folder per screen.
- `src/styles.css`: design tokens (`@theme`). Components use tokens, not literal colours.

Charts render client-only (`ChartFrame`); the surrounding page still server-renders. Scenario content is placeholder data from the backend and is marked "Illustrative, not computed".
