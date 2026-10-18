import json
import shutil
from datetime import date
from pathlib import Path

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from rm_dashboard.actions import Action, ClientActions, SourceRef, derive_actions
from rm_dashboard.actions.assemble import finalise, merge, not_actioned
from rm_dashboard.actions.guard import guard_actions
from rm_dashboard.agents import StubChatModel
from rm_dashboard.domain import Computation, ToolResult
from rm_dashboard.reconciliation import NoteResult, Reconciliation
from rm_dashboard.reportsource import FlatFinding, StoreReportSource, flatten
from rm_dashboard.runners import open_registry, run_batch
from rm_dashboard.settings import Settings
from rm_dashboard.store import Kind

AS_OF = date(2026, 8, 26)


@pytest.fixture(scope="module")
def reg(seeded_db):
    with open_registry(Settings(db_path=str(seeded_db), max_concurrency=4)) as r:
        yield r


@pytest.fixture(scope="module")
def reports_dir(reg, tmp_path_factory):
    out = tmp_path_factory.mktemp("reports")
    run_batch(reg, as_of=AS_OF, store=out, client_ids=["CL-0001", "CL-0002", "CL-0003"], models=lambda role: StubChatModel(role=role))
    return out


@pytest.fixture
def source(reports_dir, tmp_path):
    dest = tmp_path / "reports"
    shutil.copytree(reports_dir, dest)
    return StoreReportSource(dest)


def stub():
    return StubChatModel(role="client_actions")


def write_reconciliation(source, cid, results):
    rec = Reconciliation(client_id=cid, as_of=AS_OF, status="complete", results=results)
    source.store.put(AS_OF, Kind.RECONCILIATION, cid, rec.model_dump_json())


def note(nid="N-001", verdict="contradicted", evidence=("ev_x",)):
    return NoteResult(note_id=nid, note_date=date(2026, 1, 8), note_quote="Client wants to cut energy.", verdict=verdict,
                      rationale="Energy is still 42.61% of the book.", evidence_ids=list(evidence))


def ev(tool, data):
    return ToolResult(data=data, as_of=AS_OF, computation=Computation(tool=tool, version="1"))


FINDINGS = {
    "CL-0001#f1": FlatFinding("CL-0001#f1", "CL-0001", "Bara Nusantara Energy is 42.61% of assets.", "high", ("ev_a",)),
    "CL-0001#f2": FlatFinding("CL-0001#f2", "CL-0001", "The KYC review is due in 96 days (2026-11-30).", "high", ("ev_k",)),
}


def raw(**kw):
    base = dict(category="concentration_risk", importance="low", title="Discuss concentration", what="Review the exposure.",
                why="It is 43% of assets.", refs=["CL-0001#f1"])
    return {**base, **kw}


# ---- 2.2 guard ------------------------------------------------------------------------------------
def test_guard_keeps_valid_action_and_copies_evidence_from_sources():
    out = guard_actions([raw(evidence_ids=["ev_forged"])], FINDINGS, {})
    a = out.actions[0]
    assert not out.gaps and a.sources == [SourceRef(kind="finding", ref="CL-0001#f1", report_path="CL-0001", evidence_ids=["ev_a"])]


@pytest.mark.parametrize("bad,needle", [
    (dict(category="marketing"), "category"),
    (dict(importance="urgent"), "importance"),
    (dict(refs=["CL-0002#f1"]), "unknown source"),
    (dict(refs=[]), "links no source"),
    (dict(why="It is 77.7% of assets."), "77.7"),
    (dict(what=""), "required"),
])
def test_guard_drops_each_violation(bad, needle):
    out = guard_actions([raw(**bad)], FINDINGS, {})
    assert out.actions == [] and len(out.gaps) == 1
    assert out.gaps[0].kind == "guard_removed" and needle in out.gaps[0].description


def test_guard_note_links_use_note_content_for_numbers():
    ok = guard_actions([raw(refs=["N-001"], why="The note says energy is still 42.61%.", category="client_contact")], {}, {"N-001": note()})
    assert ok.actions and ok.actions[0].sources[0].kind == "note"
    assert guard_actions("junk", FINDINGS, {}).actions == []


# ---- 2.3 merge, order, not_actioned ----------------------------------------------------------------
def act(title, category="concentration_risk", importance="high", refs=("CL-0001#f1",), kind="finding"):
    return Action(title=title, what="w", why="y", category=category, importance=importance,
                  sources=[SourceRef(kind=kind, ref=r, evidence_ids=[]) for r in refs])


def test_merge_overlapping_same_category_keeps_union_and_highest_importance():
    merged = merge([act("A", importance="low", refs=("CL-0001#f1",)), act("B", importance="high", refs=("N-001", "CL-0001#f1"))])
    assert len(merged) == 1 and merged[0].title == "B" and merged[0].importance == "high"
    assert {s.ref for s in merged[0].sources} == {"CL-0001#f1", "N-001"}


def test_merge_keeps_other_categories_and_disjoint_sources_apart():
    out = merge([act("A"), act("B", category="client_contact"), act("C", refs=("CL-0001#f9",))])
    assert len(out) == 3


def test_finalise_applies_floor_horizon_order_and_rank():
    evidence = {"ev_a": ev("analytics.concentration", {"single_names": [{"share_pct": 42.6}]}),
                "ev_k": ev("clients.get", {"client": {"kyc_review_due": "2026-11-30", "days_to_kyc_due": 96, "kyc_overdue": False}})}
    a = Action(title="Concentration", what="w", why="y", category="concentration_risk", importance="low",
               sources=[SourceRef(kind="finding", ref="CL-0001#f1", evidence_ids=["ev_a"])])
    k = Action(title="KYC", what="w", why="y", category="compliance_kyc", importance="high",
               sources=[SourceRef(kind="finding", ref="CL-0001#f2", evidence_ids=["ev_k"])])
    out = finalise([k, a], FINDINGS, {}, evidence, AS_OF)
    by = {x.title: x for x in out}
    assert by["Concentration"].importance == "high" and by["Concentration"].importance_raised_from == "low"
    assert by["KYC"].due_date == date(2026, 11, 30) and by["KYC"].horizon == "later" and by["KYC"].importance_raised_from is None
    assert [x.rank for x in out] == [1, 2]
    assert [x.title for x in out] == ["KYC", "Concentration"]  # same importance: a dated action precedes an undated one


def test_order_is_importance_then_horizon_then_date_then_title():
    items = [act(t, importance=i, refs=(f"CL-0001#f{n}",)) for n, (t, i) in enumerate(
        [("b", "low"), ("a", "critical"), ("d", "medium"), ("c", "medium")], start=1)]
    out = finalise(items, {}, {}, {}, AS_OF)
    assert [x.title for x in out] == ["a", "c", "d", "b"]
    assert out == finalise(list(reversed(items)), {}, {}, {}, AS_OF)


def test_contradicted_note_without_action_is_listed():
    notes = {"N-001": note(), "N-002": note("N-002", "consistent")}
    assert [n.note_id for n in not_actioned([], notes)] == ["N-001"]
    covered = [act("A", category="client_contact", refs=("N-001",), kind="note")]
    assert not_actioned(covered, notes) == []


def test_contradicted_note_raises_importance_to_medium():
    n = {"N-001": note()}
    a = act("Talk", category="client_contact", importance="low", refs=("N-001",), kind="note")
    assert finalise([a], {}, n, {}, AS_OF)[0].importance == "medium"


# ---- 1.2 reconciliation input, 3.3 agent -------------------------------------------------------------
def test_stub_run_without_reconciliation_has_actions_and_a_gap(reg, source):
    res = derive_actions(reg, "CL-0001", as_of=AS_OF, source=source, model=stub())
    assert res.actions and res.status == "partial" and any("notes were not reconciled" in g.description for g in res.gaps)
    assert [a.rank for a in res.actions] == list(range(1, len(res.actions) + 1))
    flat = {f.ref: f for f in flatten(source.report(AS_OF, "CL-0001"))}
    evidence = source.evidence(AS_OF, "CL-0001")
    for a in res.actions:
        assert a.sources and all(s.ref in flat for s in a.sources)
        assert all(i in evidence for s in a.sources for i in s.evidence_ids)


def test_present_reconciliation_is_used_and_contradiction_becomes_an_action(reg, source):
    write_reconciliation(source, "CL-0001", [note("N-001", "contradicted", evidence=())])
    res = derive_actions(reg, "CL-0001", as_of=AS_OF, source=source, model=stub())
    assert not any("notes were not reconciled" in g.description for g in res.gaps)
    contact = [a for a in res.actions if any(s.kind == "note" for s in a.sources)]
    assert contact and contact[0].category == "client_contact" and contact[0].importance == "medium"
    assert contact[0].importance_raised_from == "low" and res.not_actioned == []


def test_only_the_clients_own_content_is_used(reg, source):
    write_reconciliation(source, "CL-0002", [note("N-777", "contradicted", evidence=())])
    res = derive_actions(reg, "CL-0001", as_of=AS_OF, source=source, model=stub())
    own = {f.ref for f in flatten(source.report(AS_OF, "CL-0001"))}
    assert all(s.ref in own for a in res.actions for s in a.sources)


def test_contradicted_note_without_action_appears_in_not_actioned(reg, source):
    write_reconciliation(source, "CL-0001", [note("N-001", "contradicted", evidence=())])
    reply = json.dumps({"actions": []})
    res = derive_actions(reg, "CL-0001", as_of=AS_OF, source=source, model=FakeListChatModel(responses=[reply]))
    assert res.actions == [] and [n.note_id for n in res.not_actioned] == ["N-001"]


@pytest.mark.parametrize("mode", ["uncited_number", "bad_ref", "bad_category"])
def test_model_violations_drop_actions_with_gaps(reg, source, mode):
    res = derive_actions(reg, "CL-0001", as_of=AS_OF, source=source, model=StubChatModel(role="client_actions", mode=mode))
    assert res.status == "partial" and any(g.kind == "guard_removed" for g in res.gaps)


@pytest.mark.parametrize("mode", ["raise", "unparsable"])
def test_model_failure_gives_partial_without_actions(reg, source, mode):
    write_reconciliation(source, "CL-0001", [note("N-001", "contradicted", evidence=())])
    res = derive_actions(reg, "CL-0001", as_of=AS_OF, source=source, model=StubChatModel(role="client_actions", mode=mode))
    assert res.status == "partial" and res.actions == [] and any(g.kind == "agent_error" for g in res.gaps)
    assert [n.note_id for n in res.not_actioned] == ["N-001"]


def test_missing_report_is_insufficient_data(reg, tmp_path):
    res = derive_actions(reg, "CL-0001", as_of=AS_OF, source=StoreReportSource(tmp_path), model=stub())
    assert res.status == "insufficient_data" and res.actions == []


def test_rerun_is_identical(reg, source):
    a = derive_actions(reg, "CL-0003", as_of=AS_OF, source=source, model=stub())
    b = derive_actions(reg, "CL-0003", as_of=AS_OF, source=source, model=stub())
    assert a.model_dump_json() == b.model_dump_json()


def test_policy_denial_at_start_is_a_gap(reg, source):
    from rm_dashboard.policy import ScriptedEngine

    res = derive_actions(reg, "CL-0001", as_of=AS_OF, source=source, model=stub(), engine=ScriptedEngine(rules={"request_entitlement": "deny"}))
    assert res.status == "insufficient_data" and res.gaps[0].kind == "policy_denied"


# ---- 3.1 privacy and prompt ---------------------------------------------------------------------------
def test_names_are_pseudonymised_for_the_model_and_restored(reg, source):
    doc = json.loads(source.store.get(AS_OF, Kind.REPORT, "CL-0001"))
    for f in doc["findings"]:
        if "largest single-name" in f["claim"]:
            f["claim"] = "Hartono Wijaya Kusuma holds the largest single-name exposure in energy."
    source.store.put(AS_OF, Kind.REPORT, "CL-0001", json.dumps(doc))
    model = stub()
    res = derive_actions(reg, "CL-0001", as_of=AS_OF, source=source, model=model)
    sent = json.dumps([[m.content for m in ms] for ms in model.seen])
    assert "Hartono" not in sent and "PERSON_" in sent and res.actions
    pseudo = "PERSON_" + __import__("hashlib").sha256(b"rm-dashboard:CL-0001").hexdigest()[:6].upper()
    reply = json.dumps({"actions": [{"category": "client_contact", "importance": "low", "title": f"Call {pseudo}", "what": "Call.",
                                     "why": "Because.", "refs": ["CL-0001#f1"]}]})
    res = derive_actions(reg, "CL-0001", as_of=AS_OF, source=source, model=FakeListChatModel(responses=[reply]))
    assert res.actions[0].title == "Call Hartono Wijaya Kusuma"


def test_prompt_contains_the_rubric_and_all_categories():
    from rm_dashboard.actions.agent import SYSTEM_PROMPT
    from rm_dashboard.actions.contracts import CATEGORIES

    assert all(c in SYSTEM_PROMPT for c in CATEGORIES) and "critical" in SYSTEM_PROMPT and "overdue" in SYSTEM_PROMPT


# ---- 4.1 CLI ----------------------------------------------------------------------------------------------
def test_cli_saves_artifacts_and_rerun_is_byte_identical(seeded_db, source, capsys, monkeypatch):
    from rm_dashboard.runners.actions import main

    monkeypatch.delenv("RM_DASHBOARD_DB", raising=False)
    args = ["--as-of", "2026-08-26", "--db", str(seeded_db), "--reports-dir", str(Path(source.store.path).parent), "--clients", "CL-0001,CL-0017"]
    assert main(args) == 0
    store = source.store

    def saved():
        return {k: store.get(AS_OF, Kind.ACTIONS, k) for k in store.keys(AS_OF, Kind.ACTIONS)}

    first = saved()
    assert set(first) == {"CL-0001", "CL-0017"} and store.get(AS_OF, Kind.RUN_SUMMARY, "actions")
    ClientActions.model_validate_json(first["CL-0001"])
    assert json.loads(first["CL-0017"])["status"] == "insufficient_data"  # no report in this fixture: delivered, not raised
    assert main(args) == 0
    assert first == saved()
    assert "2 client action files written" in capsys.readouterr().out


def test_cli_requires_database_and_date(tmp_path, capsys, monkeypatch):
    from rm_dashboard.runners.actions import main

    monkeypatch.delenv("RM_DASHBOARD_DB", raising=False)
    assert main(["--as-of", "2026-08-26"]) == 2
    assert main(["--as-of", "2026-08-26", "--db", str(tmp_path / "missing.db")]) == 2
    with pytest.raises(SystemExit):
        main(["--db", "x.db"])
    assert "no database given" in capsys.readouterr().err
