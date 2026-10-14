import json
import sqlite3

import pytest

from rm_dashboard.data import seed
from rm_dashboard.data.seed import SeedError

COUNTS = {
    "clients": 20, "portfolios": 24, "holdings": 1015, "instruments": 62, "mandates": 48,
    "transactions": 393, "credit_facilities": 5, "commitments": 5, "planned_cash_needs": 20,
    "market_context": 115, "event_log": 16, "rm_notes": 28,
}


def count(db, table):
    with sqlite3.connect(db) as c:
        return c.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]


def test_seed_sample_dataset(tmp_path):
    db = tmp_path / "rm.db"
    assert seed.seed(db) == COUNTS
    assert {t: count(db, t) for t in COUNTS} == COUNTS


def test_null_and_value_preservation(seeded_db):
    with sqlite3.connect(seeded_db) as c:
        assert c.execute("SELECT COUNT(*) FROM clients WHERE age IS NULL").fetchone()[0] == 1
        assert c.execute("SELECT total_aum_usd FROM clients WHERE client_id='CL-0001'").fetchone()[0] == 46571821.48
        assert c.execute("SELECT kyc_review_due FROM clients WHERE client_id='CL-0001'").fetchone()[0] == "2026-11-30"
        assert c.execute("SELECT pep_status FROM clients WHERE client_id='CL-0001'").fetchone()[0] == 0
        assert c.execute("SELECT COUNT(*) FROM instruments WHERE underlying_reference IS NULL").fetchone()[0] == 53
        assert c.execute("SELECT COUNT(*) FROM instruments WHERE underlying_reference = ''").fetchone()[0] == 0


def test_cli_main(tmp_path, capsys):
    assert seed.main(["--db", str(tmp_path / "x.db")]) == 0
    assert "clients" in capsys.readouterr().out


def test_missing_file(data_copy, tmp_path):
    (data_copy / "holdings.csv").unlink()
    db = tmp_path / "rm.db"
    with pytest.raises(SeedError, match="holdings.csv"):
        seed.seed(db, data_copy)
    assert not db.exists()


def test_wrong_header(data_copy, tmp_path):
    p = data_copy / "clients.csv"
    p.write_text(p.read_text(encoding="utf-8").replace("client_id,", "id,", 1), encoding="utf-8")
    with pytest.raises(SeedError, match=r"clients.csv.*header"):
        seed.seed(tmp_path / "rm.db", data_copy)


@pytest.mark.parametrize(
    "old, new",
    [("46571821.48", "abc"), ("2026-11-30", "31/12/2026"), (",No,English", ",Maybe,English")],
)
def test_bad_cells_name_file_row_column(data_copy, tmp_path, old, new):
    p = data_copy / "clients.csv"
    text = p.read_text(encoding="utf-8")
    assert old in text
    p.write_text(text.replace(old, new, 1), encoding="utf-8")
    with pytest.raises(SeedError, match=r"clients.csv: row 1, column"):
        seed.seed(tmp_path / "rm.db", data_copy)


def test_reseed_refused_then_replace(tmp_path):
    db = tmp_path / "rm.db"
    seed.seed(db)
    with pytest.raises(SeedError, match="--replace"):
        seed.seed(db)
    assert seed.main(["--db", str(db)]) == 1
    assert count(db, "clients") == 20
    seed.seed(db, replace=True)
    assert {t: count(db, t) for t in COUNTS} == COUNTS


def test_failure_leaves_no_partial_data(data_copy, tmp_path):
    db = tmp_path / "rm.db"
    seed.seed(db, data_copy)
    notes = json.loads((data_copy / "rm_notes.json").read_text(encoding="utf-8"))
    notes[0]["note_date"] = "not-a-date"
    (data_copy / "rm_notes.json").write_text(json.dumps(notes), encoding="utf-8")
    with pytest.raises(SeedError, match="rm_notes.json"):
        seed.seed(db, data_copy, replace=True)
    assert {t: count(db, t) for t in COUNTS} == COUNTS  # old data intact


def test_duplicate_key_mid_load_rolls_back(data_copy, tmp_path):
    q = data_copy / "planned_cash_needs.csv"
    lines = q.read_text(encoding="utf-8").splitlines()
    q.write_text("\n".join(lines + [lines[1]]) + "\n", encoding="utf-8")
    db = tmp_path / "rm.db"
    with pytest.raises(SeedError, match="planned_cash_needs.csv"):
        seed.seed(db, data_copy)
    with sqlite3.connect(db) as c:
        assert c.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'").fetchone()[0] == 0
