"""Client analyses use the persisted outlooks: citations, the house-view flag, missing outlooks and the stages after the batch."""

from datetime import date

import pytest

from rm_dashboard.agents import StubChatModel, analyse
from rm_dashboard.domain import Computation, ToolResult
from rm_dashboard.reportsource import FolderReportSource
from rm_dashboard.runners import run_batch
from rm_dashboard.runners.actions import run_actions
from rm_dashboard.runners.overview import run_overview
from rm_dashboard.runners.reconcile import run_reconcile
from rm_dashboard.actions.assemble import finalise
from rm_dashboard.actions.contracts import Action, SourceRef
from rm_dashboard.actions.rubric import conditions

AS_OF = date(2026, 8, 26)


class Models:
    def __init__(self):
        self.made = {}

    def __call__(self, role):
        m = StubChatModel(role=role)
        self.made.setdefault(role, []).append(m)
        return m


def run(make_scope, role, subject, **kw):
    scope = make_scope(subject=subject, **kw)
    models = Models()
    return analyse(role, subject, scope, models), scope, models


def tools_of(scope):
    return {r.computation.tool for r in scope.store.results.values()}


# ---- 2.1 no delegation to the instrument analyst --------------------------------------------------
def test_the_portfolio_run_makes_no_child_runs_and_binds_the_outlook_tools(make_scope):
    from rm_dashboard.agents.tooladapter import lc_name

    r, scope, models = run(make_scope, "portfolio_analyst", "PF-0001", outlooks=True)
    assert r.children == [] and list(models.made) == ["portfolio_analyst"]
    names = {n for m in models.made["portfolio_analyst"] for bound in m.bound_tool_names for n in bound}
    assert {lc_name("outlook.market"), lc_name("outlook.instrument")} <= names and "task" not in names


def test_the_relationship_run_binds_only_the_market_outlook_tool(make_scope):
    from rm_dashboard.agents.tooladapter import lc_name

    _, _, models = run(make_scope, "relationship_analyst", "CL-0001", outlooks=True)
    names = {n for m in models.made["relationship_analyst"] for bound in m.bound_tool_names for n in bound}
    assert lc_name("outlook.market") in names and lc_name("outlook.instrument") not in names


def test_prompts_state_the_outlook_rules():
    from rm_dashboard.agents import prompts

    for p in (prompts.PORTFOLIO_ANALYST, prompts.RELATIONSHIP_ANALYST):
        assert "the bank's view as of" in p and "not a fact" in p and "no outlook" in p
    assert "outlook.instrument" in prompts.PORTFOLIO_ANALYST and "instrument analyst to delegate" in prompts.PORTFOLIO_ANALYST
    assert "outlook.market" in prompts.RELATIONSHIP_ANALYST


# ---- 2.2 outlook findings --------------------------------------------------------------------------
def test_findings_citing_outlook_results_are_kept_and_dated(make_scope):
    r, scope, _ = run(make_scope, "portfolio_analyst", "PF-0001", outlooks=True)
    views = [f for f in r.findings if f.claim.startswith("The bank's view of")]
    assert len(views) == 2 and not [g for g in r.gaps if g.kind == "guard_removed"]
    for f in views:
        assert "as of 2026-08-26" in f.claim and "confidence" in f.claim and "horizon" in f.claim
        assert all(scope.store.get(i).computation.tool == "outlook.instrument" for i in f.evidence_ids)


def test_the_report_carries_the_house_view_flag(make_scope):
    r, *_ = run(make_scope, "portfolio_analyst", "PF-0001", outlooks=True)
    flags = [f for f in r.flags if f.code == "house_view"]
    assert flags and all("not a fact" in f.message for f in flags)
    rel, *_ = run(make_scope, "relationship_analyst", "CL-0001", outlooks=True)
    assert any(f.code == "house_view" for f in rel.flags)


def test_the_evidence_behind_an_outlook_is_resolvable_and_citable(make_scope):
    from rm_dashboard.agents.guard import guard_output

    _, scope, _ = run(make_scope, "portfolio_analyst", "PF-0001", outlooks=True)
    inst = next(r for r in scope.store.results.values() if r.computation.tool == "outlook.instrument")
    underlying = inst.data["drivers"][0]["evidence_ids"][0]
    assert underlying in scope.store
    out = guard_output([{"claim": f"The outlook rests on {inst.data['drivers'][0]['claim']}", "confidence": "low",
                         "evidence_ids": [underlying]}], "", scope.store, AS_OF)
    assert len(out.findings) == 1 and not out.gaps


def test_an_unsupported_figure_in_an_outlook_finding_is_still_removed(make_scope):
    from rm_dashboard.agents.guard import guard_output

    _, scope, _ = run(make_scope, "portfolio_analyst", "PF-0001", outlooks=True)
    inst = next(r for r in scope.store.results.values() if r.computation.tool == "outlook.instrument")
    out = guard_output([{"claim": "The bank expects a 41.7% gain.", "confidence": "low", "evidence_ids": [inst.evidence_id]}], "", scope.store, AS_OF)
    assert not out.findings and any(g.kind == "guard_removed" for g in out.gaps)


def test_an_outlook_alone_never_raises_an_action_floor():
    view = ToolResult(data={"instrument_id": "SYN-EQ-0001", "direction": "negative", "drivers": [{"claim": "Prices fell sharply."}]},
                      as_of=AS_OF, computation=Computation(tool="outlook.instrument", version="1"))
    market = ToolResult(data={"market_outlook_as_of": "2026-08-26", "views": [{"segment": "overall", "direction": "negative"}]},
                        as_of=AS_OF, computation=Computation(tool="outlook.market", version="1"))
    assert conditions([view, market]) == []
    from rm_dashboard.reportsource import FlatFinding

    finding = FlatFinding(ref="CL-0001#f1", report_path="CL-0001", claim="The bank's view of SYN-EQ-0001 is negative.", confidence="medium",
                          evidence_ids=(view.evidence_id,))
    action = Action(action_id="CL-0001-A1", category="concentration_risk", importance="low", title="Watch SYN-EQ-0001", what="Watch it.",
                    why="The bank's view is negative.", sources=[SourceRef(kind="finding", ref="CL-0001#f1", evidence_ids=[view.evidence_id])])
    out = finalise([action], {"CL-0001#f1": finding}, {}, {view.evidence_id: view}, AS_OF)
    assert out[0].importance == "low" and out[0].importance_raised_from is None


# ---- 2.3 missing outlooks and the stages after the batch -----------------------------------------------
def test_missing_outlooks_are_gaps_and_no_forward_view_is_stated(make_scope):
    r, scope, _ = run(make_scope, "portfolio_analyst", "PF-0001")          # no reports folder: no outlooks
    missing = [g for g in r.gaps if g.kind == "no_data" and g.subject == "outlook.instrument"]
    assert r.status == "partial" and len(missing) == 2 and len({g.description for g in missing}) == 2
    assert any(g.subject == "outlook.market" for g in r.gaps)
    assert not any(f.claim.startswith("The bank's") for f in r.findings)
    assert [f for f in r.findings if f.claim.startswith("No outlook is available")]
    assert not any(f.code == "house_view" for f in r.flags)


def test_missing_outlook_files_in_an_existing_folder(make_scope, registry, tmp_path):
    import dataclasses

    from rm_dashboard.agents import RunScope
    from rm_dashboard.policy import RunContext
    from rm_dashboard.tools import ToolRegistry

    empty = ToolRegistry(dataclasses.replace(registry.ctx, reports_dir=tmp_path))
    r = analyse("portfolio_analyst", "PF-0001", RunScope(run=RunContext("PF-0001", AS_OF), registry=empty), Models())
    assert r.status == "partial" and sum(1 for g in r.gaps if g.subject == "outlook.instrument") == 2
    assert any("rm-dashboard-outlook" in g.description for g in r.gaps)


def test_a_later_outlook_is_not_used(make_scope):
    scope = make_scope(subject="PF-0001", as_of=date(2026, 6, 30), outlooks=True)
    r = analyse("portfolio_analyst", "PF-0001", scope, Models())
    assert not any(f.claim.startswith("The bank's") for f in r.findings)
    assert any(g.subject == "outlook.instrument" for g in r.gaps)


def test_an_earlier_outlook_is_used_with_its_date(make_scope):
    scope = make_scope(subject="PF-0001", as_of=date(2026, 9, 15), outlooks=True)
    r = analyse("portfolio_analyst", "PF-0001", scope, Models())
    views = [f for f in r.findings if f.claim.startswith("The bank's view of")]
    assert views and all("as of 2026-08-26" in f.claim for f in views)
    assert any(f.code == "stale_outlook" for f in r.flags)


def test_the_stages_after_the_batch_work_without_instrument_children(outlook_registry, tmp_path):
    clients = ["CL-0001", "CL-0002", "CL-0003"]
    batch = run_batch(outlook_registry, as_of=AS_OF, out_dir=tmp_path, client_ids=clients, models=lambda role: StubChatModel(role=role))
    for rep in batch.reports.values():
        assert all(not c.children for c in rep.children)
    rec = run_reconcile(outlook_registry, as_of=AS_OF, reports_dir=tmp_path, client_ids=clients, models=lambda role: StubChatModel(role=role))
    act = run_actions(outlook_registry, as_of=AS_OF, reports_dir=tmp_path, client_ids=clients, models=lambda role: StubChatModel(role=role))
    ov = run_overview(outlook_registry, as_of=AS_OF, reports_dir=tmp_path, models=lambda role: StubChatModel(role=role))
    assert set(rec.reconciliations) == set(act.results) == set(clients) and ov.overviews
    assert all(a.status in ("complete", "partial") for a in act.results.values())
    src = FolderReportSource(tmp_path)
    ev = src.evidence(AS_OF, "CL-0001")
    report = src.report(AS_OF, "CL-0001")
    assert {i for f in report.findings for i in f.evidence_ids} <= set(ev)
    assert {i for c in report.children for f in c.findings for i in f.evidence_ids} <= set(ev)


def test_the_batch_finds_the_outlooks_beside_its_reports(registry, outlook_dir, tmp_path):
    """The analyse command writes reports where the outlook stage wrote its outlooks: no extra wiring needed."""
    import shutil

    shutil.copytree(outlook_dir, tmp_path, dirs_exist_ok=True)
    assert registry.ctx.reports_dir is None
    batch = run_batch(registry, as_of=AS_OF, out_dir=tmp_path, client_ids=["CL-0001"], models=lambda role: StubChatModel(role=role))
    rep = batch.reports["CL-0001"]
    assert any(f.claim.startswith("The bank's market view as of") for f in rep.findings)
    assert any(f.claim.startswith("The bank's view of") for c in rep.children for f in c.findings)
    assert any(f.code == "house_view" for f in rep.flags)


def test_the_batch_without_outlooks_is_partial_not_failed(registry, tmp_path):
    batch = run_batch(registry, as_of=AS_OF, out_dir=tmp_path, client_ids=["CL-0001"], models=lambda role: StubChatModel(role=role))
    rep = batch.reports["CL-0001"]
    assert rep.status == "partial" and any(g.subject == "outlook.market" for g in rep.gaps)
    assert not any(f.claim.startswith("The bank's") for f in rep.findings)
