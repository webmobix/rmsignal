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
