"""The artifact store contract, run against every backend, plus the evidence/audit helpers and the factory."""

import json
import sqlite3
import threading
from datetime import date

import pytest
from pydantic import BaseModel

from firestore_support import BACKENDS, new_store

from rm_dashboard.domain import Computation, ToolResult
from rm_dashboard.policy import AuditLog
from rm_dashboard.settings import Settings
from rm_dashboard.store import GLOBAL, Artifact, Kind, SqliteArtifactStore, open_store, read_model
from rm_dashboard.store.audit import StoreAuditSink, read_audit
from rm_dashboard.store.evidence import find_evidence, get_evidence, put_evidence

D1, D2 = date(2026, 6, 30), date(2026, 8, 26)


@pytest.fixture(params=BACKENDS)
def store(request, tmp_path):
    return new_store(request.param, tmp_path)


def result(n: int, size: int = 10) -> ToolResult:
    return ToolResult(data={"n": n, "pad": "x" * size}, as_of=D2, computation=Computation(tool="t", version="1"))


# ---- contract ----------------------------------------------------------------------------------
def test_save_and_read_back(store):
    store.put(D2, Kind.REPORT, "CL-0001", '{"a": 1}')
    assert store.get(D2, Kind.REPORT, "CL-0001") == '{"a": 1}'


def test_replace(store):
    store.put(D2, Kind.REPORT, "CL-0001", "one")
    store.put(D2, Kind.REPORT, "CL-0001", "two")
    assert store.get(D2, Kind.REPORT, "CL-0001") == "two" and store.keys(D2, Kind.REPORT) == ["CL-0001"]


def test_missing_is_not_found_not_an_error(store):
    assert store.get(D2, Kind.REPORT, "CL-9999") is None
    store.put(D2, Kind.REPORT, "CL-0001", "x")
    assert store.get(D1, Kind.REPORT, "CL-0001") is None and store.get(D2, Kind.ACTIONS, "CL-0001") is None


def test_keys_are_listed_in_ascending_order_under_a_prefix(store):
    for k in ("b/2", "a/1", "b/1", "c"):
        store.put(D2, Kind.SCENARIO_IMPACT, k, "x")
    assert store.keys(D2, Kind.SCENARIO_IMPACT) == ["a/1", "b/1", "b/2", "c"]
    assert store.keys(D2, Kind.SCENARIO_IMPACT, "b/") == ["b/1", "b/2"]
    assert store.keys(D2, Kind.SCENARIO_IMPACT, "zzz") == []


def test_dates_oldest_first_and_global_artifacts_have_none(store):
    store.put(D2, Kind.REPORT, "CL-0001", "x")
    store.put(D1, Kind.REPORT, "CL-0001", "x")
    store.put(GLOBAL, Kind.SCENARIO_CATALOGUE, "catalogue", "x")
    assert store.dates() == [D1, D2]


def test_other_dates_untouched(store):
    store.put(D1, Kind.REPORT, "CL-0001", "old")
    store.put(D2, Kind.REPORT, "CL-0001", "new")
    store.delete_prefix(D2, Kind.REPORT)
    assert store.get(D1, Kind.REPORT, "CL-0001") == "old" and store.get(D2, Kind.REPORT, "CL-0001") is None


def test_delete_prefix_counts_and_keeps_the_rest(store):
    for k in ("x/1", "x/2", "y/1"):
        store.put(D2, Kind.AUDIT, k, "x")
    assert store.delete_prefix(D2, Kind.AUDIT, "x/") == 2 and store.keys(D2, Kind.AUDIT) == ["y/1"]


def test_get_many_returns_only_what_exists(store):
    store.put_many([Artifact(D2, Kind.EVIDENCE, f"ev_{i}", str(i)) for i in range(3)])
    assert store.get_many(D2, Kind.EVIDENCE, ["ev_0", "ev_2", "ev_9"]) == {"ev_0": "0", "ev_2": "2"}


def test_interrupted_save_leaves_the_previous_body(tmp_path):
    s = SqliteArtifactStore(tmp_path / "artifacts.db")
    s.put(D2, Kind.REPORT, "CL-0001", "before")
    broken = [Artifact(D2, Kind.REPORT, "CL-0001", "half"), Artifact(D2, Kind.REPORT, "CL-0002", object())]  # fails mid-batch
    with pytest.raises(Exception):
        s.put_many(broken)
    assert s.get(D2, Kind.REPORT, "CL-0001") == "before" and s.get(D2, Kind.REPORT, "CL-0002") is None
    fresh = SqliteArtifactStore(tmp_path / "other.db")
    with pytest.raises(Exception):
        fresh.put_many(broken)
    assert fresh.get(D2, Kind.REPORT, "CL-0001") is None


def test_threads_can_share_a_store(store):
    errors = []

    def work(i):
        try:
            for j in range(20):
                store.put(D2, Kind.AUDIT, f"s/{i:02d}{j:02d}", "x")
                store.keys(D2, Kind.AUDIT)
        except Exception as e:  # noqa: BLE001 - reported below; a thread's exception would otherwise vanish
            errors.append(e)

    threads = [threading.Thread(target=work, args=(i,)) for i in range(8)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert not errors and len(store.keys(D2, Kind.AUDIT)) == 160


# ---- SQLite specifics ----------------------------------------------------------------------------
def test_reading_does_not_create_the_file(tmp_path):
    s = SqliteArtifactStore(tmp_path / "sub" / "artifacts.db")
    assert s.get(D2, Kind.REPORT, "x") is None and s.keys(D2, Kind.REPORT) == [] and s.dates() == []
    assert s.delete_prefix(D2, Kind.REPORT) == 0
    assert not (tmp_path / "sub").exists()


def test_created_on_first_write(tmp_path):
    s = SqliteArtifactStore(tmp_path / "sub" / "artifacts.db")
    s.put(D2, Kind.REPORT, "x", "y")
    assert (tmp_path / "sub" / "artifacts.db").is_file() and s.get(D2, Kind.REPORT, "x") == "y"


def test_a_database_file_without_the_table_reads_as_empty(tmp_path):
    sqlite3.connect(tmp_path / "artifacts.db").close()
    assert SqliteArtifactStore(tmp_path / "artifacts.db").dates() == []


# ---- typed reads -----------------------------------------------------------------------------------
class Thing(BaseModel):
    n: int


def test_unparseable_body_counts_as_absent(store):
    store.put(D2, Kind.SCENARIO_IMPACT, "ok", '{"n": 1}')
    store.put(D2, Kind.SCENARIO_IMPACT, "stale", '{"n": "not a number"}')
    store.put(D2, Kind.SCENARIO_IMPACT, "junk", "not json")
    assert read_model(store, D2, Kind.SCENARIO_IMPACT, "ok", Thing) == Thing(n=1)
    assert read_model(store, D2, Kind.SCENARIO_IMPACT, "stale", Thing) is None
    assert read_model(store, D2, Kind.SCENARIO_IMPACT, "junk", Thing) is None
    assert read_model(store, D2, Kind.SCENARIO_IMPACT, "missing", Thing) is None


# ---- evidence ----------------------------------------------------------------------------------------
def test_subject_evidence_keeps_its_order(store):
    rs = [result(3), result(1), result(2)]
    put_evidence(store, D2, "report", "CL-0001", rs)
    assert get_evidence(store, D2, "report", "CL-0001") == rs
    assert get_evidence(store, D2, "report", "CL-9999") is None


def test_any_result_is_found_by_id_alone(store):
    a, b = result(1), result(2)
    put_evidence(store, D2, "report", "CL-0001", [a])
    put_evidence(store, D2, "outlook-market", "market", [b])
    assert find_evidence(store, D2, a.evidence_id) == a and find_evidence(store, D2, b.evidence_id) == b
    assert find_evidence(store, D2, "ev_missing") is None and find_evidence(store, D1, a.evidence_id) is None


def test_a_shared_result_is_stored_once(store):
    shared = result(1)
    put_evidence(store, D2, "report", "CL-0001", [shared, result(2)])
    put_evidence(store, D2, "report", "CL-0002", [shared])
    assert len(store.keys(D2, Kind.EVIDENCE)) == 2
    assert get_evidence(store, D2, "report", "CL-0002") == [shared]


def test_a_result_repeated_within_a_subject_keeps_its_place(store):
    a, b = result(1), result(2)
    put_evidence(store, D2, "report", "CL-0001", [a, b, a])
    assert get_evidence(store, D2, "report", "CL-0001") == [a, b, a]


def test_evidence_over_one_mebibyte_round_trips(store):
    rs = [result(i, size=150_000) for i in range(8)]
    assert sum(len(r.model_dump_json()) for r in rs) > 1 << 20
    put_evidence(store, D2, "report", "CL-0017", rs)
    assert get_evidence(store, D2, "report", "CL-0017") == rs
    assert max(len(b) for b in store.get_many(D2, Kind.EVIDENCE, store.keys(D2, Kind.EVIDENCE)).values()) < 1 << 20


# ---- audit -------------------------------------------------------------------------------------------
def test_audit_is_read_back_in_sequence_order(store):
    log = AuditLog(sink=StoreAuditSink(store, D2, "batch"))
    for i in range(12):
        log.append(run_id="r", kind="decision", agent="a", subject=f"s{i}", as_of="2026-08-26", input_hash="h")
    assert [r["seq"] for r in read_audit(store, D2, "batch")] == list(range(1, 13))
    assert store.keys(D2, Kind.AUDIT)[0] == "batch/00000001"


def test_audit_can_continue_an_earlier_run_or_replace_it(store):
    def run(**kw):
        sink = StoreAuditSink(store, D2, "outlook", **kw)
        log = AuditLog(sink=sink, start_seq=sink.last_seq)
        log.append(run_id="r", kind="decision", agent="a", subject="s", as_of="2026-08-26", input_hash="h")
        log.append(run_id="r", kind="decision", agent="a", subject="s", as_of="2026-08-26", input_hash="h")

    run()
    run()
    assert [r["seq"] for r in read_audit(store, D2, "outlook")] == [1, 2, 3, 4]
    run(replace=True)
    assert [r["seq"] for r in read_audit(store, D2, "outlook")] == [1, 2]


def test_audit_stages_do_not_mix(store):
    for stage in ("batch", "actions"):
        AuditLog(sink=StoreAuditSink(store, D2, stage)).append(run_id="r", kind="decision", agent=stage, subject="s", as_of="x", input_hash="h")
    assert [r["agent"] for r in read_audit(store, D2, "actions")] == ["actions"]


# ---- factory and settings -------------------------------------------------------------------------------
def test_sqlite_locations(tmp_path):
    assert open_store(f"sqlite:{tmp_path}/a.db").location == f"{tmp_path}/a.db"
    assert open_store(f"sqlite:{tmp_path}").location == f"{tmp_path}/artifacts.db"
    assert open_store(tmp_path).location == f"{tmp_path}/artifacts.db"  # the --reports-dir compatibility form
    assert open_store(None).location.endswith("reports/artifacts.db")


def test_unknown_backend_lists_the_valid_ones():
    with pytest.raises(ValueError, match="valid backends: sqlite, firestore"):
        open_store("mongodb:foo")


def test_settings_read_the_store_from_the_environment():
    assert Settings.from_env({}).artifact_store == "sqlite:reports/artifacts.db"
    assert Settings.from_env({"RM_ARTIFACT_STORE": "firestore:demo"}).artifact_store == "firestore:demo"
