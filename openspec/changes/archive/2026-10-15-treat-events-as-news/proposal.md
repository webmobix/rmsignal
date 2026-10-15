# Proposal

## Why

The sample `event_log` holds real, dated events that moved markets (conflict, oil, central banks, yields). In the MVP these events are the only news there is, but `news.list` answers `no_data` ("no news source is configured") and merely attaches the events as `curated_events`. Consequences: every analysis that calls it records a false "no news" gap, and the prompts give no instruction to treat the events as established facts to be cited when explaining *why* something moved. The coming outlook agents (`add-market-outlook`, `add-instrument-outlook`) depend on events being first-class, trusted reasons.

## What Changes

- `news.list` returns the curated event log as **news items** (date, type, region, description, transmission, severity, source `event_log`) with status `ok`. It returns `no_data` only when no event is dated on or before `as_of`. `events.list` is unchanged.
- Agent prompts state that returned events are established, important facts: use them as reasons, cite them, weigh `severity`, never attribute a cause to an event that was not returned.
- Remove the false gap: a run that read events does not report "no news source".
- Docs (`docs/contracts.md` tool table, `docs/agents.md`) describe the event log as the MVP news source and that an external feed can later be added behind the same tool.

## Capabilities

### New Capabilities
<!-- None -->

### Modified Capabilities
- `agent-tools`: the news tool serves the curated event log as news instead of `no_data`.
- `analysis-agents`: events returned by tools are treated as valid, important reasons.

## Impact

- Code: `tools/domain_tools.py` (`news_list`, remove `NO_NEWS_SOURCE`), `agents/prompts.py` (`COMMON_RULES`), stub plans and tests that assert the old `no_data` behaviour, docs.
- No change to data, point-in-time rules or the output guard (numbers inside event text already count as evidence).
- Out of scope: an external news feed, event relevance scoring (see `add-instrument-outlook`), changes to `events.list`.
