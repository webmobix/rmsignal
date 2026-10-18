from datetime import date

import pytest

from rm_dashboard.agents import StubChatModel
from rm_dashboard.outlook import MarketOutlook
from rm_dashboard.outlook.store import OutlookStore
from rm_dashboard.runners import open_registry
from rm_dashboard.runners.outlook import main, run_outlook
from rm_dashboard.settings import Settings
from rm_dashboard.store import Kind
from rm_dashboard.store.audit import read_audit
from rm_dashboard.store.summary import get_summary

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
    return run_outlook(reg, as_of=as_of, store=tmp_path, models=models, **kw), models


# ---- 4.1 persistence ------------------------------------------------------------------------
def test_results_are_saved_under_the_date(reg, tmp_path):
    res, _ = run(reg, tmp_path)
    store = OutlookStore(tmp_path).store
    assert res.store.location == store.location and not [p for p in tmp_path.rglob("*.json")]  # one database, no per-artifact files
    assert store.keys(AS_OF, Kind.OUTLOOK_MARKET) == ["market"] and store.keys(AS_OF, Kind.RUN_SUMMARY) == ["outlook"]
    assert read_audit(store, AS_OF, "outlook")
    o = MarketOutlook.model_validate_json(store.get(AS_OF, Kind.OUTLOOK_MARKET, "market"))
    assert o == res.market
    s = get_summary(store, AS_OF, "outlook")
    assert s["as_of"] == "2026-08-26" and s["model"] == "stub" and s["market"]["views"] == 6 and s["market"]["status"] == "complete"


def test_every_cited_evidence_id_resolves_in_the_evidence(reg, tmp_path):
    res, _ = run(reg, tmp_path)
    ev = {r.evidence_id for r in OutlookStore(tmp_path).load_market_evidence(AS_OF)}
    cited = {i for v in res.market.views for r in (*v.drivers, *v.risks) for i in r.evidence_ids}
    assert cited and cited <= ev and set(res.market.evidence_ids) <= ev


def test_reference_chain_leaves_earlier_outlooks_untouched(reg, tmp_path):
    run(reg, tmp_path, as_of=date(2026, 6, 30))
    store = OutlookStore(tmp_path).store
    before = store.get(date(2026, 6, 30), Kind.OUTLOOK_MARKET, "market")
    second, _ = run(reg, tmp_path)
    assert store.get(date(2026, 6, 30), Kind.OUTLOOK_MARKET, "market") == before
    assert second.market.previous_as_of == date(2026, 6, 30) and not second.market.is_first
    assert OutlookStore(tmp_path).dates() == [date(2026, 6, 30), AS_OF]


def test_a_later_outlook_is_never_used_as_previous(reg, tmp_path):
    run(reg, tmp_path)
    early, _ = run(reg, tmp_path, as_of=date(2026, 3, 31))
    assert early.market.is_first and early.market.previous_as_of is None
    assert OutlookStore(tmp_path).load_market(AS_OF) is not None


def test_rerun_with_same_inputs_is_skipped_and_force_regenerates(reg, tmp_path):
    first, m1 = run(reg, tmp_path)
    store = OutlookStore(tmp_path).store
    body = store.get(AS_OF, Kind.OUTLOOK_MARKET, "market")
    audit = len(read_audit(store, AS_OF, "outlook"))
    again, m2 = run(reg, tmp_path)
    assert again.skipped and m2.calls == 0 and store.get(AS_OF, Kind.OUTLOOK_MARKET, "market") == body
    assert len(read_audit(store, AS_OF, "outlook")) == audit
    forced, m3 = run(reg, tmp_path, force=True)
    assert not forced.skipped and m3.calls > 0


def test_an_outlook_without_data_does_not_hide_the_history(reg, tmp_path):
    run(reg, tmp_path, as_of=date(2026, 6, 30))
    empty, _ = run(reg, tmp_path, as_of=date(2025, 12, 30))
    store = OutlookStore(tmp_path)
    assert empty.market.status == "insufficient_data" and store.load_market(date(2025, 12, 30)) is not None
    assert store.previous_market(before=date(2026, 8, 26)).as_of == date(2026, 6, 30)


# ---- 4.2 command line -----------------------------------------------------------------------
def test_cli_writes_the_market_outlook(seeded_db, tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("RM_DASHBOARD_DB", raising=False)
    assert main(["--as-of", "2026-08-26", "--db", str(seeded_db), "--reports-dir", str(tmp_path), "--instruments", "SYN-EQ-0001"]) == 0
    out = capsys.readouterr().out
    assert "market outlook written" in out and "6 views" in out and "first outlook" in out and "model: stub" in out
    assert OutlookStore(tmp_path).load_market(AS_OF) is not None
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
