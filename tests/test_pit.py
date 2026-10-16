import ast
from datetime import date
from pathlib import Path

import polars as pl
import pytest

from rm_dashboard.pit import AsOfError

D = date


def test_rows_and_long_tables(pit_repo):
    h = pit_repo.holdings(as_of=D(2026, 8, 26))
    assert h.status == "ok" and h.effective_snapshot_date == D(2026, 8, 26) and h.gap_days == 0
    assert pit_repo.snapshot_dates()[0] == D(2025, 12, 31) and len(pit_repo.snapshot_dates()) == 5
    aum = pit_repo.portfolio_aum(as_of=D(2026, 8, 26)).frame
    assert aum.height == 24 * 5
    assert pit_repo.instrument_prices(as_of=D(2026, 8, 26)).frame.height == 62 * 5
    assert pit_repo.facility_snapshots(as_of=D(2026, 8, 26)).frame.height == 5 * 5
    one = pit_repo.instrument_prices(as_of=D(2026, 8, 26), instrument_id="SYN-EQ-0001").frame
    assert one.height == 5 and one["snapshot_date"].n_unique() == 5


def test_prices_only_up_to_effective_snapshot(pit_repo):
    f = pit_repo.instrument_prices(as_of=D(2026, 4, 15), instrument_id="SYN-EQ-0001").frame
    assert f["snapshot_date"].max() == D(2026, 3, 31) and f.height == 3


def test_aum_reconciles_to_holdings(pit_repo):
    for snap in pit_repo.snapshot_dates():
        h = pit_repo.holdings(as_of=snap).frame.group_by("portfolio_id").agg(pl.col("market_value_base").sum())
        a = pit_repo.portfolio_aum(as_of=snap).frame.filter(pl.col("snapshot_date") == snap)
        j = h.join(a, on="portfolio_id")
        assert j.height == h.height
        diff = (j["market_value_base"] - j["aum"]).abs().max()
        assert diff < max(1.0, 1e-4 * j["aum"].max()), (snap, diff)


def test_missing_or_bad_as_of_rejected(pit_repo):
    with pytest.raises(TypeError):
        pit_repo.holdings()
    for bad in (None, "2026-08-26"):
        with pytest.raises(AsOfError):
            pit_repo.holdings(as_of=bad)
        with pytest.raises(AsOfError):
            pit_repo.resolve(as_of=bad)


def test_between_snapshots(pit_repo):
    r = pit_repo.resolve(as_of=D(2026, 2, 1))
    assert r.effective_snapshot_date == D(2025, 12, 31) and r.gap_days == 32
    h = pit_repo.holdings(as_of=D(2026, 2, 1))
    assert set(h.frame["snapshot_date"].to_list()) == {D(2025, 12, 31)}
    assert any(f.code == "snapshot_lag" for f in h.flags)


def test_before_first_snapshot(pit_repo):
    for res in (pit_repo.holdings(as_of=D(2025, 1, 1)), pit_repo.facility_snapshots(as_of=D(2025, 1, 1)),
                pit_repo.portfolio_aum(as_of=D(2025, 1, 1))):
        assert res.status == "insufficient_data" and res.frame.is_empty() and res.reason


def test_event_dated_no_lookahead(pit_repo):
    as_of = D(2026, 8, 1)
    assert pit_repo.notes(as_of=as_of).frame["note_date"].max() <= as_of
    assert pit_repo.events(as_of=as_of).frame["event_date"].max() <= as_of
    assert pit_repo.transactions(as_of=as_of).frame["trade_date"].max() <= as_of
    # a note dated 2026-08-19 exists and is excluded at 2026-08-01, included at 2026-08-26
    full = pit_repo.notes(as_of=D(2026, 8, 26)).frame
    late = full.filter(pl.col("note_date") > as_of)
    assert late.height > 0
    early = pit_repo.notes(as_of=as_of).frame
    assert not set(late["note_id"]) & set(early["note_id"])
    assert pit_repo.notes(as_of=D(2020, 1, 1)).frame.is_empty()


def test_cash_needs_assumed_known_since_relationship_start(pit_repo):
    r = pit_repo.cash_needs(as_of=D(2026, 3, 31))
    assert r.frame.height == 20 and r.pit == "current_only"       # every client already existed: nothing dropped
    assert any(f.code == "assumed_known_since_relationship_start" for f in r.flags)
    # CL-0003 became a client on 2026-02-16: its need exists from then on, not before
    assert pit_repo.cash_needs(as_of=D(2026, 2, 15), client_id="CL-0003").frame.is_empty()
    assert pit_repo.cash_needs(as_of=D(2026, 2, 16), client_id="CL-0003").frame["need_id"].to_list() == ["CN-004"]
    assert pit_repo.cash_needs(as_of=D(2026, 8, 26), client_id="CL-0003").frame.height == 1
    assert pit_repo.commitments(as_of=D(2026, 8, 26), client_id="CL-0017").frame.height == 2


def test_current_only_tagging(pit_repo):
    c = pit_repo.clients(as_of=D(2026, 3, 31), client_id="CL-0001")
    assert c.pit == "current_only" and "risk_profile" in c.current_only_attributes
    assert "kyc_review_due" in c.current_only_attributes and "tax_domicile" in c.current_only_attributes
    assert any(f.code == "current_only" for f in c.flags)
    p = pit_repo.portfolios(as_of=D(2026, 3, 31), client_id="CL-0001")
    assert "mandate_code" in p.current_only_attributes and "benchmark" in p.current_only_attributes
    assert p.frame.height == 2 and "aum" in p.frame.columns
    assert pit_repo.mandates(as_of=D(2026, 3, 31)).pit == "current_only"


def codes(res, code):
    return {f.subject for f in res.flags if f.code == code}


def test_quality_flags_known_rows(pit_repo):
    h = pit_repo.holdings(as_of=D(2026, 8, 26))
    assert codes(h, "stale_mark") == {"PF-0004/SYN-AL-0308"}
    msg = next(f.message for f in h.flags if f.code == "stale_mark")
    assert "2025-09-30" in msg and "2026-08-26" in msg
    assert codes(h, "missing_cost_basis") == {"PF-0005/SYN-ST-0107"}
    assert "bond_nominal_unit" in {f.code for f in h.flags}
    tx = pit_repo.transactions(as_of=D(2026, 8, 26))
    assert codes(tx, "subscription_currency_mismatch") == {"TXN-0004", "TXN-0005"}
    fac = pit_repo.facility_snapshots(as_of=D(2026, 8, 26))
    assert codes(fac, "facility_drawdown_mismatch") == {"CF-0002"}
    # the other facility's drawdown reconciles with its transaction
    assert "CF-0001" not in codes(fac, "facility_drawdown_mismatch")


def test_mid_period_position_flag(pit_repo):
    h = pit_repo.holdings(as_of=D(2026, 6, 30))
    assert "PF-0001/SYN-SP-0505" in codes(h, "mid_period_position")
    assert not codes(pit_repo.holdings(as_of=D(2025, 12, 31)), "mid_period_position")


def test_flags_depend_on_as_of(pit_repo):
    early = pit_repo.facility_snapshots(as_of=D(2026, 2, 27))
    assert not codes(early, "facility_drawdown_mismatch")


def test_kyc_overdue_differs_by_as_of(pit_repo):
    a = pit_repo.clients(as_of=D(2026, 8, 26)).frame
    b = pit_repo.clients(as_of=D(2026, 10, 15)).frame
    assert a["kyc_overdue"].sum() != b["kyc_overdue"].sum()
    assert not (a["kyc_overdue"] == b["kyc_overdue"]).all()


def test_repeatable_regardless_of_calendar(pit_repo):
    a = pit_repo.holdings(as_of=D(2026, 8, 26)).frame
    b = pit_repo.holdings(as_of=D(2026, 8, 26)).frame
    assert a.equals(b)


CLOCK_CALLS = {("date", "today"), ("datetime", "now"), ("datetime", "utcnow"), ("datetime", "today"),
               ("time", "time"), ("time", "monotonic"), ("time", "perf_counter"), ("time", "time_ns")}


def test_no_module_reads_the_wall_clock():
    root = Path(__file__).parent.parent / "src" / "rm_dashboard"
    offenders = []
    for path in root.rglob("*.py"):
        if path.name == "llmlog.py":  # measures how long a model call took; never feeds analysis data or as_of
            continue
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                v = node.func.value
                name = v.id if isinstance(v, ast.Name) else v.attr if isinstance(v, ast.Attribute) else None
                if (name, node.func.attr) in CLOCK_CALLS:
                    offenders.append(f"{path.relative_to(root)}:{node.lineno}")
    assert not offenders, offenders


def test_client_record_has_no_current_aum_leak(pit_repo):
    a = pit_repo.clients(as_of=D(2026, 3, 31), client_id="CL-0001")
    b = pit_repo.clients(as_of=D(2026, 8, 26), client_id="CL-0001")
    ra, rb = a.frame.row(0, named=True), b.frame.row(0, named=True)
    assert "total_aum_usd" not in ra and rb["aum_snapshot_date"] == D(2026, 8, 26) and ra["aum_snapshot_date"] == D(2026, 3, 31)
    assert ra["aum_usd"] != rb["aum_usd"]
    h = pit_repo.holdings(as_of=D(2026, 3, 31), client_id="CL-0001").frame
    assert ra["aum_usd"] == pytest.approx(h["market_value_usd"].sum())
    assert rb["aum_usd"] == pytest.approx(46571821.48, rel=1e-4)       # reconciles to the source's current total
    early = pit_repo.clients(as_of=D(2025, 1, 1), client_id="CL-0001")
    assert early.status in ("ok", "insufficient_data") and (not early.frame.height or early.frame["aum_usd"][0] is None)


def test_no_frame_exposes_current_only_quantities(pit_repo):
    for res in (pit_repo.clients(as_of=D(2026, 3, 31)), pit_repo.portfolios(as_of=D(2026, 3, 31)),
                pit_repo.facility_terms(as_of=D(2026, 3, 31)), pit_repo.holdings(as_of=D(2026, 3, 31)),
                pit_repo.instruments(as_of=D(2026, 3, 31))):
        leaked = [c for c in res.frame.columns if c.endswith("_current") or c.startswith("total_")]
        assert not leaked, (res.dataset, leaked)
