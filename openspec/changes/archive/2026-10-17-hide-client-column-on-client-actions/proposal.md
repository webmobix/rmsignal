# Proposal

## Why

The Actions table on the client page's Actions tab has a Client column. Every row shows the same client, because the page is already scoped to one client. The column takes space and tells the RM nothing.

## What Changes

- The actions table on the client page's Actions tab no longer shows the Client column.
- The Overview and the Actions page keep the Client column, since they list actions across clients.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `client-portfolio-ui`: the "Client actions and notes" requirement now states that the client's actions list omits the Client column.

## Impact

- `dashboard-ui/src/features/overview/ActionList.tsx`: the shared `ActionTable` needs to be able to hide the Client column.
- `dashboard-ui/src/features/clients/ActionsNotes.tsx`: passes the option to hide it.
- Tests for the client Actions tab.
- No API or data changes.
