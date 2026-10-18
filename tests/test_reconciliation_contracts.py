from datetime import date

import pytest
from pydantic import ValidationError

from rm_dashboard.domain import Finding, Report
from rm_dashboard.reconciliation.contracts import NoteResult, Reconciliation
from rm_dashboard.reportsource import StoreReportSource, flatten


def result(**kw):
    base = dict(note_id="N-001", note_date=date(2026, 1, 8), note_quote="q", verdict="consistent", rationale="r")
    return NoteResult(**{**base, **kw})


def test_verdict_and_kind_are_closed_sets():
    with pytest.raises(ValidationError):
        result(verdict="maybe")
    with pytest.raises(ValidationError):
        result(kind="mandate")
    assert result().kind == "rm_note"


def test_reconciliation_round_trips_through_json():
    r = Reconciliation(client_id="CL-0001", as_of=date(2026, 8, 26), status="partial", results=[result(finding_refs=["CL-0001#f1"])])
    assert Reconciliation.model_validate_json(r.model_dump_json()) == r
    with pytest.raises(ValidationError):
        Reconciliation(client_id="CL-0001", as_of=date(2026, 8, 26), status="done")


def test_flatten_gives_stable_refs_for_nested_reports():
    leaf = Report(subject="SYN-EQ-0001", as_of=date(2026, 8, 26), status="complete", agent="instrument_analyst",
                  findings=[Finding(claim="leaf", evidence_ids=["ev_1"])])
    pf = Report(subject="PF-0001", as_of=date(2026, 8, 26), status="complete", agent="portfolio_analyst",
                findings=[Finding(claim="a", evidence_ids=["ev_2"]), Finding(claim="b", evidence_ids=["ev_3"])], children=[leaf])
    top = Report(subject="CL-0001", as_of=date(2026, 8, 26), status="partial", agent="relationship_analyst",
                 findings=[Finding(claim="top", evidence_ids=["ev_4"])], children=[pf])
    flat = {f.ref: f for f in flatten(top)}
    assert list(flat) == ["CL-0001#f1", "CL-0001/PF-0001#f1", "CL-0001/PF-0001#f2", "CL-0001/PF-0001/SYN-EQ-0001#f1"]
    assert flat["CL-0001/PF-0001#f2"].claim == "b" and flat["CL-0001/PF-0001#f2"].evidence_ids == ("ev_3",)
    assert flatten(top) == flatten(top)


def test_folder_source_missing_files_return_none(tmp_path):
    src = StoreReportSource(tmp_path / "nope")
    assert src.report(date(2026, 8, 26), "CL-0001") is None and src.evidence(date(2026, 8, 26), "CL-0001") is None
