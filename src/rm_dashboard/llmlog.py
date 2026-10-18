"""Operational log of LLM calls: one record per call and one summary per runner. Never logs content."""

import logging
import os
import sys
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler

LOGGER_NAME = "rm_dashboard.llm"
LOG_FILE = "run.log"
LEVEL_ENV = "RM_LOG_LEVEL"
_FORMAT = "%(asctime)s %(levelname)s %(message)s"
_META = "rm_"  # call-metadata keys: rm_run_id, rm_thread_id, rm_agent, rm_subject


def _tok(n: int | None) -> str:
    return "n/a" if n is None else str(n)


class LlmCallStats:
    """Totals over the calls of one runner, safe to update from worker threads."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.started = time.monotonic()
        self._calls: list[dict] = []

    def record(self, **call: Any) -> None:
        with self._lock:
            self._calls.append(call)

    def summary(self, elapsed: float | None = None) -> dict:
        with self._lock:
            calls = list(self._calls)
        elapsed = time.monotonic() - self.started if elapsed is None else elapsed

        def totals(rows: list[dict]) -> dict:
            used = [c for c in rows if c["total_tokens"] is not None]
            return {
                "calls": len(rows), "failed": sum(1 for c in rows if c["outcome"] == "error"),
                "input_tokens": sum(c["input_tokens"] or 0 for c in used), "output_tokens": sum(c["output_tokens"] or 0 for c in used),
                "total_tokens": sum(c["total_tokens"] for c in used), "calls_without_usage": len(rows) - len(used),
                "llm_seconds": round(sum(c["ms"] for c in rows) / 1000, 3),
            }

        by_agent: dict[str, list[dict]] = {}
        for c in calls:
            by_agent.setdefault(c["agent"], []).append(c)
        slowest = max(calls, key=lambda c: c["ms"], default=None)
        return {
            "elapsed_seconds": round(elapsed, 3), **totals(calls),
            "slowest": None if slowest is None else {k: slowest[k] for k in ("agent", "run_id", "thread_id", "ms")},
            "by_agent": {a: totals(rows) for a, rows in sorted(by_agent.items())},
        }


class _LazyFileHandler(logging.FileHandler):
    """Creates (and truncates) its file, and the folder, on the first record: a run without LLM calls leaves no trace."""

    def __init__(self, path: Path) -> None:
        super().__init__(path, mode="w", encoding="utf-8", delay=True)

    def _open(self):
        Path(self.baseFilename).parent.mkdir(parents=True, exist_ok=True)
        return super()._open()


class LlmCallLogger(BaseCallbackHandler):
    """LangChain callback: times each chat-model call and logs identity, duration and token use when it ends."""

    raise_error = False

    def __init__(self, runner: str, logger: logging.Logger | None = None) -> None:
        self.runner = runner
        self.log = logger or logging.getLogger(LOGGER_NAME)
        self.stats = LlmCallStats()
        self._open: dict[Any, tuple[float, dict]] = {}
        self._lock = threading.Lock()
        self._frozen: dict | None = None

    # ---- callbacks ------------------------------------------------------------------------
    def on_chat_model_start(self, serialized, messages, *, run_id, metadata=None, **kwargs):  # noqa: ANN001
        self._start(run_id, metadata)

    def on_llm_start(self, serialized, prompts, *, run_id, metadata=None, **kwargs):  # noqa: ANN001
        self._start(run_id, metadata)

    def on_llm_end(self, response, *, run_id, **kwargs):  # noqa: ANN001
        started = self._pop(run_id)
        if started is not None:
            self._finish(started, "ok", usage=_usage(response))

    def on_llm_error(self, error, *, run_id, **kwargs):  # noqa: ANN001
        started = self._pop(run_id)
        if started is not None:
            self._finish(started, "error", error=type(error).__name__)

    # ---- internals ------------------------------------------------------------------------
    def _start(self, run_id, metadata) -> None:  # noqa: ANN001
        meta = {k[len(_META):]: v for k, v in (metadata or {}).items() if k.startswith(_META)}
        with self._lock:
            self._open.setdefault(run_id, (time.monotonic(), meta))  # setdefault: a handler reached twice counts once

    def _pop(self, run_id):  # noqa: ANN001
        with self._lock:
            return self._open.pop(run_id, None)

    def _finish(self, started: tuple[float, dict], outcome: str, usage: dict | None = None, error: str | None = None) -> None:
        t0, meta = started
        ms = round((time.monotonic() - t0) * 1000)
        u = usage or {}
        i, o = u.get("input_tokens"), u.get("output_tokens")
        t = u.get("total_tokens")
        if t is None and (i is not None or o is not None):
            t = (i or 0) + (o or 0)
        call = {"runner": self.runner, "run_id": meta.get("run_id", "-"), "thread_id": meta.get("thread_id", "-"),
                "agent": meta.get("agent", "-"), "subject": meta.get("subject", "-"), "ms": ms,
                "input_tokens": i, "output_tokens": o, "total_tokens": t, "outcome": outcome}
        self.stats.record(**call)
        line = (f"llm_call runner={call['runner']} run_id={call['run_id']} thread_id={call['thread_id']} agent={call['agent']} "
                f"subject={call['subject']} ms={ms} in={_tok(i)} out={_tok(o)} total={_tok(t)} outcome={outcome}")
        if error:
            self.log.warning(f"{line} error={error}")
        else:
            self.log.info(line)

    # ---- summary --------------------------------------------------------------------------
    def counts(self) -> dict:
        """The deterministic part of the summary (no durations): this is what runners persist in the run summary,
        so that a rerun on the same inputs stays byte-identical."""
        s = self.summary()
        keep = ("calls", "failed", "input_tokens", "output_tokens", "total_tokens", "calls_without_usage")
        return {**{k: s[k] for k in keep}, "by_agent": {a: {k: v[k] for k in keep} for a, v in s["by_agent"].items()}}

    def summary(self) -> dict:
        """Totals so far; the first call fixes the elapsed time, so the file and the log agree."""
        if self._frozen is None:
            self._frozen = self.stats.summary()
        return self._frozen

    def log_summary(self) -> dict:
        s = self.summary()
        self.log.info(f"llm_summary runner={self.runner} elapsed_s={s['elapsed_seconds']} llm_s={s['llm_seconds']} calls={s['calls']} "
                      f"failed={s['failed']} in={s['input_tokens']} out={s['output_tokens']} total={s['total_tokens']} "
                      f"without_usage={s['calls_without_usage']}")
        if s["slowest"]:
            w = s["slowest"]
            self.log.info(f"llm_summary_slowest runner={self.runner} agent={w['agent']} run_id={w['run_id']} thread_id={w['thread_id']} ms={w['ms']}")
        for agent, a in s["by_agent"].items():
            self.log.info(f"llm_summary_agent runner={self.runner} agent={agent} calls={a['calls']} failed={a['failed']} llm_s={a['llm_seconds']} "
                          f"in={a['input_tokens']} out={a['output_tokens']} total={a['total_tokens']} without_usage={a['calls_without_usage']}")
        if s["failed"] or s["calls_without_usage"]:
            self.log.warning(f"llm_summary_warning runner={self.runner} failed={s['failed']} without_usage={s['calls_without_usage']}")
        return s


def _usage(response) -> dict | None:  # noqa: ANN001
    for gens in getattr(response, "generations", None) or []:
        for g in gens:
            u = getattr(getattr(g, "message", None), "usage_metadata", None)
            if u:
                return dict(u)
    tu = (getattr(response, "llm_output", None) or {}).get("token_usage")
    if tu:
        return {"input_tokens": tu.get("prompt_tokens"), "output_tokens": tu.get("completion_tokens"), "total_tokens": tu.get("total_tokens")}
    return None


# ---- the active logger of the running runner ----------------------------------------------------
_active: LlmCallLogger | None = None


def current_llm_log() -> LlmCallLogger | None:
    """The logger of the runner now running. Process-wide, not thread-local: runner workers are threads."""
    return _active


def llm_config(run, agent: str) -> dict:
    """Config for one model/graph invocation: identity metadata, the LangGraph thread and the active logger."""
    cfg: dict[str, Any] = {
        "metadata": {f"{_META}run_id": run.run_id, f"{_META}thread_id": run.thread_id, f"{_META}agent": agent,
                     f"{_META}subject": run.subject},
        "configurable": {"thread_id": run.thread_id},
    }
    if run.llm_log is not None:
        cfg["callbacks"] = [run.llm_log]
    return cfg


def _level() -> int:
    name = os.environ.get(LEVEL_ENV, "INFO").upper()
    return logging.getLevelNamesMapping().get(name, logging.INFO)


@contextmanager
def llm_logging(runner: str, out_dir: Path | str) -> Iterator[LlmCallLogger]:
    """Log LLM calls to stderr and ``<out_dir>/run.log`` (a fresh file once there is a call); log the summary on the way out."""
    global _active
    out = Path(out_dir)
    logger = logging.getLogger(LOGGER_NAME)
    previous_level, previous_propagate = logger.level, logger.propagate
    file_handler = _LazyFileHandler(out / LOG_FILE)
    handlers = [logging.StreamHandler(sys.stderr), file_handler]
    for h in handlers:
        h.setFormatter(logging.Formatter(_FORMAT))
        logger.addHandler(h)
    logger.setLevel(_level())
    logger.propagate = False
    handler, before = LlmCallLogger(runner, logger), _active
    _active = handler
    try:
        yield handler
    finally:
        _active = before
        try:
            if handler.summary()["calls"] == 0:  # nothing to record: console only, the file (and an earlier run's) stays as it is
                logger.removeHandler(file_handler)
            handler.log_summary()
        finally:
            for h in handlers:
                logger.removeHandler(h)
                h.close()
            logger.setLevel(previous_level)
            logger.propagate = previous_propagate
