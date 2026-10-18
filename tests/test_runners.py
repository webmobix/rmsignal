import json
from datetime import date

import pytest

from rm_dashboard.agents import StubChatModel
from rm_dashboard.domain import Report
from rm_dashboard.policy import ScriptedEngine
from rm_dashboard.runners import open_registry, run_batch
from rm_dashboard.runners.analyse import main
from rm_dashboard.settings import Settings
from rm_dashboard.store import Kind, as_store
from rm_dashboard.store.audit import read_audit
from rm_dashboard.store.evidence import get_evidence
from rm_dashboard.store.summary import get_summary
from storehelp import saved

AS_OF = date(2026, 8, 26)

EVENT_DATE_KEYS = {"note_date", "event_date", "trade_date"}


@pytest.fixture(scope="module")
def reg(seeded_db):
    with open_registry(Settings(db_path=str(seeded_db), max_concurrency=4)) as r:
        yield r


def stub(role):
    return StubChatModel(role=role)


# ---- 9.1 CLI --------------------------------------------------------------------------------
def test_cli_saves_one_report_per_client_and_a_summary(seeded_db, tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("RM_DASHBOARD_DB", raising=False)
    code = main(["--as-of", "2026-08-26", "--db", str(seeded_db), "--out", str(tmp_path), "--clients", "CL-0001,CL-0017"])
    assert code == 0
    store = as_store(tmp_path)
    assert store.keys(AS_OF, Kind.REPORT) == ["CL-0001", "CL-0017"]
    for body in saved(tmp_path, "2026-08-26", Kind.REPORT).values():
        Report.model_validate_json(body)
    summary = get_summary(store, AS_OF, "analyse")
    assert summary["clients"] == 2 and sum(summary["status_counts"].values()) == 2 and summary["model"] == "stub"
    out = capsys.readouterr().out
    assert "2 reports written" in out and "CL-0001:" in out
    assert read_audit(store, AS_OF, "analyse")
    assert not list(tmp_path.glob("*/*.json"))  # nothing is written beside the store


def test_cli_requires_as_of_and_database(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("RM_DASHBOARD_DB", raising=False)
    with pytest.raises(SystemExit) as e:
        main(["--db", "x.db"])
    assert e.value.code == 2
    assert main(["--as-of", "2026-08-26"]) == 2
    assert main(["--as-of", "2026-08-26", "--db", str(tmp_path / "missing.db")]) == 2
    err = capsys.readouterr().err
    assert "no database given" in err and "database not found" in err and "rm-dashboard-seed" in err
    with pytest.raises(SystemExit):
        main(["--as-of", "not-a-date", "--db", "x"])


def test_cli_reads_database_from_environment(seeded_db, tmp_path, monkeypatch):
    monkeypatch.setenv("RM_DASHBOARD_DB", str(seeded_db))
    assert main(["--as-of", "2026-03-31", "--out", str(tmp_path), "--clients", "CL-0002"]) == 0
    assert as_store(tmp_path).keys(date(2026, 3, 31), Kind.REPORT) == ["CL-0002"]


# ---- 9.2 end to end ---------------------------------------------------------------------------
def walk_dates(x, found):
    if isinstance(x, dict):
        for k, v in x.items():
            if k in EVENT_DATE_KEYS and isinstance(v, str):
                found.append(date.fromisoformat(v))
            walk_dates(v, found)
    elif isinstance(x, list):
        for v in x:
            walk_dates(v, found)


@pytest.fixture(scope="module")
def full_runs(reg, tmp_path_factory):
    out = tmp_path_factory.mktemp("reports")
    return {d: run_batch(reg, as_of=d, store=out, models=stub) for d in (date(2026, 8, 26), date(2026, 3, 31))}


@pytest.mark.parametrize("as_of", [date(2026, 8, 26), date(2026, 3, 31)])
def test_twenty_valid_reports_per_date(full_runs, as_of):
    res = full_runs[as_of]
    assert len(res.reports) == 20 and len(res.store.keys(as_of, Kind.REPORT)) == 20
    for body in saved(res.store, as_of.isoformat(), Kind.REPORT).values():
        r = Report.model_validate_json(body)
        assert r.as_of == as_of and r.findings and r.evidence_ids
    assert sum(res.summary["status_counts"].values()) == 20
    assert res.summary["status_counts"]["insufficient_data"] == 0


def test_no_lookahead_for_earlier_date(full_runs):
    res = full_runs[date(2026, 3, 31)]
    cutoff = res.as_of
    n = 0
    for cid in res.store.keys(cutoff, Kind.EVIDENCE_INDEX, "report/"):
        for ev in (r.model_dump(mode="json") for r in get_evidence(res.store, cutoff, "report", cid.split("/", 1)[1])):
            n += 1
            assert ev["as_of"] == cutoff.isoformat()
            if ev["effective_snapshot_date"]:
                assert date.fromisoformat(ev["effective_snapshot_date"]) <= cutoff
            assert all(not s["snapshot_date"] or date.fromisoformat(s["snapshot_date"]) <= cutoff for s in ev["sources"])
            found: list[date] = []
            walk_dates(ev["data"], found)
            assert all(d <= cutoff for d in found), (cid, ev["computation"]["tool"])
    assert n > 200


def test_later_date_differs_and_dates_are_independent(full_runs):
    late, early = full_runs[date(2026, 8, 26)], full_runs[date(2026, 3, 31)]
    assert set(late.reports["CL-0001"].evidence_ids) != set(early.reports["CL-0001"].evidence_ids)
    kyc = lambda res: [f.claim for f in res.reports["CL-0014"].findings if f.claim.startswith("The KYC review")][0]  # noqa: E731
    assert kyc(late) != kyc(early)


def test_batch_is_reproducible(reg, tmp_path):
    a = run_batch(reg, as_of=date(2026, 8, 26), store=tmp_path / "a", client_ids=["CL-0003", "CL-0017"], models=stub)
    b = run_batch(reg, as_of=date(2026, 8, 26), store=tmp_path / "b", client_ids=["CL-0003", "CL-0017"], models=stub)
    for cid in a.reports:
        assert a.reports[cid].evidence_ids == b.reports[cid].evidence_ids
        assert a.reports[cid].findings == b.reports[cid].findings


# ---- 9.3 failures -----------------------------------------------------------------------------
def test_model_failure_still_delivers_a_report_per_client(reg, tmp_path):
    res = run_batch(reg, as_of=date(2026, 8, 26), store=tmp_path, models=lambda role: StubChatModel(role=role, mode="raise"))
    assert len(res.reports) == 20
    assert {r.status for r in res.reports.values()} == {"partial"}
    assert all(any(g.kind == "agent_error" for g in r.gaps) for r in res.reports.values())
    assert res.summary["status_counts"] == {"complete": 0, "partial": 20, "insufficient_data": 0}


def test_denied_tool_still_delivers_partial_reports(reg, tmp_path):
    res = run_batch(reg, as_of=date(2026, 8, 26), store=tmp_path, models=stub,
                    engine=ScriptedEngine(by_tool={"analytics.liquidity": "deny"}))
    assert len(res.reports) == 20
    for r in res.reports.values():
        assert r.status == "partial" and r.findings
        assert any(g.kind == "policy_denied" and g.subject == "analytics.liquidity" for g in r.gaps)


def test_as_of_before_data_gives_insufficient_data_for_all(reg, tmp_path):
    res = run_batch(reg, as_of=date(2025, 1, 1), store=tmp_path, models=stub, client_ids=["CL-0001", "CL-0002"])
    assert {r.status for r in res.reports.values()} == {"insufficient_data"}


def test_unknown_client_still_gets_a_report(reg, tmp_path):
    res = run_batch(reg, as_of=date(2026, 8, 26), store=tmp_path, models=stub, client_ids=["CL-9999"])
    assert res.reports["CL-9999"].status in ("partial", "insufficient_data")
