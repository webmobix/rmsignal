import json
import logging
import re
import threading
from datetime import date

import pytest
from langchain_core.messages import HumanMessage

from rm_dashboard.agents import StubChatModel
from rm_dashboard.agents.stub import StubModelError
from rm_dashboard.llmlog import LlmCallLogger, llm_config, llm_logging
from rm_dashboard.policy import RunContext
from rm_dashboard.runners import open_registry, run_batch
from rm_dashboard.runners.actions import run_actions
from rm_dashboard.runners.outlook import run_outlook
from rm_dashboard.runners.reconcile import run_reconcile
from rm_dashboard.settings import Settings
from rm_dashboard.store.summary import get_summary

AS_OF = date(2026, 8, 26)


def fields(line: str) -> dict:
    return dict(re.findall(r"(\w+)=(\S+)", line))


def calls(text: str) -> list[dict]:
    return [fields(l) for l in text.splitlines() if " llm_call " in l]


def ask(run: RunContext, agent: str, model=None):
    return (model or StubChatModel()).invoke([HumanMessage(content="hello")], config=llm_config(run, agent))


# ---- 1.1 / 1.2 core ------------------------------------------------------------------------
def test_ok_error_and_no_usage_records(tmp_path):
    with llm_logging("t", tmp_path) as llm:
        run = RunContext("S-1", AS_OF)
        ask(run, "a1")
        with pytest.raises(StubModelError):
            ask(run, "a2", StubChatModel(mode="raise"))
        ask(run, "a3", StubChatModel(report_usage=False))
        s = llm.summary()
    rows = calls((tmp_path / "run.log").read_text())
    assert [r["outcome"] for r in rows] == ["ok", "error", "ok"]
    ok, err, nousage = rows
    assert ok["run_id"] == run.run_id and ok["thread_id"] == run.thread_id and ok["agent"] == "a1" and ok["runner"] == "t"
    assert int(ok["in"]) > 0 and int(ok["total"]) == int(ok["in"]) + int(ok["out"]) and int(ok["ms"]) >= 0
    assert (nousage["in"], nousage["out"], nousage["total"]) == ("n/a",) * 3
    assert "error=StubModelError" in (tmp_path / "run.log").read_text() and "stub model failure" not in (tmp_path / "run.log").read_text()
    assert s["calls"] == 3 and s["failed"] == 1 and s["calls_without_usage"] == 2  # an error call carries no usage either
    assert s["total_tokens"] == int(ok["total"])


def test_concurrent_totals_equal_the_sum_of_records(tmp_path):
    with llm_logging("t", tmp_path) as llm:
        run = RunContext("S-1", AS_OF)
        ts = [threading.Thread(target=lambda: [ask(run, "w") for _ in range(10)]) for _ in range(8)]
        [t.start() for t in ts]
        [t.join() for t in ts]
        s = llm.summary()
    text = (tmp_path / "run.log").read_text()
    rows = calls(text)
    assert len(rows) == 80 == s["calls"]
    assert s["total_tokens"] == sum(int(r["total"]) for r in rows) and s["input_tokens"] == sum(int(r["in"]) for r in rows)
    assert all(re.match(r"\d{4}-.* (INFO|WARNING) llm_call ", l) for l in text.splitlines() if "llm_call " in l)


def test_summary_lines_and_both_sinks(tmp_path, capsys):
    with llm_logging("t", tmp_path):
        ask(RunContext("S-1", AS_OF), "a1")
    err = capsys.readouterr().err
    text = (tmp_path / "run.log").read_text()
    assert err == text and "llm_summary runner=t" in text and "llm_summary_agent runner=t agent=a1 calls=1" in text
    assert "llm_summary_slowest" in text


def test_level_warning_suppresses_ok_records_but_not_failures(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("RM_LOG_LEVEL", "WARNING")
    with llm_logging("t", tmp_path):
        run = RunContext("S-1", AS_OF)
        ask(run, "a1")
        with pytest.raises(StubModelError):
            ask(run, "a2", StubChatModel(mode="raise"))
    text = (tmp_path / "run.log").read_text()
    assert [r["outcome"] for r in calls(text)] == ["error"] and "llm_summary_warning" in text and "llm_summary runner" not in text
    assert capsys.readouterr().err == text


def test_handlers_are_removed_and_file_is_fresh(tmp_path):
    for _ in range(2):
        with llm_logging("t", tmp_path):
            ask(RunContext("S-1", AS_OF), "a1")
    assert not logging.getLogger("rm_dashboard.llm").handlers
    assert len(calls((tmp_path / "run.log").read_text())) == 1
    assert RunContext("S", AS_OF).llm_log is None


def test_zero_calls_logs_a_summary_to_console_only(tmp_path, capsys):
    target = tmp_path / "nested"
    with llm_logging("t", target) as llm:
        assert llm.counts()["calls"] == 0
    err = capsys.readouterr().err
    assert "llm_summary runner=t" in err and "calls=0" in err and "in=0 out=0 total=0" in err
    assert not target.exists()


# ---- 1.3 thread ids ------------------------------------------------------------------------
def test_child_shares_thread_and_logger_and_runs_differ():
    a, b = RunContext("S-1", AS_OF), RunContext("S-1", AS_OF)
    c = a.child("peer")
    assert c.thread_id == a.thread_id and c.run_id == a.run_id and a.thread_id != b.thread_id
    assert llm_config(c, "x")["configurable"]["thread_id"] == a.thread_id


def test_log_handler_defaults_to_the_active_runner(tmp_path):
    with llm_logging("t", tmp_path) as llm:
        assert RunContext("S-1", AS_OF).llm_log is llm
    assert isinstance(llm, LlmCallLogger)


# ---- 2.x / 3.x through the runners ---------------------------------------------------------------
@pytest.fixture(scope="module")
def reg(seeded_db):
    with open_registry(Settings(db_path=str(seeded_db), max_concurrency=4)) as r:
        yield r


class Counting:
    def __init__(self):
        self.made = []

    def __call__(self, role):
        m = StubChatModel(role=role)
        self.made.append(m)
        return m

    @property
    def calls(self) -> int:
        return sum(m.calls for m in self.made)


def test_batch_groups_calls_by_thread_and_summary_matches_log(reg, tmp_path, capsys):
    models = Counting()
    result = run_batch(reg, as_of=AS_OF, store=tmp_path, client_ids=["CL-0001", "CL-0017"], models=models)
    text = (result.out_dir / "run.log").read_text()
    rows = calls(text)
    assert len(rows) == models.calls > 0
    by_thread: dict[str, list[dict]] = {}
    for r in rows:
        by_thread.setdefault(r["thread_id"], []).append(r)
    assert len(by_thread) == 2 and {r["subject"] for r in rows} == {"CL-0001", "CL-0017"}
    for group in by_thread.values():
        assert len({r["subject"] for r in group}) == 1 and len({r["run_id"] for r in group}) == 1
        assert "relationship_analyst" in {r["agent"] for r in group}
    assert any({"relationship_analyst", "portfolio_analyst"} <= {r["agent"] for r in g} for g in by_thread.values())  # delegation grouped
    llm = result.summary["llm"]
    assert llm["calls"] == len(rows) and llm["total_tokens"] == sum(int(r["total"]) for r in rows)
    assert llm == get_summary(result.store, AS_OF, "analyse")["llm"]
    assert "elapsed_s" not in json.dumps(llm) and "llm_summary runner=analyse" in text
    assert capsys.readouterr().err.count(" llm_call ") == len(rows)


def test_no_prompt_response_or_name_in_logs(reg, tmp_path):
    names = [r["client_name"] for r in reg.ctx.repo.clients(as_of=AS_OF).frame.iter_rows(named=True)][:5]
    result = run_batch(reg, as_of=AS_OF, store=tmp_path, client_ids=["CL-0001"], models=Counting())
    text = (result.out_dir / "run.log").read_text()
    assert text and not any(n in text for n in names) and "Analyse client" not in text and '"findings"' not in text


def test_later_stages_log_their_agents(reg, tmp_path):
    run_batch(reg, as_of=AS_OF, store=tmp_path, client_ids=["CL-0001"], models=Counting())
    rec = run_reconcile(reg, as_of=AS_OF, store=tmp_path, client_ids=["CL-0001"], models=Counting())
    act = run_actions(reg, as_of=AS_OF, store=tmp_path, client_ids=["CL-0001"], models=Counting())
    for res, agent in ((rec, "note_reconciler"), (act, "client_actions")):
        rows = calls((res.out_dir / "run.log").read_text())
        assert len(rows) == 1 and rows[0]["agent"] == agent and rows[0]["subject"] == "CL-0001" and res.summary["llm"]["calls"] == 1


def test_outlook_logs_and_an_unchanged_rerun_leaves_the_log_alone(reg, tmp_path):
    first = run_outlook(reg, as_of=AS_OF, store=tmp_path, models=Counting())
    log = first.out_dir / "run.log"
    assert calls(log.read_text()) and first.summary["llm"]["calls"] == len(calls(log.read_text()))
    before = log.read_bytes()
    again = run_outlook(reg, as_of=AS_OF, store=tmp_path, models=Counting())
    assert again.untouched and log.read_bytes() == before


def test_an_all_failed_batch_still_gets_a_summary(reg, tmp_path):
    class Failing(Counting):
        def __call__(self, role):
            m = StubChatModel(role=role, mode="raise")
            self.made.append(m)
            return m

    result = run_batch(reg, as_of=AS_OF, store=tmp_path, client_ids=["CL-0001"], models=Failing())
    llm = result.summary["llm"]
    assert llm["calls"] >= 1 and llm["failed"] == llm["calls"]
    assert "llm_summary_warning" in (result.out_dir / "run.log").read_text()


def test_session_turns_share_the_session_thread(make_scope, tmp_path):
    from rm_dashboard.agents import AnalystSession

    with llm_logging("session", tmp_path):
        scope = make_scope()
        s = AnalystSession("relationship_analyst", "CL-0001", scope, lambda role: StubChatModel(role=role), thread_id="thread_ab12")
        s.start()
        s.ask("What about concentration?")
    rows = calls((tmp_path / "run.log").read_text())
    assert len(rows) >= 3 and {r["thread_id"] for r in rows} == {"thread_ab12"}
