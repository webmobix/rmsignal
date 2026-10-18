"""Outlook stage: the market outlook, then one outlook per held instrument, persisted;
command line ``rm-dashboard-outlook --as-of DATE``."""

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
from rm_dashboard.store import ArtifactStore, check_writable, log_dir
from rm_dashboard.store.summary import get_summary, put_summary
from rm_dashboard.tools import ToolRegistry

from .stage import add_store_args, data_source_problem, open_audit, store_from_args
from .wiring import open_registry

STATUSES = ("complete", "partial", "insufficient_data")
STAGE = "outlook"


@dataclass
class OutlookResult:
    as_of: date
    out_dir: Path
    """The local folder of the run log (``run.log``)."""
    market: MarketOutlook
    summary: dict
    skipped: bool = False
    """The market outlook was left as it was: same inputs, no force."""
    instruments: dict[str, InstrumentOutlook] = field(default_factory=dict)
    instruments_skipped: set[str] = field(default_factory=set)
    store: ArtifactStore | None = None

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


def run_outlook(registry: ToolRegistry, *, as_of: date, store: ArtifactStore | str | Path, models: ModelFactory | None = None,
                engine: PolicyEngine | None = None, settings: Settings | None = None, force: bool = False,
                instrument_ids: list[str] | None = None, with_instruments: bool = True) -> OutlookResult:
    settings = settings or registry.ctx.settings
    models = models or (lambda role: build_model(settings, role=role))
    engine = engine or MockPolicyEngine()
    repo = registry.ctx.repo
    outlooks = OutlookStore(store)
    artifacts = outlooks.store
    check_writable(artifacts)
    out_dir = log_dir(artifacts, as_of, STAGE)
    with llm_logging("outlook", out_dir) as llm:
        audit: AuditLog | None = None

        def the_audit() -> AuditLog:
            nonlocal audit
            if audit is None:  # the trail is append-only: a later run adds to it, nothing is ever removed
                audit = open_audit(artifacts, as_of, STAGE, resume=True)
            return audit

        # ---- market ---------------------------------------------------------------------------
        existing = outlooks.load_market(as_of)
        market_skipped = (existing is not None and not force and existing.status != "insufficient_data"
                          and existing.inputs == compute_inputs(repo, as_of)[0])
        if market_skipped:
            market = existing
        else:
            market, evidence = produce_market_outlook(registry, as_of=as_of, store=outlooks, models=models, engine=engine, audit=the_audit(), force=force)
            outlooks.save_market(market, evidence)

        # ---- instruments ----------------------------------------------------------------------
        ids = sorted(set(instrument_ids)) if instrument_ids else (held_instruments(repo, as_of) if with_instruments else [])
        todo: list[str] = []
        done: dict[str, InstrumentOutlook] = {}
        skipped: set[str] = set()
        for iid in ids:
            old = outlooks.load_instrument(as_of, iid)
            if old is not None and not force and old.status != "insufficient_data" and old.inputs.same_as(instrument_inputs(repo, outlooks, iid, as_of)[0]):
                done[iid] = old
                skipped.add(iid)
            else:
                todo.append(iid)

        def one(iid: str):
            try:
                return iid, *produce_instrument_outlook(registry, instrument_id=iid, as_of=as_of, store=outlooks, models=models, engine=engine,
                                                        audit=the_audit(), force=force)
            except Exception as e:  # noqa: BLE001 - belt and braces: produce_instrument_outlook already never raises
                return iid, InstrumentOutlook(subject=iid, as_of=as_of, status="partial",
                                              gaps=[Gap(kind="agent_error", description=f"{type(e).__name__}: {e}", subject=iid)]), []

        if todo:
            with ThreadPoolExecutor(max_workers=max(1, settings.max_concurrency)) as pool:
                for iid, outlook, evidence in pool.map(one, todo):
                    outlooks.save_instrument(outlook, evidence)
                    done[iid] = outlook

        detail = {iid: instrument_summary(done[iid]) for iid in ids}
        counts = Counter(o.status for o in done.values())
        summary = {"as_of": as_of.isoformat(), "model": settings.model_name, "market": market_summary(market),
                   "instruments": {"count": len(ids), "unchanged": len(skipped), "status_counts": {s: counts.get(s, 0) for s in STATUSES}, "detail": detail},
                   "audit_log": f"audit/{STAGE}"}
        summary["llm"] = llm.counts()
        if audit is not None:  # something ran: the summary describes the state after it
            put_summary(artifacts, as_of, STAGE, summary)
        elif (earlier := get_summary(artifacts, as_of, STAGE)) is not None:
            summary = earlier
        return OutlookResult(as_of, out_dir, market, summary, skipped=market_skipped, instruments=done, instruments_skipped=skipped,
                             store=artifacts)


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="rm-dashboard-outlook",
                                description="Write the house-view outlooks as of a date: the market, then every held instrument. "
                                            "An outlook changes only when new data has arrived.")
    p.add_argument("--as-of", required=True, type=date.fromisoformat, metavar="YYYY-MM-DD", help="analysis date (required)")
    p.add_argument("--instruments", help="comma-separated instrument ids (default: every instrument held in any portfolio)")
    p.add_argument("--db", help="seeded SQLite database (or set RM_DASHBOARD_DB)")
    add_store_args(p)
    p.add_argument("--concurrency", type=int, help="instruments processed in parallel (default: RM_MAX_CONCURRENCY or 4)")
    p.add_argument("--force", action="store_true", help="regenerate even when no new data has arrived")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    settings = Settings.from_env()
    overrides = {k: v for k, v in (("db_path", args.db), ("max_concurrency", args.concurrency)) if v}
    settings = replace(settings, **overrides)
    if (problem := data_source_problem(settings)) is not None:
        print(f"error: {problem}", file=sys.stderr)
        return 2
    ids = [i.strip() for i in args.instruments.split(",") if i.strip()] if args.instruments else None
    try:
        store = store_from_args(args, settings)
    except (ValueError, ImportError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    with open_registry(settings, with_peer=False, artifacts=store) as registry:
        result = run_outlook(registry, as_of=args.as_of, store=store, settings=settings, force=args.force, instrument_ids=ids)
    m = result.market
    if result.untouched:
        print(f"outlooks for {args.as_of} already exist with the same inputs: unchanged ({result.store.location})")
        return 0
    how = f"carried forward from {m.carried_forward_from}" if m.carried_forward_from else ("first outlook" if m.is_first else f"compared with {m.previous_as_of}")
    if result.skipped:
        print(f"market outlook for {args.as_of} unchanged ({result.store.location})")
    else:
        print(f"market outlook written to {result.store.location}: {m.status}, {len(m.views)} views, {how}, "
              f"{len(m.gaps)} gaps, {len(m.unaddressed_events)} unaddressed severe events; model: {settings.model_name}")
    if result.instruments:
        c = Counter(o.status for o in result.instruments.values())
        print(f"instrument outlooks: {len(result.instruments) - len(result.instruments_skipped)} written to {result.store.location}, "
              f"{len(result.instruments_skipped)} unchanged (complete {c['complete']}, partial {c['partial']}, insufficient_data {c['insufficient_data']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
