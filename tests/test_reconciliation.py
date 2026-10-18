import json
from datetime import date

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from rm_dashboard.agents import StubChatModel
from rm_dashboard.domain import Report
from rm_dashboard.reconciliation import Reconciliation, reconcile
from rm_dashboard.reconciliation.guard import Note, guard_results
from rm_dashboard.reportsource import FlatFinding, StoreReportSource, flatten
from rm_dashboard.runners import open_registry, run_batch
from rm_dashboard.settings import Settings
from rm_dashboard.store import Kind

AS_OF = date(2026, 8, 26)
EARLY = date(2026, 3, 31)


@pytest.fixture(scope="module")
def reg(seeded_db):
    with open_registry(Settings(db_path=str(seeded_db), max_concurrency=4)) as r:
        yield r


@pytest.fixture(scope="module")
def reports_dir(reg, tmp_path_factory):
    out = tmp_path_factory.mktemp("reports")
    for d in (AS_OF, EARLY):
        run_batch(reg, as_of=d, store=out, client_ids=["CL-0001", "CL-0012"], models=lambda role: StubChatModel(role=role))
    return out


@pytest.fixture
def source(reports_dir):
    return StoreReportSource(reports_dir)


def scripted(*results):
    return FakeListChatModel(responses=[json.dumps({"results": list(results)})])


# ---- 1.2 loader on real batch output ----------------------------------------------------------
def test_loader_reads_report_evidence_and_flattens(source):
    report = source.report(AS_OF, "CL-0001")
    evidence = source.evidence(AS_OF, "CL-0001")
    assert isinstance(report, Report) and evidence
    flat = flatten(report)
    refs = [f.ref for f in flat]
    assert refs == [f.ref for f in flatten(source.report(AS_OF, "CL-0001"))] and len(set(refs)) == len(refs)
    assert any(r.startswith("CL-0001/PF-0001#f") for r in refs)
    assert all(i in evidence for f in flat for i in f.evidence_ids)
    assert source.report(AS_OF, "CL-0099") is None


# ---- 1.3 / 3.3 notes at as_of, end to end ---------------------------------------------------------
def test_stub_run_gives_one_verdict_per_note(reg, source):
    rec = reconcile(reg, "CL-0001", as_of=AS_OF, source=source, model=StubChatModel(role="note_reconciler"))
    assert [r.note_id for r in rec.results] == ["N-001", "N-002"]
    assert all(r.kind == "rm_note" and r.rationale and r.note_quote for r in rec.results)
    assert {r.verdict for r in rec.results} <= {"consistent", "contradicted", "unverifiable"}
    ev = source.evidence(AS_OF, "CL-0001")
    assert all(i in ev for r in rec.results for i in r.evidence_ids)
    assert rec.status in ("complete", "partial")


def test_notes_after_as_of_are_excluded(reg, source):
    rec = reconcile(reg, "CL-0001", as_of=EARLY, source=source, model=StubChatModel(role="note_reconciler"))
    assert [r.note_id for r in rec.results] == ["N-001"]


def test_client_without_notes_yields_empty_complete_result(reg, source):
    rec = reconcile(reg, "CL-0012", as_of=EARLY, source=source, model=StubChatModel(role="note_reconciler"))
    assert rec.results == [] and rec.status == "complete" and rec.gaps == []


def test_missing_report_is_insufficient_data(reg, tmp_path):
    rec = reconcile(reg, "CL-0001", as_of=AS_OF, source=StoreReportSource(tmp_path), model=StubChatModel(role="note_reconciler"))
    assert rec.status == "insufficient_data" and rec.results == [] and rec.gaps[0].kind == "no_data"


def test_rerun_is_identical(reg, source):
    a = reconcile(reg, "CL-0001", as_of=AS_OF, source=source, model=StubChatModel(role="note_reconciler"))
    b = reconcile(reg, "CL-0001", as_of=AS_OF, source=source, model=StubChatModel(role="note_reconciler"))
    assert a.model_dump_json() == b.model_dump_json()


# ---- 3.3 failures -------------------------------------------------------------------------------
@pytest.mark.parametrize("mode", ["raise", "unparsable"])
def test_model_failure_marks_every_note_unverifiable(reg, source, mode):
    rec = reconcile(reg, "CL-0001", as_of=AS_OF, source=source, model=StubChatModel(role="note_reconciler", mode=mode))
    assert rec.status == "partial" and any(g.kind == "agent_error" for g in rec.gaps)
    assert [r.verdict for r in rec.results] == ["unverifiable", "unverifiable"]


def test_invented_figure_removes_the_assessment(reg, source):
    rec = reconcile(reg, "CL-0001", as_of=AS_OF, source=source, model=StubChatModel(role="note_reconciler", mode="uncited_number"))
    first = rec.results[0]
    assert first.verdict == "unverifiable" and "7351" not in first.rationale
    assert rec.status == "partial" and any("7351.24" in g.description for g in rec.gaps)


def test_unknown_ref_downgrades_supported_verdict(reg, source):
    rec = reconcile(reg, "CL-0001", as_of=AS_OF, source=source, model=StubChatModel(role="note_reconciler", mode="bad_ref"))
    assert rec.results[0].verdict == "unverifiable" and rec.results[0].finding_refs == []
    assert any("CL-9999#f99" in g.description for g in rec.gaps)


# ---- 2.1 guard rules ------------------------------------------------------------------------------
class Ev:
    def __init__(self, data):
        self.data = data


def fixture_guard():
    notes = [Note("N-001", date(2026, 1, 8), "Client wants to cut energy; mentioned about 9m."),
             Note("N-002", date(2026, 4, 14), "Second note."), Note("N-003", date(2026, 9, 1), "Later note.")]
    findings = {"CL-0001#f1": FlatFinding("CL-0001#f1", "CL-0001", "Energy is 42.61% of the book.", "high", ("ev_a",))}
    return notes, findings, {"ev_a": Ev({"share_pct": 42.613})}


def test_guard_supported_verdict_keeps_resolved_evidence():
    notes, findings, ev = fixture_guard()
    out = guard_results([{"note_id": "N-001", "verdict": "contradicted", "rationale": "Energy remains 43% of the book.",
                          "finding_refs": ["CL-0001#f1"]}], notes, findings, ev, date(2026, 8, 26))
    r = out.results[0]
    assert (r.verdict, r.finding_refs, r.evidence_ids) == ("contradicted", ["CL-0001#f1"], ["ev_a"])


def test_guard_note_numbers_may_be_quoted_but_not_unknown_figures():
    notes, findings, ev = fixture_guard()
    ok = guard_results([{"note_id": "N-001", "verdict": "consistent", "rationale": "The note mentions 9m.", "finding_refs": ["CL-0001#f1"]}],
                       notes, findings, ev, date(2026, 8, 26))
    assert ok.results[0].verdict == "consistent"
    bad = guard_results([{"note_id": "N-001", "verdict": "consistent", "rationale": "It is 55.5% now.", "finding_refs": ["CL-0001#f1"]}],
                        notes, findings, ev, date(2026, 8, 26))
    assert bad.results[0].verdict == "unverifiable" and any(g.kind == "guard_removed" for g in bad.gaps)


def test_guard_supported_verdict_without_evidence_is_downgraded():
    notes, findings, ev = fixture_guard()
    out = guard_results([{"note_id": "N-001", "verdict": "consistent", "rationale": "Fine.", "finding_refs": []}],
                        notes, findings, ev, date(2026, 8, 26))
    assert out.results[0].verdict == "unverifiable" and out.gaps


def test_guard_drops_unknown_and_later_notes_and_fills_skipped_ones():
    notes, findings, ev = fixture_guard()
    out = guard_results([{"note_id": "N-003", "verdict": "unverifiable", "rationale": "x"},
                         {"note_id": "N-999", "verdict": "unverifiable", "rationale": "x"}],
                        notes, findings, ev, date(2026, 8, 26))
    assert [r.note_id for r in out.results] == ["N-001", "N-002"]
    assert all(r.verdict == "unverifiable" for r in out.results)
    assert sum(g.kind == "guard_removed" for g in out.gaps) == 2 and sum(g.kind == "other" for g in out.gaps) == 2


def test_guard_invalid_verdict_and_garbage_input():
    notes, findings, ev = fixture_guard()
    out = guard_results([{"note_id": "N-001", "verdict": "maybe", "rationale": "x", "finding_refs": []}, "junk"],
                        notes, findings, ev, date(2026, 8, 26))
    assert out.results[0].verdict == "unverifiable" and len(out.results) == 2
    assert guard_results("not a list", notes, findings, ev, date(2026, 8, 26)).results[1].note_id == "N-002"


# ---- 2.2 scope: notes only ------------------------------------------------------------------------------
def test_scope_is_notes_only(reg, source):
    """CL-0001's report has mandate findings; the output has results for notes and nothing else."""
    rec = reconcile(reg, "CL-0001", as_of=AS_OF, source=source, model=StubChatModel(role="note_reconciler"))
    assert {r.kind for r in rec.results} == {"rm_note"}
    assert {r.note_id for r in rec.results} == {"N-001", "N-002"}


# ---- 3.1 privacy ----------------------------------------------------------------------------------------
def named_source(reports_dir, tmp_path):
    """A copy of the batch output whose first finding names the client, as a real model's report would."""
    import shutil

    dest = tmp_path / "reports"
    shutil.copytree(reports_dir, dest)
    source = StoreReportSource(dest)
    doc = json.loads(source.store.get(AS_OF, Kind.REPORT, "CL-0001"))
    doc["findings"][0]["claim"] = "Hartono Wijaya Kusuma holds the account. " + doc["findings"][0]["claim"]
    source.store.put(AS_OF, Kind.REPORT, "CL-0001", json.dumps(doc))
    return source


def test_names_are_pseudonymised_for_the_model(reg, reports_dir, tmp_path):
    model = StubChatModel(role="note_reconciler")
    reconcile(reg, "CL-0001", as_of=AS_OF, source=named_source(reports_dir, tmp_path), model=model)
    sent = json.dumps([[m.content for m in msgs] for msgs in model.seen])
    assert "Hartono" not in sent and "Kusuma" not in sent and "PERSON_" in sent


def test_restore_puts_names_back_into_rationale(reg, source):
    from rm_dashboard.policy import Pseudonymiser

    ps = Pseudonymiser().pseudonym("CL-0001")
    reply = json.dumps({"results": [{"note_id": "N-001", "verdict": "unverifiable", "rationale": f"{ps} said so.", "finding_refs": []},
                                    {"note_id": "N-002", "verdict": "unverifiable", "rationale": "ok", "finding_refs": []}]})
    rec = reconcile(reg, "CL-0001", as_of=AS_OF, source=source, model=FakeListChatModel(responses=[reply]))
    assert "Hartono Wijaya Kusuma said so." in rec.results[0].rationale


# ---- policy ---------------------------------------------------------------------------------------------
def test_policy_denial_at_start_is_a_gap_not_an_error(reg, source):
    from rm_dashboard.policy import ScriptedEngine

    rec = reconcile(reg, "CL-0001", as_of=AS_OF, source=source, model=StubChatModel(role="note_reconciler"),
                    engine=ScriptedEngine(rules={"request_entitlement": "deny"}))
    assert rec.status == "insufficient_data" and rec.gaps[0].kind == "policy_denied"


def test_model_input_goes_through_the_pii_checkpoint(reg, source):
    from rm_dashboard.policy import ScriptedEngine

    engine = ScriptedEngine()
    reconcile(reg, "CL-0001", as_of=AS_OF, source=source, model=StubChatModel(role="note_reconciler"), engine=engine)
    assert "pii_minimisation" in [c for c, _ in engine.seen] and "tool_authorisation" in [c for c, _ in engine.seen]


# ---- 4.1 CLI ---------------------------------------------------------------------------------------------
def test_cli_saves_artifacts_and_rerun_is_identical(seeded_db, reports_dir, capsys, monkeypatch):
    from rm_dashboard.runners.reconcile import main

    monkeypatch.delenv("RM_DASHBOARD_DB", raising=False)
    args = ["--as-of", "2026-08-26", "--db", str(seeded_db), "--reports-dir", str(reports_dir), "--clients", "CL-0001,CL-0017"]
    assert main(args) == 0
    store = StoreReportSource(reports_dir).store

    def saved():
        return {k: store.get(AS_OF, Kind.RECONCILIATION, k) for k in store.keys(AS_OF, Kind.RECONCILIATION)}

    first = saved()
    assert set(first) == {"CL-0001", "CL-0017"} and store.get(AS_OF, Kind.RUN_SUMMARY, "reconcile")
    Reconciliation.model_validate_json(first["CL-0001"])
    # CL-0017 has no persisted report in this fixture: delivered as insufficient_data, not an error
    assert json.loads(first["CL-0017"])["status"] == "insufficient_data"
    assert main(args) == 0
    assert first == saved()
    text = capsys.readouterr().out
    assert "2 reconciliations written" in text and "CL-0001:" in text


def test_cli_requires_database_and_date(tmp_path, capsys, monkeypatch):
    from rm_dashboard.runners.reconcile import main

    monkeypatch.delenv("RM_DASHBOARD_DB", raising=False)
    assert main(["--as-of", "2026-08-26"]) == 2
    assert main(["--as-of", "2026-08-26", "--db", str(tmp_path / "missing.db")]) == 2
    with pytest.raises(SystemExit):
        main(["--db", "x.db"])
    assert "no database given" in capsys.readouterr().err
