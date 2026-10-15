import dataclasses
import json
from datetime import date

import polars as pl
import pytest

from rm_dashboard.agents import StubChatModel
from rm_dashboard.agents.stub import StubModelError
from rm_dashboard.outlook import InstrumentOutlook, MarketOutlook
from rm_dashboard.outlook.inputs import held_instruments, instrument_inputs
from rm_dashboard.outlook.store import OutlookStore
from rm_dashboard.runners import open_registry
from rm_dashboard.runners.outlook import main, run_outlook
from rm_dashboard.settings import Settings
from rm_dashboard.tools import ToolRegistry

AS_OF = date(2026, 8, 26)


class Models:
    def __init__(self, fail_for=""):
        self.made, self.fail_for = [], fail_for

    def __call__(self, role):
        m = Flaky(role=role, fail_for=self.fail_for)
        self.made.append(m)
        return m

    @property
    def calls(self):
        return sum(m.calls for m in self.made)


class Flaky(StubChatModel):
    """The stub, failing for one instrument when asked to."""

    fail_for: str = ""

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        if self.fail_for and any(self.fail_for in str(m.content) for m in messages if m.type == "human"):
            raise StubModelError(f"model failure for {self.fail_for}")
        return super()._generate(messages, stop, run_manager, **kwargs)


@pytest.fixture(scope="module")
def reg(seeded_db):
    with open_registry(Settings(db_path=str(seeded_db), max_concurrency=4), with_peer=False) as r:
        yield r


class Trimmed:
    """The repository with fewer holdings, to see that only held instruments get an outlook."""

    def __init__(self, repo, keep):
        self._repo, self._keep = repo, keep

    def __getattr__(self, name):
        return getattr(self._repo, name)

    def holdings(self, **kw):
        r = self._repo.holdings(**kw)
        r.frame = r.frame.filter(pl.col("instrument_id").is_in(self._keep))
        return r


def stage(reg, tmp_path, as_of=AS_OF, models=None, **kw):
    models = models or Models()
    return run_outlook(reg, as_of=as_of, reports_dir=tmp_path, models=models, **kw), models


def files(d):
    return {str(p.relative_to(d)): p.read_bytes() for p in sorted(d.rglob("*")) if p.is_file()}


# ---- 3.1 which instruments --------------------------------------------------------------------
def test_held_instruments_are_the_union_of_all_portfolios(reg):
    held = held_instruments(reg.ctx.repo, AS_OF)
    f = reg.ctx.repo.holdings(as_of=AS_OF).frame
    assert held == sorted(set(f["instrument_id"].to_list())) and len(held) == 62
    assert f.filter(pl.col("instrument_id") == "SYN-EQ-0001")["portfolio_id"].n_unique() > 1


def test_only_held_instruments_get_an_outlook(reg, tmp_path):
    keep = ["SYN-EQ-0001", "SYN-CM-0401", "SYN-FI-0201"]
    trimmed = ToolRegistry(dataclasses.replace(reg.ctx, repo=Trimmed(reg.ctx.repo, keep)))
    res, _ = stage(trimmed, tmp_path)
    assert sorted(res.instruments) == sorted(keep)
    assert OutlookStore(tmp_path).instrument_ids(AS_OF) == sorted(keep)
    assert not (res.out_dir / "instruments" / "SYN-EQ-0003.json").exists()


def test_an_explicit_list_overrides_the_held_set(reg, tmp_path):
    res, models = stage(reg, tmp_path, instrument_ids=["SYN-ST-0102", "SYN-EQ-0003"])
    assert sorted(res.instruments) == ["SYN-EQ-0003", "SYN-ST-0102"] and models.calls == 6


# ---- 3.2 fingerprint, carry-forward, skip -------------------------------------------------------
def test_full_stage_writes_one_file_per_instrument(reg, tmp_path):
    res, models = stage(reg, tmp_path)
    d = res.out_dir
    assert len(res.instruments) == 62 and len(list((d / "instruments").glob("*.json"))) == 62
    assert len(list((d / "evidence" / "instruments").glob("*.json"))) == 62
    for iid, o in res.instruments.items():
        assert InstrumentOutlook.model_validate_json((d / "instruments" / f"{iid}.json").read_text()) == o
        assert o.subject == iid and o.status in ("complete", "partial") and o.view is not None
    s = json.loads((d / "summary.json").read_text())
    assert s["instruments"]["count"] == 62 and sum(s["instruments"]["status_counts"].values()) == 62
    assert set(s["instruments"]["detail"]) == set(res.instruments) and s["market"]["views"] == 6
    assert (d / "audit.jsonl").read_text().strip()


def test_rerun_with_the_same_inputs_calls_no_model_and_changes_nothing(reg, tmp_path):
    res, _ = stage(reg, tmp_path)
    before = files(res.out_dir)
    again, models = stage(reg, tmp_path)
    assert models.calls == 0 and again.untouched and len(again.instruments_skipped) == 62
    assert files(res.out_dir) == before


def test_two_portfolios_holding_the_instrument_give_one_outlook(reg, tmp_path):
    res, _ = stage(reg, tmp_path, instrument_ids=["SYN-EQ-0001"])
    assert [p.name for p in (res.out_dir / "instruments").glob("*.json")] == ["SYN-EQ-0001.json"]


def test_a_new_relevant_event_regenerates_only_the_affected_instruments(reg, tmp_path):
    first, _ = stage(reg, tmp_path, as_of=date(2026, 8, 4))
    store = OutlookStore(tmp_path)
    ids = sorted(first.instruments)
    old = {i: instrument_inputs(reg.ctx.repo, store, i, date(2026, 8, 4))[0] for i in ids}
    second, models = stage(reg, tmp_path, as_of=date(2026, 8, 5))
    new = {i: instrument_inputs(reg.ctx.repo, store, i, date(2026, 8, 5))[0] for i in ids}
    assert not second.market.carried_forward_from and second.market.inputs != first.market.inputs        # a new event: a new market outlook
    assert {o.market_outlook_digest for o in new.values()} == {first.instruments[ids[0]].inputs.market_outlook_digest}, "market view unchanged"
    affected = {i for i in ids if new[i].relevant_event_ids != old[i].relevant_event_ids}
    assert 0 < len(affected) < len(ids)
    assert len(models.made) == 1 + len(affected)                                                          # market + affected instruments only
    for i in ids:
        o = second.instruments[i]
        assert (o.carried_forward_from is None) == (i in affected), i
        if i not in affected:
            assert o.previous_as_of == date(2026, 8, 4) and o.view.change.kind == "unchanged"
    assert "EVT-2026-08-05-1" in new["SYN-EQ-0008"].relevant_event_ids and "EVT-2026-08-05-1" not in new["SYN-CM-0401"].relevant_event_ids


def test_force_regenerates_everything(reg, tmp_path):
    stage(reg, tmp_path, instrument_ids=["SYN-EQ-0001", "SYN-EQ-0002"])
    res, models = stage(reg, tmp_path, instrument_ids=["SYN-EQ-0001", "SYN-EQ-0002"], force=True)
    assert not res.skipped and not res.instruments_skipped and models.calls == 6


def test_the_audit_trail_only_grows(reg, tmp_path):
    res, _ = stage(reg, tmp_path, instrument_ids=["SYN-EQ-0001"])
    n = len((res.out_dir / "audit.jsonl").read_text().splitlines())
    stage(reg, tmp_path, instrument_ids=["SYN-EQ-0001"], force=True)
    assert len((res.out_dir / "audit.jsonl").read_text().splitlines()) > n


# ---- 3.3 isolation and persistence ----------------------------------------------------------------
def test_one_failing_instrument_does_not_affect_the_others(reg, tmp_path):
    res, _ = stage(reg, tmp_path, models=Models(fail_for="SYN-EQ-0003"), instrument_ids=["SYN-EQ-0001", "SYN-EQ-0003", "SYN-EQ-0004"])
    assert res.instruments["SYN-EQ-0003"].status == "partial" and res.instruments["SYN-EQ-0003"].view is None
    assert any(g.kind == "agent_error" for g in res.instruments["SYN-EQ-0003"].gaps)
    for ok in ("SYN-EQ-0001", "SYN-EQ-0004"):
        assert res.instruments[ok].status == "complete" and res.instruments[ok].view is not None
    s = json.loads((res.out_dir / "summary.json").read_text())["instruments"]["detail"]
    assert {i: d["status"] for i, d in s.items()} == {"SYN-EQ-0001": "complete", "SYN-EQ-0003": "partial", "SYN-EQ-0004": "complete"}
    assert (res.out_dir / "instruments" / "SYN-EQ-0003.json").is_file()


def test_every_cited_evidence_id_resolves_in_each_instrument_evidence_file(reg, tmp_path):
    from rm_dashboard.domain import ToolResult

    res, _ = stage(reg, tmp_path, instrument_ids=["SYN-EQ-0003", "SYN-CM-0401"])
    for iid, o in res.instruments.items():
        ev = {ToolResult.model_validate(x).evidence_id for x in json.loads((res.out_dir / "evidence" / "instruments" / f"{iid}.json").read_text())}
        cited = {i for r in (*o.view.drivers, *o.view.risks) for i in r.evidence_ids}
        assert cited and cited <= ev and set(o.evidence_ids) <= ev


def test_the_reference_chain_of_an_instrument(reg, tmp_path):
    first, _ = stage(reg, tmp_path, as_of=date(2026, 6, 30), instrument_ids=["SYN-EQ-0003"])
    path = first.out_dir / "instruments" / "SYN-EQ-0003.json"
    before = path.read_bytes()
    second, _ = stage(reg, tmp_path, instrument_ids=["SYN-EQ-0003"])
    o = second.instruments["SYN-EQ-0003"]
    assert path.read_bytes() == before and o.previous_as_of == date(2026, 6, 30) and not o.is_first


# ---- command line -----------------------------------------------------------------------------
def test_cli_writes_market_and_instruments(seeded_db, tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("RM_DASHBOARD_DB", raising=False)
    args = ["--as-of", "2026-08-26", "--db", str(seeded_db), "--reports-dir", str(tmp_path)]
    assert main(args) == 0
    out = capsys.readouterr().out
    assert "market outlook written" in out and "instrument outlooks: 62 written" in out and "0 unchanged" in out
    assert len(list((tmp_path / "2026-08-26" / "outlook" / "instruments").glob("*.json"))) == 62
    assert main(args) == 0
    assert "already exist with the same inputs: unchanged" in capsys.readouterr().out
    assert main([*args, "--instruments", "SYN-EQ-0001,SYN-EQ-0002", "--force"]) == 0
    out = capsys.readouterr().out
    assert "2 written" in out and "60 unchanged" not in out and "instrument outlooks: 2 written" in out
