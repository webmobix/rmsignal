import json
import shutil
from datetime import date
from pathlib import Path

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from rm_dashboard.actions import Action, SourceRef, derive_actions
from rm_dashboard.actions.agent import SYSTEM_PROMPT
from rm_dashboard.actions.assemble import finalise, not_actioned
from rm_dashboard.actions.guard import guard_actions
from rm_dashboard.actions.rubric import MANDATE_FLOORS, MANDATE_STATUSES, MANDATE_TABLE, RUBRIC_TEXT, floor_for, mandate_floor
from rm_dashboard.agents import StubChatModel
from rm_dashboard.domain import Computation, ToolResult
from rm_dashboard.mandate_reconciliation import BreachResult, MandateReconciliation, NoteQuote
from rm_dashboard.reportsource import StoreReportSource
from rm_dashboard.runners import open_registry, run_batch
from rm_dashboard.settings import Settings
from rm_dashboard.store import Kind

AS_OF = date(2026, 8, 26)
REF = "PF-0009/band/Commodities"
DESC = "Commodities weight is 14.20% against a maximum of 10.00% (gap 4.20 percentage points)"


def result(status="client_directed", kind="band", key="Commodities", pid="PF-0009", waiver=True, notes=("N-010",)):
    quotes = [NoteQuote(note_id=n, note_date=date(2026, 1, 22), quote="Client instructed more gold. Suitability waiver on file.") for n in notes]
    return BreachResult(portfolio_id=pid, kind=kind, key=key, evidence_id="ev_m", description=DESC, status=status,
                        rationale="The client instructed a purchase above the 10% ceiling." if status != "no_note" else "",
                        notes=quotes if status != "no_note" else [], waiver_claimed=waiver and status != "no_note")


def raw(**kw):
    base = dict(category="mandate_drift", importance="low", title="Review the instruction", what="Verify the waiver.",
                why="The breach is 14.20% against 10.00%.", refs=[REF])
    return {**base, **kw}


def ev(tool, data):
    return ToolResult(data=data, as_of=AS_OF, computation=Computation(tool=tool, version="1"))


# ---- 3.1 mandate source -------------------------------------------------------------------------------
def test_guard_links_a_mandate_result_with_its_status_evidence_and_notes():
    out = guard_actions([raw(evidence_ids=["ev_forged"])], {}, {}, {REF: result()})
    s = out.actions[0].sources[0]
    assert not out.gaps
    assert (s.kind, s.ref, s.evidence_ids, s.mandate_status, s.breach_kind, s.note_ids) == \
        ("mandate", REF, ["ev_m"], "client_directed", "band", ["N-010"])


def test_mandate_source_with_unknown_ref_removes_the_action_and_records_a_gap():
    out = guard_actions([raw(refs=["PF-0009/band/Gold"])], {}, {}, {REF: result()})
    assert out.actions == [] and len(out.gaps) == 1 and "unknown source" in out.gaps[0].description
    assert guard_actions([raw(why="It is 99.9% of assets.")], {}, {}, {REF: result()}).actions == []


# ---- 3.2 status-aware rubric -----------------------------------------------------------------------------
@pytest.mark.parametrize("kind", ["band", "position", "exclusion"])
@pytest.mark.parametrize("status", MANDATE_STATUSES)
def test_every_cell_of_the_floor_table(kind, status):
    expected = MANDATE_FLOORS["exclusion" if kind == "exclusion" else "band or position"][status]
    assert floor_for("mandate_drift", [], mandate=[(kind, status)]) == expected == mandate_floor(kind, status)
    a = Action(title="t", what="w", why="y", category="mandate_drift", importance="low",
               sources=[SourceRef(kind="mandate", ref=REF, evidence_ids=["ev_m"], mandate_status=status, breach_kind=kind)])
    out = finalise([a], {}, {}, {}, AS_OF)[0]
    assert out.importance == expected and out.importance_raised_from == "low"


def test_table_values_follow_the_spec():
    assert [mandate_floor("band", s) for s in MANDATE_STATUSES] == ["high", "medium", "high", "critical"]
    assert [mandate_floor("exclusion", s) for s in MANDATE_STATUSES] == ["high", "high", "high", "critical"]


def test_action_without_a_mandate_source_keeps_the_flat_high():
    drift = ev("analytics.mandate_drift", {"breaches": [{"asset_class": "Commodities"}]})
    excl = ev("analytics.exclusion_breaches", {"breaches": [{"instrument_id": "X"}]})
    assert floor_for("mandate_drift", [drift]) == floor_for("mandate_drift", [excl]) == "high"
    a = Action(title="t", what="w", why="y", category="mandate_drift", importance="low",
               sources=[SourceRef(kind="finding", ref="CL-0001#f1", evidence_ids=[drift.evidence_id])])
    assert finalise([a], {}, {}, {drift.evidence_id: drift}, AS_OF)[0].importance == "high"


def test_acknowledged_band_is_medium_even_when_evidence_alone_would_say_high():
    drift = ev("analytics.mandate_drift", {"breaches": [{"asset_class": "Commodities"}]})
    a = Action(title="t", what="w", why="y", category="mandate_drift", importance="medium",
               sources=[SourceRef(kind="mandate", ref=REF, evidence_ids=[drift.evidence_id], mandate_status="acknowledged", breach_kind="band")])
    assert finalise([a], {}, {}, {drift.evidence_id: drift}, AS_OF)[0].importance == "medium"


def test_rubric_text_and_docs_render_the_same_table():
    assert MANDATE_TABLE in RUBRIC_TEXT and MANDATE_TABLE in SYSTEM_PROMPT
    docs = (Path(__file__).parent.parent / "docs" / "agents.md").read_text()
    assert MANDATE_TABLE in docs


# ---- 3.3 wording per status, not_actioned ----------------------------------------------------------------
@pytest.fixture(scope="module")
def reg(seeded_db):
    with open_registry(Settings(db_path=str(seeded_db), max_concurrency=4)) as r:
        yield r


@pytest.fixture(scope="module")
def reports_dir(reg, tmp_path_factory):
    out = tmp_path_factory.mktemp("reports")
    run_batch(reg, as_of=AS_OF, store=out, client_ids=["CL-0001"], models=lambda role: StubChatModel(role=role))
    return out


@pytest.fixture
def source(reports_dir, tmp_path):
    dest = tmp_path / "reports"
    shutil.copytree(reports_dir, dest)
    return StoreReportSource(dest)


def write_mandate(source, results, cid="CL-0001"):
    rec = MandateReconciliation(client_id=cid, as_of=AS_OF, status="complete", results=results)
    source.store.put(AS_OF, Kind.MANDATE_RECONCILIATION, cid, rec.model_dump_json())


def mandate_actions(res):
    return [a for a in res.actions if any(s.kind == "mandate" for s in a.sources)]


def test_client_directed_asks_to_verify_the_waiver_and_links_the_notes(reg, source):
    write_mandate(source, [result("client_directed")])
    res = derive_actions(reg, "CL-0001", as_of=AS_OF, source=source, model=StubChatModel(role="client_actions"))
    (a,) = mandate_actions(res)
    assert "waiver" in a.what and "Review" in a.title and a.importance == "high" and a.category == "mandate_drift"
    s = next(x for x in a.sources if x.kind == "mandate")
    assert s.note_ids == ["N-010"] and s.mandate_status == "client_directed"


def test_contradicted_corrects_the_record_at_critical(reg, source):
    write_mandate(source, [result("contradicted", waiver=False)])
    (a,) = mandate_actions(derive_actions(reg, "CL-0001", as_of=AS_OF, source=source, model=StubChatModel(role="client_actions")))
    assert "Correct the record" in a.title and a.importance == "critical" and a.importance_raised_from == "low"


def test_acknowledged_is_a_follow_up_at_medium(reg, source):
    write_mandate(source, [result("acknowledged", waiver=False)])
    (a,) = mandate_actions(derive_actions(reg, "CL-0001", as_of=AS_OF, source=source, model=StubChatModel(role="client_actions")))
    assert "Follow up" in a.title and a.importance == "medium"


def test_contradicted_mandate_result_without_an_action_is_not_actioned():
    r = result("contradicted", waiver=False)
    out = not_actioned([], {}, {REF: r})
    assert [(n.kind, n.note_id) for n in out] == [("mandate", REF)]
    covered = [Action(title="t", what="w", why="y", category="mandate_drift", importance="critical",
                      sources=[SourceRef(kind="mandate", ref=REF, evidence_ids=["ev_m"], mandate_status="contradicted", breach_kind="band")])]
    assert not_actioned(covered, {}, {REF: r}) == []
    assert not_actioned([], {}, {REF: result("client_directed")}) == []


def test_the_prompt_states_the_wording_per_status():
    for needle in ("no_note", "acknowledged", "client_directed", "contradicted", "verify that any claimed waiver", "correct the record"):
        assert needle in SYSTEM_PROMPT


# ---- 3.4 missing mandate reconciliation --------------------------------------------------------------------
def test_missing_mandate_reconciliation_is_a_gap_and_nothing_else_changes(reg, source):
    base = derive_actions(reg, "CL-0001", as_of=AS_OF, source=source, model=StubChatModel(role="client_actions"))
    assert any("mandate breaches were not reconciled" in g.description for g in base.gaps)
    assert mandate_actions(base) == [] and base.status == "partial"
    write_mandate(source, [])
    with_empty = derive_actions(reg, "CL-0001", as_of=AS_OF, source=source, model=StubChatModel(role="client_actions"))
    assert [a.model_dump() for a in with_empty.actions] == [a.model_dump() for a in base.actions]
    assert not any("mandate breaches were not reconciled" in g.description for g in with_empty.gaps)


def test_no_note_results_leave_actions_as_they_were(reg, source):
    base = derive_actions(reg, "CL-0001", as_of=AS_OF, source=source, model=StubChatModel(role="client_actions"))
    write_mandate(source, [result("no_note")])
    res = derive_actions(reg, "CL-0001", as_of=AS_OF, source=source, model=StubChatModel(role="client_actions"))
    assert [a.model_dump() for a in res.actions] == [a.model_dump() for a in base.actions]


# ---- links are re-checked by the overview ------------------------------------------------------------------
def test_overview_rechecks_mandate_links(reg, source):
    from rm_dashboard.actions.contracts import ClientActions
    from rm_dashboard.overview.build import _links_broken
    from rm_dashboard.overview.source import StoreOverviewSource

    write_mandate(source, [result("client_directed")])
    src = StoreOverviewSource(source.store)

    def check(**kw):
        s = SourceRef(kind="mandate", ref=REF, evidence_ids=["ev_m"], mandate_status="client_directed", breach_kind="band")
        a = Action(title="t", what="w", why="y", category="mandate_drift", importance="high", sources=[s.model_copy(update=kw)])
        return _links_broken(ClientActions(client_id="CL-0001", as_of=AS_OF, status="complete", actions=[a]), src, AS_OF)

    assert check() == []
    assert "not found" in check(ref="PF-0009/band/Gold")[0]
    assert "differs" in check(mandate_status="acknowledged")[0]
