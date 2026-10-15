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


@pytest.fixture
def make_scope(registry):
    """Factory for a fresh run scope on the seeded data."""
    from datetime import date

    from rm_dashboard.agents import RunScope
    from rm_dashboard.agents.scope import register_people
    from rm_dashboard.policy import RunContext, Pseudonymiser

    def make(as_of=date(2026, 8, 26), engine=None, subject="CL-0001", register_names=True):
        run = RunContext(subject, as_of, **({"engine": engine} if engine else {}))
        if register_names:
            register_people(run, registry.ctx.repo, date(2026, 12, 31))
        return RunScope(run=run, registry=registry)

    return make
