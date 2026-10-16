# Proposal

## Why

Agent runs take a long time and there is no way to see where the time and tokens go. Tool calls are audited, but a model call leaves only a pre-call audit record (message count, no outcome), so duration, token use and failures of the LLM calls themselves are invisible.

## What Changes

- One log line per LLM call, written when the call ends (or fails): `run_id`, `thread_id`, agent, runner, duration, input, output and total tokens, outcome.
- A run summary logged when each runner finishes: wall time, number of calls, input/output/total tokens, a breakdown per agent, the slowest call, and the number of failed calls and of calls that reported no usage.
- Logs go to the console (stderr) and to a file beside each runner's output (`run.log`, next to `audit.jsonl`), using Python's standard `logging` module. Level is configurable with `RM_LOG_LEVEL`.
- The same summary is added to the runner's `summary.json` under `llm`.
- Prompts and responses are never logged (personal data stays out of logs; the audit trail is unchanged).
- The deterministic stub model reports token usage so the feature is testable without a gateway.

No behavior of reports, tools, policy or the audit trail changes.

## Capabilities

### New Capabilities
- `llm-call-logging`: per-call and per-run observability of LLM calls (identity, timing, token use) for every runner, to console and file.

### Modified Capabilities
<!-- none: audit and policy requirements are unchanged -->

## Impact

- Code: `rm_dashboard/agents` (new logging callback and stats, stub model usage), `rm_dashboard/policy/runtime.py` (optional thread id on `RunContext`), the five runners in `rm_dashboard/runners/` (outlook, analyse/batch, reconcile, actions, overview if it calls a model) and the agents that invoke a model (`agents/analyst.py`, `agents/session.py`, `outlook/agent.py`, `reconciliation/agent.py`, `actions/agent.py`).
- Dependencies: none added (standard library `logging`).
- Docs: `docs/agents.md`.
- Output: a new `run.log` file per runner output folder; `summary.json` gains an `llm` key.
