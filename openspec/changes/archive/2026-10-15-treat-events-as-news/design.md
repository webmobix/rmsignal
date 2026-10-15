# Design

## Context

`events_list` and `news_list` both read `repo.events(as_of)` (event-dated, no look-ahead). `news_list` marks the result `no_data` with `NO_NEWS_SOURCE`, so `assemble_report` adds a `no_data` gap whenever an analyst calls it (`NO_DATA_STATUSES`). `evidence_numbers` already extracts numbers written inside strings, so figures in event descriptions (for example "USD 120") are valid evidence. See proposal.md.

## Goals / Non-Goals

**Goals:** events act as news and as trusted reasons; no false gap.
**Non-Goals:** a real news feed, ranking or filtering events, changing `events.list`.

## Decisions

1. **`news.list` = event log as news.** Same repository call; each row becomes an item with `source: "event_log"` and the unchanged fields. Status `ok` when at least one event is dated on or before `as_of`, else `no_data` with reason "no news dated on or before as_of". *Alternative:* delete `news.list` and point agents at `events.list`: rejected because the name is the stable contract that a future external feed will fill, and agent cards/allow-lists already reference it.

2. **Result shape.** `data = {"news": [items], "source": "event_log"}`; the `curated_events` key is removed. Tool description: "News for the period: dated market-moving events from the curated event log, up to as_of. No external news feed yet."

3. **Prompt rule in `COMMON_RULES`.** "Events and news returned by tools are established facts. Use them as reasons for market and price movements and cite them. Weigh severity. Do not name a cause that no returned event supports." Reuses the existing instruction that agents must not invent news.

4. **No guard change.** Citation and number grounding already cover event text; a test pins this.

## Risks / Trade-offs

- [Tests and stub plans assert `no_data`] → update them; add a test that a run reading news has no `no_data` gap from it.
- [Future feed mixes sources] → each item carries `source`, so provenance stays visible.
- [Overweighting a thin log] → mitigated by the honest-uncertainty rule: absence of an event is not evidence of absence, and agents still report gaps for missing data.
