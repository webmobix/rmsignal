import shutil
from pathlib import Path

import pytest

from rm_dashboard.data import seed

DATA_DIR = seed.DEFAULT_DATA_DIR


@pytest.fixture
def data_dir() -> Path:
    return DATA_DIR


@pytest.fixture
def data_copy(tmp_path) -> Path:
    """A writable copy of the dataset for failure-mode tests."""
    dest = tmp_path / "data"
    shutil.copytree(DATA_DIR, dest)
    return dest


@pytest.fixture(scope="session")
def seeded_db(tmp_path_factory) -> Path:
    db = tmp_path_factory.mktemp("db") / "rm.db"
    seed.seed(db, DATA_DIR)
    return db


@pytest.fixture(scope="session")
def pit_repo(seeded_db):
    from rm_dashboard.data.datasource import SqliteDataSource
    from rm_dashboard.pit import PolarsPitRepository

    with SqliteDataSource(seeded_db) as ds:
        yield PolarsPitRepository(ds)


@pytest.fixture(scope="session")
def registry(pit_repo):
    from rm_dashboard.tools import ToolContext, ToolRegistry

    return ToolRegistry(ToolContext(pit_repo))


@pytest.fixture(scope="session")
def outlook_dir(registry, tmp_path_factory):
    """Reports folder holding the market and instrument outlooks of 2026-08-26 (stub model)."""
    from datetime import date

    from rm_dashboard.agents import StubChatModel
    from rm_dashboard.runners.outlook import run_outlook

    d = tmp_path_factory.mktemp("outlooks")
    run_outlook(registry, as_of=date(2026, 8, 26), reports_dir=d, models=lambda role: StubChatModel(role=role))
    return d


@pytest.fixture(scope="session")
def outlook_registry(registry, outlook_dir):
    """The tool registry pointed at ``outlook_dir``: client analysts find the outlooks."""
    import dataclasses

    from rm_dashboard.tools import ToolRegistry

    return ToolRegistry(dataclasses.replace(registry.ctx, reports_dir=outlook_dir))


@pytest.fixture
def make_scope(registry, outlook_registry):
    """Factory for a fresh run scope on the seeded data. ``outlooks=True`` makes the persisted outlooks available."""
    from datetime import date

    from rm_dashboard.agents import RunScope
    from rm_dashboard.agents.scope import register_people
    from rm_dashboard.policy import RunContext, Pseudonymiser

    def make(as_of=date(2026, 8, 26), engine=None, subject="CL-0001", register_names=True, outlooks=False):
        reg = outlook_registry if outlooks else registry
        run = RunContext(subject, as_of, **({"engine": engine} if engine else {}))
        if register_names:
            register_people(run, reg.ctx.repo, date(2026, 12, 31))
        return RunScope(run=run, registry=reg)

    return make


@pytest.fixture(scope="session")
def api_reports(seeded_db, tmp_path_factory) -> Path:
    """A small, deterministic run of every stage, built in a temp folder (never ``reports/``).

    Market outlook and two instrument outlooks; analysis for CL-0001, CL-0002, CL-0003 and CL-0011; client actions for
    the same four; the RM overview over them. For CL-0001 the model of the note reconciliation and of the actions is
    scripted from the persisted report, so it has a contradicted and a consistent note and actions that cite a
    portfolio-level finding; everything else uses the stub model.
    """
    import json
    from datetime import date

    from langchain_core.language_models.fake_chat_models import FakeListChatModel

    from rm_dashboard.agents import StubChatModel
    from rm_dashboard.reportsource import FolderReportSource, flatten
    from rm_dashboard.runners import open_registry, run_batch
    from rm_dashboard.runners.actions import run_actions
    from rm_dashboard.runners.outlook import run_outlook
    from rm_dashboard.runners.overview import run_overview
    from rm_dashboard.runners.reconcile import run_reconcile
    from rm_dashboard.settings import Settings

    out = tmp_path_factory.mktemp("api_run")
    as_of = date(2026, 8, 26)
    clients = ["CL-0001", "CL-0002", "CL-0003", "CL-0011"]

    def stub(role):
        return StubChatModel(role=role)

    def first(flat, pattern, portfolio=False):
        import re

        return next(f for f in flat if re.search(pattern, f.claim) and (("/" in f.report_path) == portfolio))

    with open_registry(Settings(db_path=str(seeded_db), max_concurrency=4)) as reg:
        run_outlook(reg, as_of=as_of, reports_dir=out, models=stub, instrument_ids=["SYN-EQ-0001", "SYN-CM-0401"])
        run_batch(reg, as_of=as_of, out_dir=out, client_ids=clients, models=stub)
        flat = flatten(FolderReportSource(out).report(as_of, "CL-0001"))
        kyc, conc, credit = (first(flat, r) for r in (r"KYC review is", r"largest single-name", r"LTV is"))
        pf_finding = next(f for f in flat if "/PF-0001" in f.report_path and f.evidence_ids)
        reconciliation = {"results": [
            {"note_id": "N-001", "verdict": "contradicted", "finding_refs": [conc.ref],
             "rationale": "The note says the client wants less energy exposure but the report still shows a single-name concentration."},
            {"note_id": "N-002", "verdict": "consistent", "finding_refs": [pf_finding.ref],
             "rationale": "The report findings for the portfolio support what the note says."}]}
        run_reconcile(reg, as_of=as_of, reports_dir=out, client_ids=["CL-0001"],
                      models=lambda role: FakeListChatModel(responses=[json.dumps(reconciliation)]))
        scripted = {"actions": [
            {"category": "compliance_kyc", "importance": "medium", "title": "Prepare the KYC review", "what": "Prepare the periodic review.",
             "why": "The report shows the review date.", "refs": [kyc.ref]},
            {"category": "concentration_risk", "importance": "high", "title": "Discuss the concentration", "what": "Review the exposure.",
             "why": "The report shows a concentrated name.", "refs": [conc.ref]},
            {"category": "mandate_drift", "importance": "high", "title": "Check the portfolio", "what": "Review the portfolio finding.",
             "why": "The portfolio report raises it.", "refs": [pf_finding.ref]},
            {"category": "credit_collateral", "importance": "medium", "title": "Review the credit facility", "what": "Review the headroom.",
             "why": "The report shows the facility.", "refs": [credit.ref]},
            {"category": "client_contact", "importance": "low", "title": "Follow up on note N-001", "what": "Discuss the difference.",
             "why": "The note and the book disagree.", "refs": ["N-001"]}]}
        run_actions(reg, as_of=as_of, reports_dir=out, client_ids=["CL-0001"],
                    models=lambda role: FakeListChatModel(responses=[json.dumps(scripted)]))
        run_actions(reg, as_of=as_of, reports_dir=out, client_ids=clients[1:], models=stub)
        run_overview(reg, as_of=as_of, reports_dir=out, models=stub)
    return out


@pytest.fixture(scope="session")
def api(seeded_db, api_reports):
    """The API on the seeded data and the run built by ``api_reports``."""
    from fastapi.testclient import TestClient

    from rm_dashboard.api import create_app

    return TestClient(create_app(seeded_db, api_reports))


@pytest.fixture(scope="session")
def reports_dir(api_reports) -> Path:
    return api_reports
