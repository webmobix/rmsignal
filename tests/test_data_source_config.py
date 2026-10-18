"""Choosing the source-data backend by configuration."""

import pytest
from fastapi.testclient import TestClient

from rm_dashboard.api import create_app
from rm_dashboard.api.serve import main as serve_main
from rm_dashboard.data.datasource import SqliteDataSource
from rm_dashboard.data.factory import open_data_source, parse_spec
from rm_dashboard.runners import open_registry
from rm_dashboard.settings import Settings


def test_the_data_source_defaults_to_the_database_setting():
    assert Settings.from_env({}).data_source_spec is None
    assert Settings.from_env({"RM_DASHBOARD_DB": "rm.db"}).data_source_spec == "sqlite:rm.db"
    s = Settings.from_env({"RM_DASHBOARD_DB": "rm.db", "RM_DATA_SOURCE": "firestore:demo"})
    assert s.data_source == "firestore:demo" and s.data_source_spec == "firestore:demo"


def test_specs_name_a_backend_and_a_bare_path_is_sqlite():
    assert parse_spec("sqlite:rm.db") == ("sqlite", "rm.db") and parse_spec("rm.db") == ("sqlite", "rm.db")
    assert parse_spec("/tmp/x/rm.db") == ("sqlite", "/tmp/x/rm.db") and parse_spec("firestore:demo/db") == ("firestore", "demo/db")


def test_unknown_backend_lists_the_valid_ones():
    with pytest.raises(ValueError, match="valid backends: sqlite, firestore"):
        parse_spec("oracle:x")


def test_the_factory_opens_sqlite(seeded_db):
    for spec in (str(seeded_db), f"sqlite:{seeded_db}"):
        with open_data_source(spec) as ds:
            assert isinstance(ds, SqliteDataSource) and len(ds.list_clients()) == 20


def test_a_missing_sqlite_file_names_the_seed_command(tmp_path):
    with pytest.raises(FileNotFoundError, match="rm-dashboard-seed"):
        open_data_source(f"sqlite:{tmp_path / 'nope.db'}")


def test_the_registry_follows_the_data_source_setting(seeded_db):
    with open_registry(Settings(data_source=f"sqlite:{seeded_db}"), with_peer=False) as reg:
        assert reg.ctx.repo.clients(as_of=__import__("datetime").date(2026, 8, 26)).frame.height == 20
    with pytest.raises(ValueError, match="no database given"):
        with open_registry(Settings(), with_peer=False):
            pass


def test_the_api_starts_on_a_data_source_spec_and_serves_sources(seeded_db, tmp_path):
    c = TestClient(create_app(f"sqlite:{seeded_db}", tmp_path))
    rows = c.get("/api/sources").json()
    assert len(rows) == 12 and {r["table"]: r["count"] for r in rows}["clients"] == 20
    assert c.get("/api/sources/clients/CL-0001").json()["client_id"] == "CL-0001"


def test_the_api_start_fails_early_for_a_bad_source(tmp_path):
    with pytest.raises(FileNotFoundError):
        create_app(tmp_path / "nope.db")
    with pytest.raises(ValueError, match="valid backends"):
        create_app("oracle:x")


def test_serve_reports_a_bad_data_source(tmp_path):
    with pytest.raises(SystemExit) as e:
        serve_main(["--data-source", "oracle:x"])
    assert "valid backends" in str(e.value)
