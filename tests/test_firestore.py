"""The Firestore backends, against the in-memory fake (and an emulator when one is configured)."""

import sqlite3
import sys
from datetime import date

import pytest
from firestore_support import BACKENDS, LoaderArtifactStore, new_client, new_store, patched_client
from storehelp import snapshot

from rm_dashboard.data import seed
from rm_dashboard.data.datasource import SqliteDataSource
from rm_dashboard.data.firestore import FirestoreDataSource
from rm_dashboard.data.schema import ENTITIES
from rm_dashboard.loader import LoadError, copy_artifacts, load_source, open_artifact_source
from rm_dashboard.loader.cli import main as load_main
from rm_dashboard.loader.firestore import load_source_to_firestore
from rm_dashboard.store import GLOBAL, Kind, ReadOnlyStore, SqliteArtifactStore, as_store, open_store
from rm_dashboard.store.firestore import READ_ONLY, FirestoreArtifactStore, doc_id

D = date(2026, 8, 26)
FIRESTORE = [b for b in BACKENDS if b != "sqlite"]


# ---- optional dependency -------------------------------------------------------------------------------------------
@pytest.fixture
def no_firestore_library(monkeypatch):
    monkeypatch.setitem(sys.modules, "google.cloud.firestore", None)  # an import now raises ImportError


def test_without_the_client_library_every_firestore_entry_point_names_the_extra(no_firestore_library, tmp_path, capsys):
    from rm_dashboard.api.serve import main as serve_main
    from rm_dashboard.data.factory import open_data_source

    for call in (lambda: open_store("firestore:demo"), lambda: open_data_source("firestore:demo"),
                 lambda: load_source(target="firestore:demo"), lambda: open_artifact_source("firestore:demo")):
        with pytest.raises(ImportError, match=r"uv sync --extra firestore"):
            call()
    with pytest.raises(SystemExit) as e:
        serve_main(["--data-source", "firestore:demo", "--artifact-store", f"sqlite:{tmp_path}"])
    assert "extra firestore" in str(e.value)
    assert load_main(["artifacts", "--from", f"sqlite:{tmp_path}", "--to", "firestore:demo"]) == 1
    assert "extra firestore" in capsys.readouterr().err


def test_the_sqlite_backends_work_without_the_library(no_firestore_library, tmp_path, seeded_db):
    store = SqliteArtifactStore(tmp_path / "a.db")
    store.put(D, Kind.REPORT, "CL-0001", "x")
    assert store.get(D, Kind.REPORT, "CL-0001") == "x"
    with SqliteDataSource(seeded_db) as ds:
        assert len(ds.list_clients()) == 20


def test_the_location_syntax_is_checked():
    from rm_dashboard.firestore_client import parse_location

    assert parse_location("demo") == ("demo", "(default)") and parse_location("demo/rm") == ("demo", "rm") and parse_location("") == (None, "(default)")
    with pytest.raises(ValueError, match="firestore:<project>"):
        parse_location("bad name/db")


# ---- source data -----------------------------------------------------------------------------------------------------
@pytest.fixture(scope="module")
def loaded():
    client = new_client(FIRESTORE[-1])
    with patched_client(client):
        counts = load_source_to_firestore(seed.DEFAULT_DATA_DIR, "demo")
    return client, counts


def test_every_table_reads_back_equal_and_in_the_same_order(loaded, seeded_db):
    client, counts = loaded
    assert counts["holdings"] == 1015 and counts["mandates"] == 48
    with SqliteDataSource(seeded_db) as sql:
        fs = FirestoreDataSource(client)
        for e in ENTITIES:
            assert fs.select(e.table) == sql.select(e.table), e.table
            assert fs.count(e.table) == sql.count(e.table) == counts[e.table]


def test_documents_use_the_primary_key_or_the_file_position_as_id(loaded):
    client, _ = loaded
    assert client.collection("clients").document("CL-0001").get().exists
    assert client.collection("holdings").document("row-000001").get().exists and client.collection("holdings").document("row-001015").get().exists
    mandate_ids = [d.id for d in client.collection("mandates").stream()]
    assert len(mandate_ids) == len(set(mandate_ids)) == 48 and all("|" in i for i in mandate_ids)


def test_a_row_value_keeps_its_type_in_the_document(loaded):
    client, _ = loaded
    doc = client.collection("clients").document("CL-0001").get().to_dict()
    assert doc["kyc_review_due"] == "2026-11-30" and doc["pep_status"] is False and doc["_seq"] >= 1
    assert any(d.to_dict()["age"] is None for d in client.collection("clients").stream())


def test_loading_again_is_refused_until_replace_and_replace_leaves_exactly_the_files(seeded_db):
    client = new_client(FIRESTORE[-1])
    with patched_client(client):
        load_source_to_firestore(seed.DEFAULT_DATA_DIR, "demo")
        client.collection("clients").document("CL-STRAY").set({"client_id": "CL-STRAY", "_seq": 99})
        with pytest.raises(LoadError, match="--replace"):
            load_source(target="firestore:demo")
        assert client.collection("clients").document("CL-STRAY").get().exists  # refused: nothing changed
        load_source(target="firestore:demo", replace=True)
    assert not client.collection("clients").document("CL-STRAY").get().exists
    with SqliteDataSource(seeded_db) as sql:
        assert FirestoreDataSource(client).select("clients") == sql.select("clients")


def test_a_bad_file_writes_nothing_to_firestore(data_copy):
    (data_copy / "holdings.csv").unlink()
    client = new_client(FIRESTORE[-1])
    with patched_client(client), pytest.raises(LoadError, match="holdings.csv"):
        load_source(data_copy, "firestore:demo")
    assert not list(client.collection("clients").stream()) and not list(client.collection("_meta").stream())


def test_a_failed_load_is_completed_by_running_it_again():
    client = new_client(FIRESTORE[-1])
    real_batch = client.batch
    state = {"n": 0}

    def flaky():
        batch = real_batch()
        commit = batch.commit

        def failing():
            state["n"] += 1
            if state["n"] == 4:
                raise ConnectionError("network down")
            return commit()

        batch.commit = failing
        return batch

    client.batch = flaky
    with patched_client(client):
        with pytest.raises(LoadError, match="run the same command again"):
            load_source(target="firestore:demo")
        assert client.collection("clients").document("CL-0001").get().exists and not client.collection("_meta").document("source").get().exists
        load_source(target="firestore:demo")  # no --replace needed: the marker is only written when everything is in
        assert client.collection("_meta").document("source").get().exists
        assert sum(1 for _ in client.collection("holdings").stream()) == 1015


def test_the_cli_prints_counts_for_a_firestore_target(capsys):
    client = new_client(FIRESTORE[-1])
    with patched_client(client):
        assert load_main(["source", "--to", "firestore:demo"]) == 0
    out = capsys.readouterr().out
    assert "clients" in out and "1015 rows" in out


# ---- artifacts -------------------------------------------------------------------------------------------------------
@pytest.fixture(scope="module")
def full_store(scenario_reports):
    return as_store(scenario_reports)


@pytest.mark.parametrize("backend", FIRESTORE)
def test_artifacts_copied_to_firestore_read_the_same_through_either_store(full_store, tmp_path, backend):
    target = new_store(backend, tmp_path)
    copy_artifacts(open_artifact_source(f"sqlite:{full_store.location}"), target)
    assert snapshot(target) == snapshot(full_store)
    assert target.dates() == full_store.dates()
    for kind in Kind:
        assert target.keys(D, kind) == full_store.keys(D, kind)
        assert target.keys(D, kind, "CL-0001") == full_store.keys(D, kind, "CL-0001")


def test_a_copy_to_firestore_can_be_repeated_limited_to_a_date_and_replaced(full_store, tmp_path):
    target = new_store(FIRESTORE[-1], tmp_path)
    other = date(2026, 6, 30)
    target.put(other, Kind.REPORT, "CL-0001", "keep")
    target.mark_run(other)
    source = open_artifact_source(full_store.location)
    copy_artifacts(source, target, dates=[D])
    first = snapshot(target)
    copy_artifacts(source, target, dates=[D])
    assert snapshot(target) == first and target.get(other, Kind.REPORT, "CL-0001") == "keep"
    target.put(D, Kind.REPORT, "CL-9999", "leftover")
    copy_artifacts(source, target, dates=[D], replace=True)
    assert target.get(D, Kind.REPORT, "CL-9999") is None and target.dates() == [other, D]


def test_a_reports_folder_can_be_published_straight_to_firestore(full_store, tmp_path):
    from storehelp import export_folder

    export_folder(full_store, tmp_path / "reports")
    target = new_store(FIRESTORE[-1], tmp_path)
    copy_artifacts(open_artifact_source(tmp_path / "reports"), target)
    assert snapshot(target) == snapshot(full_store)


def test_commits_stay_under_the_firestore_operation_limit(full_store, tmp_path):
    target = new_store("firestore", tmp_path)  # the fake raises on more than 500 operations in a commit
    copy_artifacts(open_artifact_source(full_store.location), target)
    assert target.client.commits >= len(snapshot(target)) // 400


def test_keys_with_separators_round_trip(tmp_path):
    store = new_store(FIRESTORE[-1], tmp_path)
    keys = ["rates-higher-for-longer/PF-0001", "a%b", "100%/x", "plain", "pipe|key"]
    for k in keys:
        store.put(D, Kind.SCENARIO_IMPACT, k, f"body {k}")
    assert store.keys(D, Kind.SCENARIO_IMPACT) == sorted(keys)
    assert store.keys(D, Kind.SCENARIO_IMPACT, "rates-higher-for-longer/") == ["rates-higher-for-longer/PF-0001"]
    assert store.keys(D, Kind.SCENARIO_IMPACT, "100%") == ["100%/x"]
    assert all(store.get(D, Kind.SCENARIO_IMPACT, k) == f"body {k}" for k in keys)
    assert "/" not in doc_id(D, Kind.SCENARIO_IMPACT, keys[0]).split("|", 2)[2]


def test_the_order_of_keys_is_the_one_sqlite_gives(tmp_path):
    fs, sql = new_store("firestore", tmp_path), new_store("sqlite", tmp_path)
    for k in ["p-x", "p/1", "p-1", "p%1", "P", "p"]:
        fs.put(D, Kind.SCENARIO_IMPACT, k, "x")
        sql.put(D, Kind.SCENARIO_IMPACT, k, "x")
    assert fs.keys(D, Kind.SCENARIO_IMPACT) == sql.keys(D, Kind.SCENARIO_IMPACT)


def test_dates_come_from_the_runs_markers(tmp_path):
    store = new_store(FIRESTORE[-1], tmp_path)
    store.put(date(2026, 8, 26), Kind.REPORT, "a", "x")
    store.put(date(2026, 6, 30), Kind.REPORT, "a", "x")
    assert store.dates() == [date(2026, 6, 30), date(2026, 8, 26)]
    store.put(GLOBAL, Kind.SCENARIO_CATALOGUE, "catalogue", "x")
    assert store.dates() == [date(2026, 6, 30), date(2026, 8, 26)]


# ---- read-only for runners ------------------------------------------------------------------------------------------------
@pytest.fixture
def read_only():
    client = new_client(FIRESTORE[-1])
    return FirestoreArtifactStore(client, writable=False), client


def test_saving_or_deleting_is_refused_naming_the_loader_and_changes_nothing(read_only):
    store, client = read_only
    seeded = FirestoreArtifactStore(client, writable=True)
    seeded.put(D, Kind.REPORT, "CL-0001", "kept")
    before = {k: dict(v) for k, v in getattr(client, "data", {}).items()}
    for call in (lambda: store.put(D, Kind.REPORT, "CL-0001", "new"), lambda: store.put_many([]), lambda: store.delete_prefix(D, Kind.REPORT),
                 lambda: store.mark_run(D)):
        with pytest.raises(ReadOnlyStore, match="rm-dashboard-load") as e:
            call()
        assert str(e.value) == READ_ONLY
    assert store.get(D, Kind.REPORT, "CL-0001") == "kept"
    assert before == {k: dict(v) for k, v in getattr(client, "data", {}).items()}


def test_a_runner_pointed_at_firestore_fails_before_any_model_call(seeded_db, capsys, monkeypatch):
    from rm_dashboard.agents import StubChatModel
    from rm_dashboard.runners import open_registry
    from rm_dashboard.runners.reconcile import main, run_reconcile
    from rm_dashboard.settings import Settings

    made = []

    def models(role):
        made.append(role)
        return StubChatModel(role=role)

    client = new_client(FIRESTORE[-1])
    with patched_client(client):
        with open_registry(Settings(db_path=str(seeded_db)), with_peer=False) as reg:
            with pytest.raises(ReadOnlyStore, match="rm-dashboard-load"):
                run_reconcile(reg, as_of=D, store=open_store("firestore:demo"), client_ids=["CL-0001"], models=models)
        monkeypatch.delenv("RM_DASHBOARD_DB", raising=False)
        assert main(["--as-of", "2026-08-26", "--db", str(seeded_db), "--artifact-store", "firestore:demo"]) == 2
    err = capsys.readouterr().err
    assert made == [] and "rm-dashboard-load" in err


def test_the_api_reads_artifacts_and_source_data_from_firestore_like_from_sqlite(seeded_db, scenario_reports, tmp_path):
    from fastapi.testclient import TestClient

    from rm_dashboard.api import create_app

    client = new_client(FIRESTORE[-1])
    with patched_client(client):
        load_source_to_firestore(seed.DEFAULT_DATA_DIR, "demo")
        target = LoaderArtifactStore(client, writable=True)
        copy_artifacts(open_artifact_source(str(scenario_reports)), target)
        local = TestClient(create_app(seeded_db, scenario_reports))
        remote = TestClient(create_app("firestore:demo", "firestore:demo"))
        for path in ("/api/as-of", "/api/overview", "/api/clients", "/api/market-outlook", "/api/sources/clients/CL-0001", "/api/scenarios"):
            a, b = local.get(path), remote.get(path)
            assert a.status_code == b.status_code == 200, path
            assert a.json() == b.json(), path
        ev = next(e for act in local.get("/api/overview").json()["actions"] for r in act["refs"] for e in r["evidence_ids"])
        assert remote.get(f"/api/evidence/{ev}").json() == local.get(f"/api/evidence/{ev}").json()


def test_serve_picks_both_backends_from_the_environment(seeded_db, scenario_reports, monkeypatch):
    """The documented demo: publish with the loader, then start the server with only RM_DATA_SOURCE and RM_ARTIFACT_STORE set."""
    import uvicorn
    from fastapi.testclient import TestClient

    from rm_dashboard.api import create_app
    from rm_dashboard.api.serve import main as serve_main

    client = new_client(FIRESTORE[-1])
    served = {}
    with patched_client(client):
        monkeypatch.delenv("RM_DASHBOARD_DB", raising=False)
        assert load_main(["source", "--to", "firestore:demo"]) == 0
        assert load_main(["artifacts", "--from", str(scenario_reports), "--to", "firestore:demo"]) == 0
        monkeypatch.setenv("RM_DATA_SOURCE", "firestore:demo")
        monkeypatch.setenv("RM_ARTIFACT_STORE", "firestore:demo")
        monkeypatch.setattr(uvicorn, "run", lambda app, **kw: served.update(app=app, **kw))
        serve_main([])
        remote = TestClient(served["app"])
        local = TestClient(create_app(seeded_db, scenario_reports))
        assert remote.get("/api/overview").json() == local.get("/api/overview").json()
        assert remote.get("/api/overview").json()["actions"]
