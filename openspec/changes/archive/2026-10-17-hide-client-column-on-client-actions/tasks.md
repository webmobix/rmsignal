# Tasks

## 1. Hide the Client column on the client page

- [x] 1.1 Add an optional `hideClient` prop to `ActionTable` in `dashboard-ui/src/features/overview/ActionList.tsx` that omits the Client column. Verify the Overview and Actions page tests still pass.
- [x] 1.2 Pass `hideClient` from `dashboard-ui/src/features/clients/ActionsNotes.tsx`. Verify with a test that the client Actions tab has no "Client" column header and that the Overview and Actions page still do.
