import json
from datetime import date

import pytest

from rm_dashboard.agents import StubChatModel
from rm_dashboard.domain import ToolResult
from rm_dashboard.outlook import MarketOutlook
from rm_dashboard.outlook.store import OutlookStore
from rm_dashboard.runners import open_registry
from rm_dashboard.runners.outlook import main, run_outlook
from rm_dashboard.settings import Settings

AS_OF = date(2026, 8, 26)


class Models:
    def __init__(self):
        self.made = []

    def __call__(self, role):
        m = StubChatModel(role=role)
        self.made.append(m)
        return m

    @property
    def calls(self):
        return sum(m.calls for m in self.made)


@pytest.fixture(scope="module")
def reg(seeded_db):
    with open_registry(Settings(db_path=str(seeded_db)), with_peer=False) as r:
        yield r


def run(reg, tmp_path, as_of=AS_OF, **kw):
    models = kw.pop("models", None) or Models()
    kw.setdefault("with_instruments", False)   # the market tests stay on the market; see test_outlook_stage.py
    return run_outlook(reg, as_of=as_of, reports_dir=tmp_path, models=models, **kw), models


# ---- 4.1 persistence ------------------------------------------------------------------------
def test_files_are_written_under_the_date(reg, tmp_path):
    res, _ = run(reg, tmp_path)
    d = tmp_path / "2026-08-26" / "outlook"
    assert res.out_dir == d
    for name in ("market.json", "evidence/market.json", "summary.json", "audit.jsonl"):
        assert (d / name).is_file(), name
    assert (d / "audit.jsonl").read_text().strip()
    o = MarketOutlook.model_validate_json((d / "market.json").read_text())
    assert o == res.market
    s = json.loads((d / "summary.json").read_text())
    assert s["as_of"] == "2026-08-26" and s["model"] == "stub" and s["market"]["views"] == 6 and s["market"]["status"] == "complete"


def test_every_cited_evidence_id_resolves_in_the_evidence_file(reg, tmp_path):
    res, _ = run(reg, tmp_path)
    ev = {ToolResult.model_validate(x).evidence_id for x in json.loads((res.out_dir / "evidence" / "market.json").read_text())}
    cited = {i for v in res.market.views for r in (*v.drivers, *v.risks) for i in r.evidence_ids}
    assert cited and cited <= ev and set(res.market.evidence_ids) <= ev


def test_reference_chain_leaves_earlier_outlooks_untouched(reg, tmp_path):
    first, _ = run(reg, tmp_path, as_of=date(2026, 6, 30))
    path = first.out_dir / "market.json"
    before = path.read_bytes()
    second, _ = run(reg, tmp_path)
    assert path.read_bytes() == before
    assert second.market.previous_as_of == date(2026, 6, 30) and not second.market.is_first
    assert OutlookStore(tmp_path).dates() == [date(2026, 6, 30), AS_OF]


def test_a_later_outlook_is_never_used_as_previous(reg, tmp_path):
    run(reg, tmp_path)
    early, _ = run(reg, tmp_path, as_of=date(2026, 3, 31))
    assert early.market.is_first and early.market.previous_as_of is None
    assert (tmp_path / "2026-08-26" / "outlook" / "market.json").is_file()


def test_rerun_with_same_inputs_is_skipped_and_force_regenerates(reg, tmp_path):
    first, m1 = run(reg, tmp_path)
    stamp = (first.out_dir / "market.json").stat().st_mtime_ns
    again, m2 = run(reg, tmp_path)
    assert again.skipped and m2.calls == 0 and (first.out_dir / "market.json").stat().st_mtime_ns == stamp
    forced, m3 = run(reg, tmp_path, force=True)
    assert not forced.skipped and m3.calls > 0


def test_an_outlook_without_data_does_not_hide_the_history(reg, tmp_path):
    run(reg, tmp_path, as_of=date(2026, 6, 30))
    empty, _ = run(reg, tmp_path, as_of=date(2025, 12, 30))
    assert empty.market.status == "insufficient_data" and (empty.out_dir / "market.json").is_file()
    store = OutlookStore(tmp_path)
    assert store.previous_market(before=date(2026, 8, 26)).as_of == date(2026, 6, 30)


# ---- 4.2 command line -----------------------------------------------------------------------
def test_cli_writes_the_market_outlook(seeded_db, tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("RM_DASHBOARD_DB", raising=False)
    assert main(["--as-of", "2026-08-26", "--db", str(seeded_db), "--reports-dir", str(tmp_path), "--instruments", "SYN-EQ-0001"]) == 0
    out = capsys.readouterr().out
    assert "market outlook written" in out and "6 views" in out and "first outlook" in out and "model: stub" in out
    assert (tmp_path / "2026-08-26" / "outlook" / "market.json").is_file()
    assert main(["--as-of", "2026-09-15", "--db", str(seeded_db), "--reports-dir", str(tmp_path), "--instruments", "SYN-EQ-0001"]) == 0
    assert "carried forward from 2026-08-26" in capsys.readouterr().out
    assert main(["--as-of", "2026-09-15", "--db", str(seeded_db), "--reports-dir", str(tmp_path), "--instruments", "SYN-EQ-0001"]) == 0
    assert "unchanged" in capsys.readouterr().out
    assert main(["--as-of", "2026-09-15", "--db", str(seeded_db), "--reports-dir", str(tmp_path), "--instruments", "SYN-EQ-0001", "--force"]) == 0
    assert "compared with 2026-08-26" in capsys.readouterr().out


def test_cli_requires_as_of_and_database(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("RM_DASHBOARD_DB", raising=False)
    with pytest.raises(SystemExit) as e:
        main(["--db", "x.db"])
    assert e.value.code == 2
    assert main(["--as-of", "2026-08-26"]) == 2
    assert main(["--as-of", "2026-08-26", "--db", str(tmp_path / "missing.db")]) == 2
    err = capsys.readouterr().err
    assert "no database given" in err and "database not found" in err
