import json
from datetime import date
from pathlib import Path

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from pydantic import ValidationError

from rm_dashboard.agents import StubChatModel
from rm_dashboard.domain import Computation, ToolResult
from rm_dashboard.mandate_reconciliation import BreachResult, MandateReconciliation, NoteQuote, mandate_reconcile
from rm_dashboard.mandate_reconciliation.contracts import PRECEDENCE, STATUSES
from rm_dashboard.mandate_reconciliation.guard import WAIVER_CLAIM, guard_results
from rm_dashboard.mandate_reconciliation.subjects import Breach, build_subjects
from rm_dashboard.reconciliation.guard import Note
from rm_dashboard.reportsource import StoreReportSource
from rm_dashboard.runners import open_registry, run_batch
from rm_dashboard.settings import Settings
from rm_dashboard.store import Kind
from rm_dashboard.store.audit import read_audit
from rm_dashboard.store.summary import get_summary

AS_OF = date(2026, 8, 26)
CLIENTS = ["CL-0005", "CL-0007", "CL-0009", "CL-0018", "CL-0012"]


# ---- 2.1 contracts ------------------------------------------------------------------------------------
def test_contract_statuses_and_frozen_models():
    assert set(STATUSES) == set(PRECEDENCE) == {"no_note", "acknowledged", "client_directed", "contradicted"}
    r = BreachResult(portfolio_id="PF-1", kind="band", key="Equity", evidence_id="ev_a", description="d")
    assert r.status == "no_note" and r.ref == "PF-1/band/Equity" and r.note_ids == []
    with pytest.raises(ValidationError):
        r.status = "contradicted"
    with pytest.raises(ValidationError):
        BreachResult(portfolio_id="PF-1", kind="band", key="Equity", evidence_id="ev_a", description="d", status="waived")
    with pytest.raises(ValidationError):
        BreachResult(portfolio_id="PF-1", kind="sector", key="x", evidence_id="ev_a", description="d")
    full = r.model_copy(update={"notes": [NoteQuote(note_id="N-1", note_date=date(2026, 1, 1), quote="q")]})
    assert json.loads(full.model_dump_json())["note_ids"] == ["N-1"]
    assert MandateReconciliation(client_id="CL-1", as_of=AS_OF, status="complete").agent == "mandate_reconciler"
    with pytest.raises(ValidationError):
        MandateReconciliation(client_id="CL-1", as_of=AS_OF, status="done")


# ---- 2.2 subjects from evidence -----------------------------------------------------------------------
def ev(tool, data, **params):
    return ToolResult(data=data, as_of=AS_OF, computation=Computation(tool=tool, version="1", parameters={"as_of": "2026-08-26", **params}))


def drift(pid, *, band=True, position=False, applicable=True):
    if not applicable:
        return ev("analytics.mandate_drift", {"applicable": False, "portfolio_id": pid}, portfolio_id=pid)
    return ev("analytics.mandate_drift", {
        "applicable": True, "portfolio_id": pid,
        "breaches": [{"asset_class": "Commodities", "weight_pct": 14.2, "min_pct": 0.0, "max_pct": 10.0, "gap_pp": 4.2, "breach": "above_max"}] if band else [],
        "single_position_breaches": [{"instrument_id": "SYN-ST-1", "instrument_name": "Nordvind AB", "weight_pct": 30.5, "limit_pct": 12.0, "gap_pp": 18.5}] if position else []},
        portfolio_id=pid)


def excl(pid, breaches=()):
    return ev("analytics.exclusion_breaches", {"applicable": True, "bound": True, "portfolio_id": pid, "breaches": list(breaches)}, portfolio_id=pid)


def listing(*rows):
    return ev("portfolios.list", [{"portfolio_id": p, "portfolio_name": n, "service_model": m} for p, n, m in rows], client_id="CL-1")


def index(*results):
    return {r.evidence_id: r for r in results}


def test_subjects_for_a_band_a_position_and_an_exclusion_breach():
    x = excl("PF-1", [{"instrument_id": "SYN-EQ-8", "instrument_name": "Energy Majors Fund", "held": "direct", "via_instrument_id": None,
                       "via_instrument_name": None, "value": 1.0, "weight_pct": 11.13}])
    breaches, gaps, managed = build_subjects(index(listing(("PF-1", "Core", "Discretionary")), drift("PF-1", position=True), x))
    assert gaps == [] and managed == 1
    assert [(b.kind, b.key) for b in breaches] == [("band", "Commodities"), ("position", "SYN-ST-1"), ("exclusion", "SYN-EQ-8")]
    assert breaches[0].evidence_id == drift("PF-1", position=True).evidence_id and breaches[2].evidence_id == x.evidence_id
    assert "14.20%" in breaches[0].description and "30.50%" in breaches[1].description and "11.13%" in breaches[2].description


def test_custody_portfolio_has_no_subject_and_missing_check_is_a_gap():
    custody = index(listing(("PF-2", "Safe", "Custody")), drift("PF-2", applicable=False))
    assert build_subjects(custody) == ([], [], 0)
    missing = index(listing(("PF-1", "Core", "Advisory")), drift("PF-1"))
    breaches, gaps, managed = build_subjects(missing)
    assert [b.kind for b in breaches] == ["band"] and managed == 1
    assert len(gaps) == 1 and gaps[0].subject == "PF-1" and "exclusion" in gaps[0].description
    nothing = index(listing(("PF-1", "Core", "Advisory")))
    assert len(build_subjects(nothing)[1]) == 2


def test_look_through_exclusion_key_names_the_product():
    x = excl("PF-1", [{"instrument_id": "SYN-EQ-8", "instrument_name": "Energy Majors Fund", "held": "look_through",
                       "via_instrument_id": "SYN-SP-1", "via_instrument_name": "Note A", "value": 1.0, "weight_pct": 3.0}])
    breaches, *_ = build_subjects(index(listing(("PF-1", "Core", "Advisory")), drift("PF-1", band=False), x))
    assert breaches[0].key == "SYN-EQ-8@SYN-SP-1" and "through Note A" in breaches[0].description


# ---- 2.4 guard -----------------------------------------------------------------------------------------
def guard_fixture(multi=False):
    d = drift("PF-1")
    b = Breach("PF-1", "band", "Commodities", d.evidence_id, "Commodities weight is 14.20% against a maximum of 10.00%", "Core",
               ("commodities", "commod", "gold"))
    notes = [Note("N-001", date(2026, 1, 22), "Client instructed more gold; I noted it was above the 10% ceiling. Suitability waiver on file."),
             Note("N-002", date(2026, 9, 1), "Later note about gold."), Note("N-003", date(2026, 2, 1), "Discussed the school fees.")]
    return b, notes, index(d)


def item(**kw):
    base = {"portfolio_id": "PF-1", "kind": "band", "key": "Commodities", "status": "client_directed", "note_ids": ["N-001"],
            "rationale": "The client instructed a gold purchase above the 10% ceiling."}
    return {**base, **kw}


def run_guard(raw, multi=False, ambiguous=()):
    b, notes, evidence = guard_fixture()
    return guard_results(raw, list(ambiguous), [b], notes, evidence, AS_OF, multi_portfolio=multi)


def test_guard_keeps_a_supported_status_and_quotes_the_waiver_as_a_claim():
    out = run_guard([item()])
    r = out.results[0]
    assert (r.status, r.note_ids, r.waiver_claimed) == ("client_directed", ["N-001"], True)
    assert WAIVER_CLAIM in r.rationale and r.notes[0].quote.startswith("Client instructed") and out.gaps == []


@pytest.mark.parametrize("bad", [
    item(status="waived"), item(note_ids=[]), item(note_ids=["N-404"]), item(note_ids=["N-002"]),
    item(evidence_id="ev_other"), item(rationale="  ")])
def test_guard_resets_unsupported_status_to_no_note(bad):
    out = run_guard([bad])
    assert out.results[0].status == "no_note" and out.results[0].notes == []
    assert any(g.kind == "guard_removed" for g in out.gaps)


def test_guard_later_dated_note_is_not_used():
    out = run_guard([item(note_ids=["N-001", "N-002"])])
    assert out.results[0].note_ids == ["N-001"] and any("N-002" in g.description for g in out.gaps)


def test_guard_invented_figure_resets_the_result():
    out = run_guard([item(rationale="The position is 77.7% of the book.")])
    assert out.results[0].status == "no_note" and any("77.7" in g.description for g in out.gaps)


def test_guard_cannot_add_a_breach_and_missing_result_is_neutral():
    out = run_guard([item(key="Gold")])
    assert [r.status for r in out.results] == ["no_note"] and any("not a breach computed" in g.description for g in out.gaps)
    assert run_guard([]).results[0].status == "no_note"


def test_guard_two_portfolios_one_note_goes_to_ambiguous():
    out = run_guard([item(note_ids=["N-003"])], multi=True)
    assert out.results[0].status == "no_note"
    assert [a.note_id for a in out.ambiguous] == ["N-003"]
    named = run_guard([item()], multi=True)
    assert named.results[0].status == "client_directed" and named.ambiguous == []


def test_guard_model_ambiguous_notes_are_validated():
    out = run_guard([], ambiguous=[{"note_id": "N-003", "reason": "either portfolio"}, {"note_id": "N-404", "reason": "x"}])
    assert [a.note_id for a in out.ambiguous] == ["N-003"]


# ---- 2.3 agent on persisted batch output ----------------------------------------------------------------
@pytest.fixture(scope="module")
def reg(seeded_db):
    with open_registry(Settings(db_path=str(seeded_db), max_concurrency=4)) as r:
        yield r


@pytest.fixture(scope="module")
def source(reg, tmp_path_factory):
    out = tmp_path_factory.mktemp("reports")
    run_batch(reg, as_of=AS_OF, store=out, client_ids=CLIENTS, models=lambda role: StubChatModel(role=role))
    return StoreReportSource(out)


def scripted(results, ambiguous=()):
    return FakeListChatModel(responses=[json.dumps({"results": results, "ambiguous_notes": list(ambiguous)})])


def entry(source, client, kind, key, status, notes, rationale, pid):
    ev_id = next(b.evidence_id for b in build_subjects(source.evidence(AS_OF, client))[0] if b.ref == f"{pid}/{kind}/{key}")
    return {"portfolio_id": pid, "kind": kind, "key": key, "evidence_id": ev_id, "status": status, "note_ids": notes, "rationale": rationale}


class Counting(FakeListChatModel):
    calls: int = 0

    def _call(self, *a, **k):
        self.calls += 1
        return super()._call(*a, **k)


def test_no_breaches_means_no_model_call(reg, source):
    m = Counting(responses=["{}"])
    rec = mandate_reconcile(reg, "CL-0012", as_of=AS_OF, source=source, model=m)
    assert rec.status == "complete" and m.calls == 0
    assert all(r.status == "no_note" for r in rec.results)


def test_no_notes_up_to_as_of_means_no_model_call(reg, source):
    m = Counting(responses=["{}"])
    rec = mandate_reconcile(reg, "CL-0005", as_of=date(2026, 1, 1), source=source, model=m)
    assert m.calls == 0 and rec.status in ("complete", "insufficient_data")


def test_notes_about_other_topics_give_no_note(reg, source):
    rec = mandate_reconcile(reg, "CL-0005", as_of=AS_OF, source=source, model=scripted([]))
    assert rec.status == "complete" and rec.results and {r.status for r in rec.results} == {"no_note"}


@pytest.mark.parametrize("model", [StubChatModel(role="mandate_reconciler", mode="raise"),
                                   StubChatModel(role="mandate_reconciler", mode="unparsable"),
                                   FakeListChatModel(responses=["not json"])])
def test_model_failure_is_partial_with_every_breach_no_note(reg, source, model):
    rec = mandate_reconcile(reg, "CL-0007", as_of=AS_OF, source=source, model=model)
    assert rec.status == "partial" and rec.results and {r.status for r in rec.results} == {"no_note"}
    assert any(g.kind == "agent_error" for g in rec.gaps)


def test_missing_report_is_insufficient_data(reg, tmp_path):
    rec = mandate_reconcile(reg, "CL-0007", as_of=AS_OF, source=StoreReportSource(tmp_path), model=scripted([]))
    assert rec.status == "insufficient_data" and rec.results == [] and rec.gaps[0].kind == "no_data"


# ---- 2.5 seeded integration -------------------------------------------------------------------------------
def test_seeded_notes_get_the_expected_statuses(reg, source):
    def status(client, results):
        rec = mandate_reconcile(reg, client, as_of=AS_OF, source=source, model=scripted(results))
        return rec, {r.ref: r for r in rec.results}

    rec, by = status("CL-0005", [entry(source, "CL-0005", "exclusion", "SYN-EQ-0008", "contradicted", ["N-008"],
                                       "The note says the portfolio is fully aligned but the evidence shows the excluded energy fund.", "PF-0007")])
    r = by["PF-0007/exclusion/SYN-EQ-0008"]
    assert r.status == "contradicted" and r.note_ids == ["N-008"] and not r.waiver_claimed
    assert by["PF-0007/exclusion/SYN-ST-0105"].status == "no_note" and rec.status == "complete"

    rec, by = status("CL-0007", [entry(source, "CL-0007", "band", "Commodities", "client_directed", ["N-010"],
                                       "The client instructed a gold purchase above the commodity ceiling.", "PF-0009")])
    r = by["PF-0009/band/Commodities"]
    assert r.status == "client_directed" and r.waiver_claimed and "Suitability waiver on file" in r.notes[0].quote
    assert "not verified" in r.rationale and "weight is" in r.description

    rec, by = status("CL-0009", [entry(source, "CL-0009", "band", "Cash and Equivalents", "client_directed", ["N-013"],
                                       "The client has not executed the deployment plan.", "PF-0011"),
                                 entry(source, "CL-0009", "position", "SYN-ST-0107", "client_directed", ["N-013"],
                                       "The client is unwilling to sell the residual stake.", "PF-0011")])
    assert by["PF-0011/band/Cash and Equivalents"].status == "client_directed" and by["PF-0011/position/SYN-ST-0107"].status == "client_directed"
    assert by["PF-0011/band/Fixed Income"].status == "no_note"

    rec, by = status("CL-0018", [entry(source, "CL-0018", "band", "Commodities", "acknowledged", ["N-024"],
                                       "The client knows the gold position is larger than the original sizing.", "PF-0022")])
    assert by["PF-0022/band/Commodities"].status == "acknowledged"
    assert all(r.evidence_id.startswith("ev_") for r in rec.results)


def test_rerun_is_identical(reg, source):
    a = mandate_reconcile(reg, "CL-0007", as_of=AS_OF, source=source, model=StubChatModel(role="mandate_reconciler"))
    b = mandate_reconcile(reg, "CL-0007", as_of=AS_OF, source=source, model=StubChatModel(role="mandate_reconciler"))
    assert a.model_dump_json() == b.model_dump_json()


def test_notes_after_as_of_are_not_used(reg, source):
    rec = mandate_reconcile(reg, "CL-0007", as_of=AS_OF, source=source, model=scripted([]))
    assert rec.status == "complete"


# ---- 2.6 runner -----------------------------------------------------------------------------------------
def test_cli_saves_artifacts_and_rerun_is_identical(seeded_db, source, capsys, monkeypatch):
    from rm_dashboard.runners.mandate_reconcile import main

    monkeypatch.delenv("RM_DASHBOARD_DB", raising=False)
    base = Path(source.store.path).parent
    args = ["--as-of", "2026-08-26", "--db", str(seeded_db), "--reports-dir", str(base), "--clients", "CL-0007,CL-0001"]
    assert main(args) == 0
    store = source.store

    def saved():
        return {k: store.get(AS_OF, Kind.MANDATE_RECONCILIATION, k) for k in store.keys(AS_OF, Kind.MANDATE_RECONCILIATION)}

    first = saved()
    assert set(first) == {"CL-0007", "CL-0001"}
    MandateReconciliation.model_validate_json(first["CL-0007"])
    assert json.loads(first["CL-0001"])["status"] == "insufficient_data"  # no persisted report in this fixture
    summary = get_summary(store, AS_OF, "mandate-reconcile")
    assert summary["clients"] == 2 and "breach_status_counts" in summary and read_audit(store, AS_OF, "mandate-reconcile")
    assert main(args) == 0
    assert first == saved()
    assert "2 mandate reconciliations written" in capsys.readouterr().out


def test_cli_requires_database_and_date_and_has_help(tmp_path, capsys, monkeypatch):
    from rm_dashboard.runners.mandate_reconcile import main

    monkeypatch.delenv("RM_DASHBOARD_DB", raising=False)
    assert main(["--as-of", "2026-08-26"]) == 2
    assert main(["--as-of", "2026-08-26", "--db", str(tmp_path / "missing.db")]) == 2
    with pytest.raises(SystemExit) as e:
        main(["--help"])
    assert e.value.code == 0 and "rm-dashboard-mandate-reconcile" in capsys.readouterr().out
    with pytest.raises(SystemExit):
        main(["--db", "x.db"])
