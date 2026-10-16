# Tasks

## 1. Logging core

- [x] 1.1 Add `rm_dashboard/llmlog.py` with `LlmCallStats` and `LlmCallLogger` (callback handler: records duration, tokens from `usage_metadata`, outcome; reads run_id/thread_id/agent/subject from call metadata) and verify unit tests for ok, error, no-usage and concurrent calls (threads) pass, including that totals equal the sum of records
- [x] 1.2 Add `llm_logging(runner, out_dir)` context manager (stderr + `run.log` handlers, `RM_LOG_LEVEL`, fresh file, handlers removed on exit, summary logged on exit and on exceptions) and verify a test that both sinks receive the same lines and level `WARNING` suppresses ok records
- [x] 1.3 Add `llm_config(...)` helper and `thread_id` on `RunContext` (new per top-level run, copied by `child()`, set from the session id by `AnalystSession`); verify tests that a child context shares the parent's thread id and two runs get different ones
- [x] 1.4 Make `StubChatModel` return `usage_metadata`, plus a mode without it; verify existing agent tests still pass and a test covers the `n/a` path
- [x] 1.5 Add a test that no prompt, response or client name appears in log output of a run with known names

## 2. Call sites

- [x] 2.1 Pass the config at the graph invokes in `agents/analyst.py` (including child analysts via `RunScope`), `agents/session.py`, `outlook/agent.py` (market and instrument); verify a delegated analyse run logs one record per model call with the parent's run id and thread id and the child agent name
- [x] 2.2 Pass the config at `reconciliation/agent.py::_ask` and `actions/agent.py::_ask`; verify records carry agent `note_reconciler` / the actions agent and one record per client

- [x] 2.3 Add a test that records grouped by thread id match the graph runs: one thread for a Relationship → Portfolio delegation, distinct threads for two parallel clients

## 3. Runners

- [x] 3.1 Enter `llm_logging` in `run_batch`, `run_reconcile`, `run_actions`, `run_outlook` and `run_overview` (overview only if it calls a model; otherwise log a zero-call summary), add `llm` to each `summary.json`; verify each runner test finds `run.log` beside `audit.jsonl` and `summary.json["llm"]` with totals matching the log
- [x] 3.2 Verify the summary is produced for an all-failed batch and for an unchanged outlook (zero calls)
- [x] 3.3 Run `rm-dashboard-analyse` on the seeded database with the stub model and confirm the console shows per-call lines and a closing summary

## 4. Documentation

- [x] 4.1 Document the log format, `RM_LOG_LEVEL`, `run.log` and the `llm` summary in `docs/agents.md`, and verify the example line matches real output from 3.3
