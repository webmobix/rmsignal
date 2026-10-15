# Tasks

## 1. News tool

- [x] 1.1 Change `news_list` to return event-log items (`data = {news, source}`), status `ok` with events and `no_data` with reason when none; remove `NO_NEWS_SOURCE` and `curated_events`; verify tests for events present, none before `as_of`, and no look-ahead
- [x] 1.2 Update the tool description and the tool table in `docs/contracts.md`; verify `tests/test_docs.py` still passes

## 2. Agent behaviour

- [x] 2.1 Add the events-are-facts rule to `COMMON_RULES` in `agents/prompts.py`; verify the prompt tests still pass
- [x] 2.2 Update stub plans and existing tests that expect the old `no_data`/`curated_events` shape; verify a run that calls `news.list` yields no `no_data` gap for it
- [x] 2.3 Add a guard test that a finding citing an event and quoting a figure from its description (for example the Brent price) is kept

## 3. Docs

- [x] 3.1 State in `docs/agents.md` that the event log is the MVP news source and that an external feed can be added behind `news.list`; verify wording against the tool
