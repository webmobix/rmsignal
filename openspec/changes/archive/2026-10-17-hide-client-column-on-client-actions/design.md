# Design

## Context

`ActionTable` in `overview/ActionList.tsx` is shared by the Overview, the Actions page and the client Actions tab. Its column set is a module-level constant that includes `client_name`.

## Goals / Non-Goals

**Goals:**
- Hide the Client column on the client page only.

**Non-Goals:**
- Changing the other columns, the sort or the API.

## Decisions

- Add an optional `hideClient` prop to `ActionTable`. When set, it filters the `client_name` column out of the column list (a second constant built once at module level, so the column array stays stable between renders). `ActionsNotes` passes it. The default keeps the Client column, so the Overview and Actions page need no change.
- Alternative considered: a separate client-scoped table component. Rejected because it would duplicate six column definitions.

## Risks / Trade-offs

- Sort state is keyed by column id and the initial sort is on `rank`, so removing a column does not affect it.
