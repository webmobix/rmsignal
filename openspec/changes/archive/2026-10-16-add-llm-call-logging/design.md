# Design

## Context

Model calls happen in two shapes: Deep Agents graphs (`analyse`, `AnalystSession`, both outlook producers) and direct `model.invoke` calls (`reconciliation/agent.py::_ask`, `actions/agent.py::_ask`). The audit trail has a `model_call` record, written by `RunContext.model_call` before the call; it has no duration, usage or outcome and is not the right place for them (append-only, content hashed, compliance purpose). Runners fan out clients over a `ThreadPoolExecutor`, so logging must be thread-safe. The repo has no logging today (`print` only). See proposal.md for motivation.

## Goals / Non-Goals

**Goals:**
- One place that sees every model call regardless of how it is made, including calls inside delegated agents.
- Run summary that is exact under concurrency.

**Non-Goals:**
- Changing the audit trail, policy checkpoints or report contents.
- Logging prompts/responses, cost in currency, tracing/OTel export, or tool-call logging (already audited).
- Log rotation or shipping.

## Decisions

**Standard library `logging`, not a third-party logger.** The request asked about "the logger library"; the standard module gives console + file handlers, levels and thread safety with no new dependency. Alternative: `loguru` (nicer defaults, extra dependency, replaces handlers rather than composing with uvicorn/langchain loggers). Revisit only if structured/JSON output is needed.

**Capture with a LangChain callback handler (`LlmCallLogger`), not by wrapping models or middleware.** `on_chat_model_start` / `on_llm_end` / `on_llm_error` fire for every chat-model call in graphs, subagents and direct `invoke`, with `run_id` pairs for timing and `usage_metadata` on the returned `AIMessage`. Alternatives: a wrapper chat model (must also be reimplemented for the stub and would hide `bind_tools`), or `wrap_model_call` middleware (misses the direct `invoke` callers and sees retries only partly).

**Identity travels in the call config, not in the handler.** Each `invoke` passes `config={"callbacks": [handler], "metadata": {"run_id", "thread_id", "agent", "subject"}}`; the handler reads the metadata in `on_chat_model_start`. One handler per runner is shared across worker threads. Alternative: a handler per run (many objects, and the summary would need merging). A helper `llm_config(run, agent)` builds the config so call sites stay one line. Because child analysts call `analyse` themselves, the handler is held by `RunContext.llm_log` (copied by `child()`), which defaults to the logger of the runner now running (`current_llm_log()`, process-wide because runner workers are threads), so no function signature changes.

**Thread id groups a graph run.** The thread id is created once where a top-level graph run starts (`analyse` with `top_level=True`, each outlook producer, `AnalystSession`, and the single-call reconciler/actions agents) and is also passed as LangGraph's `configurable.thread_id`. `RunContext` gets a `thread_id` field (default: a new `thread_<hex>`), and `RunContext.child()` copies it, so sub-agents (`_child_runner` builds its scope with `parent.run.child(...)`) and anything called from tools inherit it without extra plumbing. `run_id` keeps its audit meaning; in a batch each client already has its own `RunContext`, so thread ids differ per client. `llm_config` reads both ids from the run, so call sites cannot forget the thread.

**Stats are aggregated in the handler** (`LlmCallStats`, lock-protected): totals and per-agent counts, in/out/total tokens, failures, calls without usage, slowest call. `summary()` returns a dict used both for the final log line(s) and for `summary.json["llm"]`. Unknown usage is `None`, never 0, and is excluded from sums but counted.

**Wiring in runners.** A context manager `llm_logging(runner, out_dir)` (in `rm_dashboard/agents/llmlog.py`) configures the `rm_dashboard.llm` logger with a stderr `StreamHandler` and a `FileHandler(out_dir/run.log, mode="w")`, yields the callback handler, and on exit logs the summary and removes the handlers (so repeated runs in tests do not stack handlers). Format: `time level runner=… run_id=… thread_id=… agent=… ms=… in=… out=… total=… outcome=…`. Runner functions (`run_batch`, `run_reconcile`, `run_actions`, `run_outlook`, `run_overview`) enter the context; the file handler is lazy, so a run without a call creates and truncates nothing.

**`summary.json` holds counts only.** Existing contracts require byte-identical reruns, so durations and the slowest call appear in the log and console only; `summary.json["llm"]` has calls, failures, tokens and per-agent counts. `llmlog.py` is the one module exempt from the test that forbids reading the clock (it measures elapsed time, never data dates).

**Stub model reports usage** (`usage_metadata` from character counts), so the pipeline is testable and the "no usage" path is covered with a separate stub mode.

## Risks / Trade-offs

- [Provider omits usage on some calls, e.g. streaming or gateway quirks] → logged as `n/a`, counted in `calls_without_usage`; set `stream_usage` on `ChatOpenAI` if the gateway supports it.
- [Callbacks not propagated into a nested call] → explicit config at every `invoke`; a test asserts the number of records equals the number of model calls in a delegated run.
- [Handlers leak between runs or tests] → handlers are removed on context exit.
- [A client name leaking via an exception message] → error records log only the exception type, not its text.
- [File I/O per call under concurrency] → `logging` serialises writes per handler; volume is low (one line per call).

## Migration Plan

Additive. No data migration; old output folders simply lack `run.log` and `llm`. Rollback is removing the context manager calls.
