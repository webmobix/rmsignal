"""Outlook stage: the market outlook, then one outlook per held instrument, persisted;
command line ``rm-dashboard-outlook --as-of DATE``."""

import json
import sys
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, replace
from datetime import date
from pathlib import Path

from rm_dashboard.agents import build_model
from rm_dashboard.agents.analyst import ModelFactory
from rm_dashboard.domain import Gap
from rm_dashboard.outlook import InstrumentOutlook, MarketOutlook
from rm_dashboard.outlook.agent import produce_instrument_outlook, produce_market_outlook
from rm_dashboard.outlook.inputs import compute_inputs, held_instruments, instrument_inputs
from rm_dashboard.outlook.store import OutlookStore
from rm_dashboard.policy import AuditLog, MockPolicyEngine, PolicyEngine
from rm_dashboard.llmlog import llm_logging
from rm_dashboard.settings import Settings
from rm_dashboard.tools import ToolRegistry

from .wiring import open_registry

STATUSES = ("complete", "partial", "insufficient_data")


@dataclass
class OutlookResult:
    as_of: date
    out_dir: Path
    market: MarketOutlook
    summary: dict
    skipped: bool = False
    """The market outlook was left as it was: same inputs, no force."""
    instruments: dict[str, InstrumentOutlook] = field(default_factory=dict)
    instruments_skipped: set[str] = field(default_factory=set)

    @property
    def untouched(self) -> bool:
        return self.skipped and len(self.instruments_skipped) == len(self.instruments)


def market_summary(o: MarketOutlook) -> dict:
    return {"status": o.status, "file": "market.json", "views": len(o.views), "previous_as_of": o.previous_as_of.isoformat() if o.previous_as_of else None,
            "carried_forward_from": o.carried_forward_from.isoformat() if o.carried_forward_from else None,
            "changes": o.changes_summary, "gaps": len(o.gaps), "unaddressed_events": len(o.unaddressed_events)}


def instrument_summary(o: InstrumentOutlook) -> dict:
    return {"status": o.status, "file": f"instruments/{o.subject}.json", "direction": o.view.direction if o.view else None,
            "confidence": o.view.confidence if o.view else None, "changes": o.changes_summary,
            "carried_forward_from": o.carried_forward_from.isoformat() if o.carried_forward_from else None,
            "gaps": len(o.gaps), "unaddressed_events": len(o.unaddressed_events)}


def run_outlook(registry: ToolRegistry, *, as_of: date, reports_dir: Path, models: ModelFactory | None = None,
                engine: PolicyEngine | None = None, settings: Settings | None = None, force: bool = False,
                instrument_ids: list[str] | None = None, with_instruments: bool = True) -> OutlookResult:
    settings = settings or registry.ctx.settings
    models = models or (lambda role: build_model(settings, role=role))
    engine = engine or MockPolicyEngine()
    repo = registry.ctx.repo
    store = OutlookStore(reports_dir)
    out_dir = store.outlook_dir(as_of)
    with llm_logging("outlook", out_dir) as llm:
        audit_path = out_dir / "audit.jsonl"
        audit: AuditLog | None = None

        def the_audit() -> AuditLog:
            nonlocal audit
            if audit is None:  # the trail is append-only: a later run adds to it, nothing is ever removed
                out_dir.mkdir(parents=True, exist_ok=True)
                audit = AuditLog(audit_path)
            return audit

        # ---- market ---------------------------------------------------------------------------
        existing = store.load_market(as_of)
        market_skipped = (existing is not None and not force and existing.status != "insufficient_data"
                          and existing.inputs == compute_inputs(repo, as_of)[0])
        if market_skipped:
            market = existing
        else:
            market, evidence = produce_market_outlook(registry, as_of=as_of, store=store, models=models, engine=engine, audit=the_audit(), force=force)
            store.save_market(market, evidence)

        # ---- instruments ----------------------------------------------------------------------
        ids = sorted(set(instrument_ids)) if instrument_ids else (held_instruments(repo, as_of) if with_instruments else [])
        todo: list[str] = []
        done: dict[str, InstrumentOutlook] = {}
        skipped: set[str] = set()
        for iid in ids:
            old = store.load_instrument(as_of, iid)
            if old is not None and not force and old.status != "insufficient_data" and old.inputs.same_as(instrument_inputs(repo, store, iid, as_of)[0]):
                done[iid] = old
                skipped.add(iid)
            else:
                todo.append(iid)

        def one(iid: str):
            try:
                return iid, *produce_instrument_outlook(registry, instrument_id=iid, as_of=as_of, store=store, models=models, engine=engine,
                                                        audit=the_audit(), force=force)
            except Exception as e:  # noqa: BLE001 - belt and braces: produce_instrument_outlook already never raises
                return iid, InstrumentOutlook(subject=iid, as_of=as_of, status="partial",
                                              gaps=[Gap(kind="agent_error", description=f"{type(e).__name__}: {e}", subject=iid)]), []

        if todo:
            with ThreadPoolExecutor(max_workers=max(1, settings.max_concurrency)) as pool:
                for iid, outlook, evidence in pool.map(one, todo):
                    store.save_instrument(outlook, evidence)
                    done[iid] = outlook

        detail = {iid: instrument_summary(done[iid]) for iid in ids}
        counts = Counter(o.status for o in done.values())
        summary = {"as_of": as_of.isoformat(), "model": settings.model_name, "market": market_summary(market),
                   "instruments": {"count": len(ids), "unchanged": len(skipped), "status_counts": {s: counts.get(s, 0) for s in STATUSES}, "detail": detail},
                   "audit_log": audit_path.name}
        summary["llm"] = llm.counts()
        if audit is not None:  # something ran: the summary describes the state after it
            (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))
        elif (out_dir / "summary.json").is_file():
            summary = json.loads((out_dir / "summary.json").read_text())
        return OutlookResult(as_of, out_dir, market, summary, skipped=market_skipped, instruments=done, instruments_skipped=skipped)


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="rm-dashboard-outlook",
                                description="Write the house-view outlooks as of a date: the market, then every held instrument. "
                                            "An outlook changes only when new data has arrived.")
    p.add_argument("--as-of", required=True, type=date.fromisoformat, metavar="YYYY-MM-DD", help="analysis date (required)")
    p.add_argument("--instruments", help="comma-separated instrument ids (default: every instrument held in any portfolio)")
    p.add_argument("--db", help="seeded SQLite database (or set RM_DASHBOARD_DB)")
    p.add_argument("--reports-dir", default="reports", help="folder holding <as-of>/outlook/ (default: reports)")
    p.add_argument("--concurrency", type=int, help="instruments processed in parallel (default: RM_MAX_CONCURRENCY or 4)")
    p.add_argument("--force", action="store_true", help="regenerate even when no new data has arrived")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    settings = Settings.from_env()
    overrides = {k: v for k, v in (("db_path", args.db), ("max_concurrency", args.concurrency)) if v}
    settings = replace(settings, **overrides)
    if not settings.db_path:
        print("error: no database given: pass --db rm.db or set RM_DASHBOARD_DB", file=sys.stderr)
        return 2
    if not Path(settings.db_path).is_file():
        print(f"error: database not found: {settings.db_path} (create it with `rm-dashboard-seed --db {settings.db_path}`)", file=sys.stderr)
        return 2
    ids = [i.strip() for i in args.instruments.split(",") if i.strip()] if args.instruments else None
    with open_registry(settings, with_peer=False, reports_dir=args.reports_dir) as registry:
        result = run_outlook(registry, as_of=args.as_of, reports_dir=Path(args.reports_dir), settings=settings, force=args.force, instrument_ids=ids)
    m = result.market
    if result.untouched:
        print(f"outlooks for {args.as_of} already exist with the same inputs: unchanged ({result.out_dir})")
        return 0
    how = f"carried forward from {m.carried_forward_from}" if m.carried_forward_from else ("first outlook" if m.is_first else f"compared with {m.previous_as_of}")
    if result.skipped:
        print(f"market outlook for {args.as_of} unchanged ({result.out_dir / 'market.json'})")
    else:
        print(f"market outlook written to {result.out_dir / 'market.json'}: {m.status}, {len(m.views)} views, {how}, "
              f"{len(m.gaps)} gaps, {len(m.unaddressed_events)} unaddressed severe events; model: {settings.model_name}")
    if result.instruments:
        c = Counter(o.status for o in result.instruments.values())
        print(f"instrument outlooks: {len(result.instruments) - len(result.instruments_skipped)} written to {result.out_dir / 'instruments'}, "
              f"{len(result.instruments_skipped)} unchanged (complete {c['complete']}, partial {c['partial']}, insufficient_data {c['insufficient_data']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
