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


REPORTS = Path(__file__).parent.parent / "reports"


@pytest.fixture(scope="session")
def api(seeded_db):
    """The API on the seeded data and the persisted run in ``reports/`` (skipped when there is none)."""
    from fastapi.testclient import TestClient

    from rm_dashboard.api import create_app

    if not (REPORTS / "2026-08-26").is_dir():
        pytest.skip("no persisted run in reports/")
    return TestClient(create_app(seeded_db, REPORTS))


@pytest.fixture(scope="session")
def reports_dir(api) -> Path:
    return REPORTS
