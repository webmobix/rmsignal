import json
import shutil
from datetime import date

import pytest
from pydantic import ValidationError

from rm_dashboard.actions import Action, ClientActions, SourceRef
from rm_dashboard.agents import StubChatModel
from rm_dashboard.domain import Gap
from rm_dashboard.overview import Overview, OverviewAction
from rm_dashboard.overview.source import FolderOverviewSource, rms_at
from rm_dashboard.runners import open_registry, run_batch
from rm_dashboard.settings import Settings

AS_OF = date(2026, 8, 26)


@pytest.fixture(scope="module")
def reg(seeded_db):
    with open_registry(Settings(db_path=str(seeded_db), max_concurrency=4)) as r:
        yield r


@pytest.fixture(scope="module")
def reports_dir(reg, tmp_path_factory):
    out = tmp_path_factory.mktemp("reports")
    run_batch(reg, as_of=AS_OF, out_dir=out, client_ids=["CL-0001", "CL-0002", "CL-0003"], models=lambda role: StubChatModel(role=role))
    return out


@pytest.fixture
def base(reports_dir, tmp_path):
    dest = tmp_path / "reports"
    shutil.copytree(reports_dir, dest)
    return dest


def oa(**kw):
    base = dict(rank=1, action_id="CL-0001-A1", client_id="CL-0001", client_name="Name", title="t", what="w", why="y",
                category="compliance_kyc", importance="high")
    return OverviewAction(**{**base, **kw})


# ---- 1.1 contracts ----------------------------------------------------------------------------
def test_contract_enums_and_round_trip():
    with pytest.raises(ValidationError):
        oa(category="nope")
    with pytest.raises(ValidationError):
        oa(importance="urgent")
    assert oa(sources=[]).sources == []  # coverage actions have no sources
    ov = Overview(rm_id="RM-1", rm_name="N", as_of=AS_OF, status="partial", actions=[oa(due_date=date(2026, 11, 30))],
                  gaps=[Gap(kind="other", description="x")])
    assert Overview.model_validate_json(ov.model_dump_json()) == ov
    with pytest.raises(ValidationError):
        Overview(rm_id="RM-1", rm_name="N", as_of=AS_OF, status="done")


# ---- 1.2 source -----------------------------------------------------------------------------------
def write_actions(base, cid, **kw):
    d = base / AS_OF.isoformat() / "actions"
    d.mkdir(exist_ok=True)
    res = ClientActions(client_id=cid, as_of=AS_OF, status=kw.pop("status", "complete"), **kw)
    (d / f"{cid}.json").write_text(res.model_dump_json())
    return res


def test_folder_source_reads_actions_findings_and_handles_absence(base, tmp_path):
    src = FolderOverviewSource(base)
    assert not src.has_actions_folder(AS_OF) and src.client_actions(AS_OF, "CL-0001") is None
    action = Action(title="t", what="w", why="y", category="compliance_kyc", importance="high",
                    sources=[SourceRef(kind="finding", ref="CL-0001#f1", report_path="CL-0001", evidence_ids=[])])
    written = write_actions(base, "CL-0001", actions=[action])
    assert src.has_actions_folder(AS_OF) and src.client_actions(AS_OF, "CL-0001") == written
    assert src.client_actions(AS_OF, "CL-0002") is None
    assert "CL-0001#f1" in src.findings(AS_OF, "CL-0001") and src.findings(AS_OF, "CL-0099") is None
    assert src.reconciliation(AS_OF, "CL-0001") is None
    missing = FolderOverviewSource(tmp_path / "nope")
    assert not missing.has_actions_folder(AS_OF) and missing.findings(AS_OF, "CL-0001") is None
    assert missing.location(AS_OF).endswith("2026-08-26/actions")


# ---- 1.3 scoping --------------------------------------------------------------------------------------
def test_rms_at_groups_clients_by_rm(reg):
    rms = rms_at(reg.ctx.repo, AS_OF)
    assert list(rms) == ["RM-SG-014"] and len(rms["RM-SG-014"].clients) == 20
    c = rms["RM-SG-014"].clients[0]
    assert c.client_id == "CL-0001" and c.client_name == "Hartono Wijaya Kusuma" and c.aum_usd > 0
    assert rms["RM-SG-014"].rm_name == "Priscilla Ong"


def test_rms_at_separates_other_rms(reg):
    import polars as pl

    class Repo:
        def clients(self, as_of):
            frame = pl.DataFrame({"client_id": ["C1", "C2", "C3"], "client_name": ["A", "B", "C"], "rm_id": ["R2", "R1", "R1"],
                                  "rm_name": ["Two", "One", "One"], "aum_usd": [1.0, 2.0, None]})
            return type("R", (), {"frame": frame})()

    rms = rms_at(Repo(), AS_OF)
    assert list(rms) == ["R1", "R2"]
    assert [c.client_id for c in rms["R1"].clients] == ["C2", "C3"] and rms["R1"].clients[1].aum_usd == 0.0
    assert [c.client_id for c in rms["R2"].clients] == ["C1"]


# ---- 2.x aggregation ------------------------------------------------------------------------------------
from rm_dashboard.overview.build import build_overview, coverage_action, rank_actions
from rm_dashboard.overview.source import ClientInfo, RmInfo


def client_action(title, importance="high", category="concentration_risk", horizon="none", due=None, ref="CL-0001#f1", cid_path="CL-0001"):
    return Action(title=title, what=f"do {title}", why=f"because {title}", category=category, importance=importance,
                  horizon=horizon, due_date=due, sources=[SourceRef(kind="finding", ref=ref, report_path=cid_path, evidence_ids=[])])


def rm_of(*ids, aum=None):
    aum = aum or {}
    return RmInfo("RM-SG-014", "Priscilla Ong", tuple(ClientInfo(i, f"Client {i}", aum.get(i, 1.0)) for i in ids))


def test_ranking_importance_horizon_date_aum_client_title(base):
    write_actions(base, "CL-0001", actions=[client_action("low one", "low"), client_action("crit", "critical", ref="CL-0001#f2"),
                                           client_action("same", "high", horizon="later", due=date(2026, 12, 1), ref="CL-0001#f3")])
    write_actions(base, "CL-0002", actions=[client_action("same", "high", horizon="later", due=date(2026, 12, 1), ref="CL-0002#f1", cid_path="CL-0002"),
                                           client_action("sooner", "high", horizon="within_30_days", due=date(2026, 9, 5), ref="CL-0002#f2", cid_path="CL-0002")])
    ov = build_overview(rm_of("CL-0001", "CL-0002", aum={"CL-0001": 5.0, "CL-0002": 50.0}), AS_OF, FolderOverviewSource(base))
    order = [(a.client_id, a.title) for a in ov.actions]
    assert order[0] == ("CL-0001", "crit")
    assert order[1] == ("CL-0002", "sooner")                  # same importance, nearer horizon
    assert order[2:4] == [("CL-0002", "same"), ("CL-0001", "same")]  # same horizon and date: larger AUM first
    assert [a.rank for a in ov.actions] == list(range(1, len(ov.actions) + 1))
    imp = [a.importance for a in ov.actions if a.origin == "client_actions"]
    assert imp == sorted(imp, key=["critical", "high", "medium", "low"].index)


def test_rerun_equality_and_content_not_rewritten(base):
    act = client_action("Concentration")
    write_actions(base, "CL-0001", actions=[act])
    src = FolderOverviewSource(base)
    a = build_overview(rm_of("CL-0001"), AS_OF, src)
    b = build_overview(rm_of("CL-0001"), AS_OF, src)
    assert a.model_dump_json() == b.model_dump_json()
    oa_ = a.actions[0]
    assert (oa_.what, oa_.why, oa_.category, oa_.importance, oa_.sources) == (act.what, act.why, act.category, act.importance, act.sources)
    assert oa_.action_id == "CL-0001-A1" and oa_.client_name == "Client CL-0001"


def test_by_category_groups_and_counts(base):
    write_actions(base, "CL-0001", actions=[client_action("a"), client_action("b", category="compliance_kyc", ref="CL-0001#f2"),
                                           client_action("c", ref="CL-0001#f3")])
    ov = build_overview(rm_of("CL-0001"), AS_OF, FolderOverviewSource(base))
    groups = {g.category: g for g in ov.by_category}
    assert groups["concentration_risk"].count == 2 and groups["compliance_kyc"].count == 1
    assert sum(g.count for g in ov.by_category) == len(ov.actions)
    assert set(groups["concentration_risk"].action_ids) <= {a.action_id for a in ov.actions}


def test_broken_finding_link_is_a_gap_and_the_action_stays(base):
    write_actions(base, "CL-0001", actions=[client_action("ok"), client_action("bad", ref="CL-0001#f999")])
    ov = build_overview(rm_of("CL-0001"), AS_OF, FolderOverviewSource(base))
    assert ov.status == "partial" and {a.title for a in ov.actions} == {"ok", "bad"}
    assert any(g.description.startswith("link_broken: CL-0001: CL-0001#f999") for g in ov.gaps)


def test_valid_links_give_a_complete_overview(base):
    from rm_dashboard.reportsource import FolderReportSource, flatten

    flat = flatten(FolderReportSource(base).report(AS_OF, "CL-0001"))[0]
    act = Action(title="t", what="w", why="y", category="compliance_kyc", importance="high",
                 sources=[SourceRef(kind="finding", ref=flat.ref, report_path=flat.report_path, evidence_ids=list(flat.evidence_ids))])
    write_actions(base, "CL-0001", actions=[act])
    ov = build_overview(rm_of("CL-0001"), AS_OF, FolderOverviewSource(base))
    assert ov.status == "complete" and ov.gaps == []


def test_note_link_checked_against_reconciliation(base):
    from rm_dashboard.reconciliation import NoteResult, Reconciliation

    d = base / AS_OF.isoformat() / "reconciliation"
    d.mkdir()
    rec = Reconciliation(client_id="CL-0001", as_of=AS_OF, status="complete", results=[
        NoteResult(note_id="N-001", note_date=date(2026, 1, 8), note_quote="q", verdict="contradicted", rationale="r")])
    (d / "CL-0001.json").write_text(rec.model_dump_json())
    note_action = lambda ref: Action(title="n", what="w", why="y", category="client_contact", importance="medium",
                                     sources=[SourceRef(kind="note", ref=ref)])
    write_actions(base, "CL-0001", actions=[note_action("N-001")])
    assert build_overview(rm_of("CL-0001"), AS_OF, FolderOverviewSource(base)).gaps == []
    write_actions(base, "CL-0001", actions=[note_action("N-404")])
    assert any("N-404" in g.description for g in build_overview(rm_of("CL-0001"), AS_OF, FolderOverviewSource(base)).gaps)


def test_client_stage_gaps_are_carried_over(base):
    write_actions(base, "CL-0001", actions=[client_action("x")], status="partial", gaps=[Gap(kind="guard_removed", description="one removed")])
    ov = build_overview(rm_of("CL-0001"), AS_OF, FolderOverviewSource(base))
    assert ov.status == "partial" and any(g.kind == "guard_removed" and g.description == "CL-0001: one removed" and g.subject == "CL-0001" for g in ov.gaps)


def test_no_client_outputs_gives_insufficient_data(base):
    ov = build_overview(rm_of("CL-0001", "CL-0002"), AS_OF, FolderOverviewSource(base))
    assert ov.status == "insufficient_data" and ov.actions == [] and ov.gaps[0].kind == "no_data" and "actions" in ov.gaps[0].description
    assert {c.reason for c in ov.clients_without_actions} == {"actions_missing"}
    nothing = build_overview(rm_of("CL-0099"), AS_OF, FolderOverviewSource(base))
    assert nothing.clients_without_actions[0].reason == "report_missing"


# ---- 2.3 coverage ---------------------------------------------------------------------------------------
def test_coverage_cases(base):
    write_actions(base, "CL-0001", actions=[client_action("x")])                    # normal
    write_actions(base, "CL-0002", actions=[])                                      # complete, nothing to do
    write_actions(base, "CL-0003", actions=[], status="partial", gaps=[Gap(kind="agent_error", description="model failed")])
    ov = build_overview(rm_of("CL-0001", "CL-0002", "CL-0003", "CL-0004", "CL-0099"), AS_OF, FolderOverviewSource(base))
    reasons = {c.client_id: c.reason for c in ov.clients_without_actions}
    assert reasons == {"CL-0002": "no_action_needed", "CL-0003": "actions_missing", "CL-0004": "report_missing", "CL-0099": "report_missing"}
    cover = {a.client_id: a for a in ov.actions if a.origin == "coverage"}
    assert set(cover) == {"CL-0003", "CL-0004", "CL-0099"}   # CL-0003 has a report but no delivered actions; CL-0004 has none at all
    assert all(a.category == "data_quality" and a.importance == "high" and a.sources == [] for a in cover.values())
    assert "report" in cover["CL-0004"].title.lower() and "missing" in cover["CL-0004"].title.lower()
    assert "CL-0002" not in cover


def test_report_present_but_actions_file_absent_is_actions_missing(base):
    write_actions(base, "CL-0001", actions=[client_action("x")])
    ov = build_overview(rm_of("CL-0001", "CL-0002"), AS_OF, FolderOverviewSource(base))  # CL-0002 has a report from the batch
    assert [(c.client_id, c.reason) for c in ov.clients_without_actions] == [("CL-0002", "actions_missing")]
    assert any(a.origin == "coverage" and a.client_id == "CL-0002" and "Actions missing" in a.title for a in ov.actions)


def test_every_client_is_accounted_for(base):
    write_actions(base, "CL-0001", actions=[client_action("x")])
    ids = ["CL-0001", "CL-0002", "CL-0003"]
    ov = build_overview(rm_of(*ids), AS_OF, FolderOverviewSource(base))
    covered = {a.client_id for a in ov.actions} | {c.client_id for c in ov.clients_without_actions}
    assert covered == set(ids)


# ---- 3.x summary ---------------------------------------------------------------------------------------------
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from rm_dashboard.overview import create_overview
from rm_dashboard.overview.summary import guard_summary


def summary_model(mode="normal"):
    return StubChatModel(role="rm_overview_summary", mode=mode)


@pytest.fixture
def two_clients(base):
    write_actions(base, "CL-0001", actions=[client_action("Discuss concentration", "high"), client_action("Prepare KYC", "medium", "compliance_kyc", ref="CL-0001#f2")])
    write_actions(base, "CL-0002", actions=[client_action("Reduce exposure", "high", ref="CL-0002#f1", cid_path="CL-0002")])
    return FolderOverviewSource(base)


def test_summary_and_themes_added_actions_untouched(reg, two_clients):
    rm = rm_of("CL-0001", "CL-0002")
    plain = build_overview(rm, AS_OF, two_clients)
    ov = create_overview(reg, rm, as_of=AS_OF, source=two_clients, model=summary_model())
    assert ov.summary.startswith("[[CL-0001]] _") and ov.summary.endswith("_.") and ov.actions == plain.actions
    assert [t.title for t in ov.themes] == ["Concentration risk across clients"] and len(ov.themes[0].action_ids) == 2
    assert ov.status == plain.status


def test_model_reorder_attempt_changes_nothing(reg, two_clients):
    rm = rm_of("CL-0001", "CL-0002")
    plain = build_overview(rm, AS_OF, two_clients)
    ov = create_overview(reg, rm, as_of=AS_OF, source=two_clients, model=summary_model("reorder"))
    assert [a.action_id for a in ov.actions] == [a.action_id for a in plain.actions] and ov.actions == plain.actions


def test_invented_figure_removes_summary_and_marks_partial(reg, two_clients):
    ov = create_overview(reg, rm_of("CL-0001", "CL-0002"), as_of=AS_OF, source=two_clients, model=summary_model("uncited_number"))
    assert ov.summary == "" and ov.actions and ov.status == "partial" and any("7351.24" in g.description for g in ov.gaps)


def test_unknown_theme_ids_are_dropped(reg, two_clients):
    ov = create_overview(reg, rm_of("CL-0001", "CL-0002"), as_of=AS_OF, source=two_clients, model=summary_model("bad_ids"))
    assert [t.title for t in ov.themes] == ["Concentration risk across clients"]
    assert any("CL-9999-A1" in g.description for g in ov.gaps)


@pytest.mark.parametrize("mode", ["raise", "unparsable"])
def test_model_failure_keeps_actions_and_is_partial(reg, two_clients, mode):
    rm = rm_of("CL-0001", "CL-0002")
    ov = create_overview(reg, rm, as_of=AS_OF, source=two_clients, model=summary_model(mode))
    assert ov.status == "partial" and ov.summary == "" and ov.themes == []
    assert ov.actions == build_overview(rm, AS_OF, two_clients).actions and any(g.kind == "agent_error" for g in ov.gaps)


def test_no_actions_skips_the_model_call(reg, base):
    model = summary_model()
    ov = create_overview(reg, rm_of("CL-0001"), as_of=AS_OF, source=FolderOverviewSource(base), model=model)
    assert ov.status == "insufficient_data" and model.calls == 0
    write_actions(base, "CL-0001", actions=[])
    ov = create_overview(reg, rm_of("CL-0001"), as_of=AS_OF, source=FolderOverviewSource(base), model=model)
    assert ov.actions == [] and model.calls == 0 and ov.status == "complete"


def test_guard_summary_rules():
    top = [oa(action_id="A1", why="exposure is 42.6%"), oa(action_id="A2", rank=2, why="x"), oa(action_id="A3", rank=3, why="y")]
    s, t, g = guard_summary({"summary": "Exposure is 43%.", "themes": [{"title": "Pair", "action_ids": ["A1", "A2"]},
                                                                       {"title": "Solo", "action_ids": ["A1"]},
                                                                       {"title": "Number 99%", "action_ids": ["A2", "A3"]}, "junk"]}, top)
    assert s == "Exposure is 43%." and [x.title for x in t] == ["Pair"] and len(g) == 3
    assert guard_summary("junk", top)[2][0].kind == "agent_error"


def test_names_pseudonymised_for_the_model(reg, base):
    write_actions(base, "CL-0001", actions=[Action(title="Call Hartono Wijaya Kusuma", what="Discuss with Hartono Wijaya Kusuma.", why="y",
                                                   category="client_contact", importance="medium",
                                                   sources=[SourceRef(kind="finding", ref="CL-0001#f1", report_path="CL-0001", evidence_ids=[])])])
    rm = RmInfo("RM-SG-014", "Priscilla Ong", (ClientInfo("CL-0001", "Hartono Wijaya Kusuma", 1.0),))
    model = summary_model()
    ov = create_overview(reg, rm, as_of=AS_OF, source=FolderOverviewSource(base), model=model)
    sent = json.dumps([[m.content for m in ms] for ms in model.seen])
    assert "Hartono" not in sent and "Kusuma" not in sent and "PERSON_" in sent
    assert ov.actions[0].client_name == "Hartono Wijaya Kusuma"  # delivered content keeps real names
    pseudo = "PERSON_" + __import__("hashlib").sha256(b"rm-dashboard:CL-0001").hexdigest()[:6].upper()
    reply = json.dumps({"summary": f"Start with {pseudo}.", "themes": []})
    ov = create_overview(reg, rm, as_of=AS_OF, source=FolderOverviewSource(base), model=FakeListChatModel(responses=[reply]))
    assert ov.summary == "Start with Hartono Wijaya Kusuma."


def test_policy_denial_leaves_actions_and_marks_partial(reg, two_clients):
    from rm_dashboard.policy import ScriptedEngine

    ov = create_overview(reg, rm_of("CL-0001", "CL-0002"), as_of=AS_OF, source=two_clients, model=summary_model(),
                         engine=ScriptedEngine(rules={"request_entitlement": "deny"}))
    assert ov.actions and ov.summary == "" and ov.status == "partial" and any(g.kind == "policy_denied" for g in ov.gaps)


# ---- 4.1 CLI ------------------------------------------------------------------------------------------------------
def test_cli_writes_overview_and_rerun_is_byte_identical(seeded_db, base, capsys, monkeypatch):
    from rm_dashboard.runners.actions import main as actions_main
    from rm_dashboard.runners.overview import main

    monkeypatch.delenv("RM_DASHBOARD_DB", raising=False)
    assert actions_main(["--as-of", "2026-08-26", "--db", str(seeded_db), "--reports-dir", str(base), "--clients", "CL-0001,CL-0002,CL-0003"]) == 0
    args = ["--as-of", "2026-08-26", "--db", str(seeded_db), "--reports-dir", str(base)]
    assert main(args) == 0
    out = base / "2026-08-26" / "overview"
    first = {p.name: p.read_bytes() for p in out.glob("*.json")}
    assert set(first) == {"RM-SG-014.json", "summary.json"}
    ov = Overview.model_validate_json(first["RM-SG-014.json"])
    assert ov.rm_id == "RM-SG-014" and len(ov.clients) == 20 and ov.actions
    assert {a.client_id for a in ov.actions if a.origin == "coverage"} >= {"CL-0004", "CL-0020"}  # no report for those clients
    assert [a.rank for a in ov.actions] == list(range(1, len(ov.actions) + 1))
    assert main(args) == 0
    assert first == {p.name: p.read_bytes() for p in out.glob("*.json")}
    text = capsys.readouterr().out
    assert "RM-SG-014:" in text and "1 overviews written" in text
    assert main([*args, "--rm", "RM-UNKNOWN"]) == 0 and json.loads((out / "summary.json").read_text())["rms"] == 0


def test_cli_without_actions_delivers_insufficient_data(seeded_db, tmp_path, monkeypatch):
    from rm_dashboard.runners.overview import main

    monkeypatch.delenv("RM_DASHBOARD_DB", raising=False)
    assert main(["--as-of", "2026-08-26", "--db", str(seeded_db), "--reports-dir", str(tmp_path)]) == 0
    ov = Overview.model_validate_json((tmp_path / "2026-08-26" / "overview" / "RM-SG-014.json").read_text())
    assert ov.status == "insufficient_data" and ov.actions == [] and ov.gaps


def test_cli_requires_database_and_date(tmp_path, capsys, monkeypatch):
    from rm_dashboard.runners.overview import main

    monkeypatch.delenv("RM_DASHBOARD_DB", raising=False)
    assert main(["--as-of", "2026-08-26"]) == 2
    assert main(["--as-of", "2026-08-26", "--db", str(tmp_path / "missing.db")]) == 2
    with pytest.raises(SystemExit):
        main(["--db", "x.db"])
    assert "no database given" in capsys.readouterr().err


def test_summary_input_carries_client_ids(two_clients):
    ov = build_overview(rm_of("CL-0001", "CL-0002"), AS_OF, two_clients)
    from rm_dashboard.overview.summary import build_input
    assert '"client_id": "CL-0001"' in build_input(ov, ov.actions)


def test_guard_keeps_client_markup_and_ignores_ids_as_figures():
    top = [oa(action_id="A1", client_id="CL-0001", why="x"), oa(action_id="A2", rank=2, client_id="CL-0002", why="y")]
    summary, _, gaps = guard_summary({"summary": "[[CL-0001]] _call today_. [[CL-0002]] _review_."}, top)
    assert summary == "[[CL-0001]] _call today_. [[CL-0002]] _review_." and gaps == []


def test_guard_removes_summary_with_unknown_client():
    top = [oa(action_id="A1", client_id="CL-0001", why="x")]
    summary, _, gaps = guard_summary({"summary": "[[CL-0009]] _call_."}, top)
    assert summary == "" and gaps and "CL-0009" in gaps[0].description
