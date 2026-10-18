"""``rm-dashboard-load``: source data and artifacts into SQLite."""

import shutil
import sqlite3
from datetime import date
from pathlib import Path

import pytest
from storehelp import export_folder, snapshot

from rm_dashboard.data import seed
from rm_dashboard.loader import LoadError, copy_artifacts, load_source, open_artifact_source
from rm_dashboard.loader.cli import main
from rm_dashboard.store import GLOBAL, Kind, SqliteArtifactStore, as_store
from rm_dashboard.store.folder import FolderArtifactSource

D = date(2026, 8, 26)
TABLES = ("clients", "portfolios", "holdings", "instruments", "mandates", "transactions", "credit_facilities", "commitments",
          "planned_cash_needs", "market_context", "event_log", "rm_notes")


def dump(db) -> dict:
    conn = sqlite3.connect(db)
    try:
        return {t: conn.execute(f'SELECT * FROM "{t}" ORDER BY rowid').fetchall() for t in TABLES}
    finally:
        conn.close()


# ---- source data ----------------------------------------------------------------------------------
def test_loading_the_sample_data_equals_what_the_seed_command_makes(tmp_path):
    seeded = tmp_path / "seed.db"
    seed.seed(seeded)
    counts = load_source(target=f"sqlite:{tmp_path / 'load.db'}")
    assert counts["clients"] == 20 and counts["holdings"] == 1015
    assert dump(tmp_path / "load.db") == dump(seeded)


def test_the_cli_prints_the_counts(tmp_path, capsys):
    assert main(["source", "--to", str(tmp_path / "x.db")]) == 0
    out = capsys.readouterr().out
    assert "clients" in out and "1015 rows" in out


def test_a_second_load_is_refused_and_replace_gives_the_same_contents(tmp_path, capsys):
    target = f"sqlite:{tmp_path / 'rm.db'}"
    load_source(target=target)
    before = dump(tmp_path / "rm.db")
    with pytest.raises(LoadError, match="--replace"):
        load_source(target=target)
    assert main(["source", "--to", target]) == 1 and "--replace" in capsys.readouterr().err
    assert dump(tmp_path / "rm.db") == before
    load_source(target=target, replace=True)
    assert dump(tmp_path / "rm.db") == before


@pytest.mark.parametrize("old, new", [("46571821.48", "abc"), ("2026-11-30", "31/12/2026")])
def test_a_bad_cell_names_file_row_and_column_like_the_seed_command(data_copy, tmp_path, old, new, capsys):
    p = data_copy / "clients.csv"
    p.write_text(p.read_text(encoding="utf-8").replace(old, new, 1), encoding="utf-8")
    assert seed.main(["--db", str(tmp_path / "seed.db"), "--data-dir", str(data_copy)]) == 1
    seed_err = capsys.readouterr().err
    assert main(["source", "--data-dir", str(data_copy), "--to", str(tmp_path / "load.db")]) == 1
    load_err = capsys.readouterr().err
    assert seed_err == load_err and "clients.csv: row 1, column" in load_err
    assert not (tmp_path / "load.db").exists() and not (tmp_path / "seed.db").exists()  # nothing was written


def test_a_missing_file_leaves_the_target_unchanged(data_copy, tmp_path):
    (data_copy / "holdings.csv").unlink()
    with pytest.raises(LoadError, match="holdings.csv"):
        load_source(data_copy, tmp_path / "rm.db")
    assert not (tmp_path / "rm.db").exists()
    load_source(target=tmp_path / "rm.db")
    before = dump(tmp_path / "rm.db")
    with pytest.raises(LoadError, match="holdings.csv"):
        load_source(data_copy, tmp_path / "rm.db", replace=True)
    assert dump(tmp_path / "rm.db") == before


def test_a_repeated_key_is_rejected_with_the_database_message(data_copy, tmp_path):
    p = data_copy / "mandates.csv"
    lines = p.read_text(encoding="utf-8").splitlines()
    p.write_text("\n".join([*lines, lines[1]]) + "\n", encoding="utf-8")
    with pytest.raises(LoadError, match=r"mandates.csv: UNIQUE constraint failed: mandates.mandate_code, mandates.asset_class"):
        load_source(data_copy, tmp_path / "rm.db")


def test_an_unknown_target_backend_is_named(tmp_path):
    with pytest.raises(LoadError, match="valid backends: sqlite, firestore"):
        load_source(target="oracle:x")


# ---- artifacts --------------------------------------------------------------------------------------
@pytest.fixture(scope="module")
def full_store(scenario_reports):
    """Every kind of artifact: a run of all stages for 2026-08-26 and a scenario result."""
    return as_store(scenario_reports)


def test_a_store_copy_has_every_address_with_an_equal_body(full_store, tmp_path):
    target = SqliteArtifactStore(tmp_path / "copy.db")
    counts = copy_artifacts(open_artifact_source(f"sqlite:{full_store.location}"), target)
    assert snapshot(full_store) == snapshot(target)
    assert counts[str(Kind.REPORT)] == 4 and counts[str(Kind.SCENARIO_VECTOR)] == 1 and sum(counts.values()) == len(snapshot(target))
    assert target.keys(GLOBAL, Kind.SCENARIO_CATALOGUE) == ["catalogue"]


def test_copying_twice_gives_the_same_artifacts(full_store, tmp_path):
    target = SqliteArtifactStore(tmp_path / "copy.db")
    source = open_artifact_source(full_store.location)
    copy_artifacts(source, target)
    first = snapshot(target)
    copy_artifacts(source, target)
    assert snapshot(target) == first


def test_one_date_only_writes_that_date_and_leaves_others(full_store, tmp_path):
    target = SqliteArtifactStore(tmp_path / "copy.db")
    other = date(2026, 6, 30)
    target.put(other, Kind.REPORT, "CL-0001", "keep")
    copy_artifacts(open_artifact_source(full_store.location), target, dates=[D])
    assert target.get(other, Kind.REPORT, "CL-0001") == "keep" and target.keys(D, Kind.REPORT)
    assert target.keys(GLOBAL, Kind.SCENARIO_CATALOGUE) == []  # the catalogue goes with a full copy, or on request
    copy_artifacts(open_artifact_source(full_store.location), target, dates=[D], catalogue=True)
    assert target.keys(GLOBAL, Kind.SCENARIO_CATALOGUE) == ["catalogue"]


def test_replace_removes_what_the_target_had_for_the_date(full_store, tmp_path):
    target = SqliteArtifactStore(tmp_path / "copy.db")
    target.put(D, Kind.REPORT, "CL-9999", "leftover")
    copy_artifacts(open_artifact_source(full_store.location), target, dates=[D], replace=True)
    assert target.get(D, Kind.REPORT, "CL-9999") is None and target.get(D, Kind.REPORT, "CL-0001")


def test_an_unknown_date_is_named(full_store, tmp_path):
    with pytest.raises(LoadError, match="2025-01-01"):
        copy_artifacts(open_artifact_source(full_store.location), SqliteArtifactStore(tmp_path / "c.db"), dates=[date(2025, 1, 1)])


def test_a_reports_folder_is_imported_re_chunked_and_reads_the_same(full_store, tmp_path):
    folder = tmp_path / "reports"
    export_folder(full_store, folder)
    assert (folder / D.isoformat() / "evidence" / "CL-0001.json").stat().st_size > 1000 and not (folder / "artifacts.db").exists()
    source = open_artifact_source(folder)
    assert isinstance(source, FolderArtifactSource) and source.dates() == full_store.dates()
    target = SqliteArtifactStore(tmp_path / "imported.db")
    copy_artifacts(source, target)
    assert snapshot(target) == snapshot(full_store)


def test_the_cli_copies_artifacts_and_prints_counts(full_store, tmp_path, capsys):
    assert main(["artifacts", "--from", f"sqlite:{full_store.location}", "--to", f"sqlite:{tmp_path / 'c.db'}", "--as-of", "2026-08-26"]) == 0
    out = capsys.readouterr().out
    assert "report" in out and "artifacts written" in out
    assert main(["artifacts", "--from", str(tmp_path / "nope"), "--to", str(tmp_path / "c.db")]) == 1
    assert "not found" in capsys.readouterr().err


def test_a_folder_with_both_a_database_and_date_folders_is_ambiguous(full_store, tmp_path):
    export_folder(full_store, tmp_path)
    shutil.copy(full_store.location, tmp_path / "artifacts.db")
    with pytest.raises(LoadError, match="both"):
        open_artifact_source(tmp_path)
    assert isinstance(open_artifact_source(f"folder:{tmp_path}"), FolderArtifactSource)


def test_a_failure_after_writing_started_says_a_rerun_completes_it(full_store, tmp_path):
    class Flaky(SqliteArtifactStore):
        calls = 0

        def put_many(self, items):
            Flaky.calls += 1
            if Flaky.calls == 2:
                raise ConnectionError("network down")
            super().put_many(items)

    target = Flaky(tmp_path / "c.db")
    with pytest.raises(LoadError, match="run the same command again"):
        copy_artifacts(open_artifact_source(full_store.location), target)
    Flaky.calls = 5
    copy_artifacts(open_artifact_source(full_store.location), target)
    assert snapshot(target) == snapshot(full_store)


def test_the_repositorys_own_reports_folder_reads_the_same_through_the_facades(tmp_path):
    """The one-time import of an existing ``reports/`` folder (skipped on a checkout without one)."""
    reports = Path(__file__).parent.parent / "reports"
    if not (reports / "2026-08-26").is_dir():
        pytest.skip("no reports/ folder in this checkout")
    from rm_dashboard.domain import Report
    from rm_dashboard.outlook.store import OutlookStore
    from rm_dashboard.reportsource import StoreReportSource

    target = SqliteArtifactStore(tmp_path / "imported.db")
    copy_artifacts(open_artifact_source(reports), target)
    src, outlooks = StoreReportSource(target), OutlookStore(target)
    for p in sorted((reports / "2026-08-26").glob("CL-*.json")):
        assert src.report(D, p.stem) == Report.model_validate_json(p.read_text())
    assert outlooks.load_market(D).summary
