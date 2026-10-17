"""Scenario stage: one shock vector per scenario, one impact per portfolio and scenario, then client and RM roll-ups, persisted;
command line ``rm-dashboard-scenarios --as-of DATE``.

A unit whose stored result has the same input hash is skipped without a model call. Units run in parallel, each result is written
as soon as it exists (a rerun after an interruption does only the missing units) and a failing unit never stops the others."""

import argparse
import json
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, replace
from datetime import date
from pathlib import Path

from rm_dashboard.agents import build_model
from rm_dashboard.agents.analyst import ModelFactory
from rm_dashboard.domain import Gap
from rm_dashboard.llmlog import llm_logging
from rm_dashboard.policy import AuditLog, MockPolicyEngine, PolicyEngine
from rm_dashboard.scenarios.agent import current_hash as vector_hash_now
from rm_dashboard.scenarios.agent import produce_shock_vector
from rm_dashboard.scenarios.catalogue import CatalogueStore
from rm_dashboard.scenarios.contracts import ClientRollup, PortfolioImpact, RMRollup, ScenarioRecord, ShockVector
from rm_dashboard.scenarios.impact_agent import current_hash as impact_hash_now
from rm_dashboard.scenarios.impact_agent import produce_portfolio_impact
from rm_dashboard.scenarios.inputs import load_portfolio_inputs, rollup_inputs_hash
from rm_dashboard.scenarios.rollup_agent import produce_client_rollup, produce_rm_rollup
from rm_dashboard.scenarios.store import ScenarioStore
from rm_dashboard.settings import Settings
from rm_dashboard.tools import ToolRegistry

from .wiring import open_registry

STATUSES = ("complete", "partial", "insufficient_data")


@dataclass
class Failure:
    unit: str
    error: str


@dataclass
class ScenarioRunResult:
    as_of: date
    out_dir: Path
    summary: dict
    produced: Counter = field(default_factory=Counter)
    """Units written by this run, by kind (vector, impact, client, rollup)."""
    skipped: Counter = field(default_factory=Counter)
    """Units left as they were: same inputs, no force."""
    failures: list[Failure] = field(default_factory=list)
    rejected: list[str] = field(default_factory=list)

    @property
    def untouched(self) -> bool:
        return not sum(self.produced.values()) and not self.failures


def _current(old, inputs_hash: str, force: bool) -> bool:
    return old is not None and not force and old.status != "insufficient_data" and old.inputs_hash == inputs_hash


def _failed_impact(scenario: ScenarioRecord, pid: str, client: str, as_of: date, e: Exception, model: str) -> PortfolioImpact:
    return PortfolioImpact(scenario_id=scenario.scenario_id, portfolio_id=pid, client_id=client, as_of=as_of, status="insufficient_data",
                           horizon_months=scenario.horizon_months, model=model,
                           gaps=[Gap(kind="agent_error", description=f"{type(e).__name__}: {e}", subject=pid)])


def run_scenarios(registry: ToolRegistry, *, as_of: date, reports_dir: Path, models: ModelFactory | None = None, engine: PolicyEngine | None = None,
                  settings: Settings | None = None, force: bool = False, scenario_ids: list[str] | None = None,
                  portfolio_ids: list[str] | None = None) -> ScenarioRunResult:
    settings = settings or registry.ctx.settings
    models = models or (lambda role: build_model(settings, role=role))
    engine = engine or MockPolicyEngine()
    repo = registry.ctx.repo
    model = settings.model_name
    store = ScenarioStore(reports_dir)
    catalogue = CatalogueStore(reports_dir).ensure_seeded()
    scenarios = [s for s in catalogue.scenarios if not scenario_ids or s.scenario_id in scenario_ids]
    unknown = sorted(set(scenario_ids or []) - {s.scenario_id for s in catalogue.scenarios})
    if unknown:
        raise ValueError(f"unknown scenario(s): {', '.join(unknown)}; the catalogue has {', '.join(s.scenario_id for s in catalogue.scenarios)}")
    out_dir = store.run_dir(as_of)
    result = ScenarioRunResult(as_of, out_dir, {}, rejected=catalogue.rejected)
    pf_frame = repo.portfolios(as_of=as_of).frame
    portfolios = [r for r in pf_frame.to_dicts()] if pf_frame.height else []
    all_pids = [p["portfolio_id"] for p in portfolios]
    unknown_pf = sorted(set(portfolio_ids or []) - set(all_pids))
    if unknown_pf:
        raise ValueError(f"unknown portfolio(s) at {as_of}: {', '.join(unknown_pf)}")
    todo_pf = [p for p in portfolios if not portfolio_ids or p["portfolio_id"] in portfolio_ids]
    cl_frame = repo.clients(as_of=as_of).frame
    clients = cl_frame.to_dicts() if cl_frame.height else []
    rm_ids = sorted({c["rm_id"] for c in clients if c.get("rm_id")})
    rm_id = rm_ids[0] if len(rm_ids) == 1 else None
    by_client: dict[str, list[dict]] = {}
    for p in portfolios:
        by_client.setdefault(p["client_id"], []).append(p)
    workers = max(1, settings.max_concurrency)

    with llm_logging("scenarios", out_dir) as llm:
        audit_path = out_dir / "audit.jsonl"
        audit: AuditLog | None = None

        def the_audit() -> AuditLog:
            nonlocal audit
            if audit is None:  # the trail is append-only: a later run adds to it, nothing is ever removed
                out_dir.mkdir(parents=True, exist_ok=True)
                audit = AuditLog(audit_path)
            return audit

        def fail(unit: str, e: Exception) -> None:
            result.failures.append(Failure(unit, f"{type(e).__name__}: {e}"))

        # ---- vectors --------------------------------------------------------------------------
        vectors: dict[str, ShockVector] = {}
        vtodo: list[ScenarioRecord] = []
        for s in scenarios:
            old = store.load_vector(as_of, s.scenario_id)
            if _current(old, vector_hash_now(repo, s, as_of, model), force):
                vectors[s.scenario_id] = old
                result.skipped["vector"] += 1
            else:
                vtodo.append(s)

        def one_vector(s: ScenarioRecord):
            try:
                v, ev = produce_shock_vector(registry, scenario=s, as_of=as_of, store=store, models=models, model_name=model, engine=engine, audit=the_audit())
                return s, v, ev, None
            except Exception as e:  # noqa: BLE001 - belt and braces: produce_shock_vector already never raises
                return s, ShockVector(scenario_id=s.scenario_id, as_of=as_of, status="insufficient_data", horizon_months=s.horizon_months, model=model,
                                      gaps=[Gap(kind="agent_error", description=f"{type(e).__name__}: {e}", subject=s.scenario_id)]), [], e

        if vtodo:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                for s, v, ev, err in pool.map(one_vector, vtodo):
                    store.save_vector(v, ev)
                    vectors[s.scenario_id] = v
                    result.produced["vector"] += 1
                    if err:
                        fail(f"vector {s.scenario_id}", err)

        # ---- impacts --------------------------------------------------------------------------
        impacts: dict[tuple[str, str], PortfolioImpact] = {}
        itodo: list[tuple[ScenarioRecord, dict]] = []
        for s in scenarios:
            v = vectors.get(s.scenario_id)
            for p in todo_pf:
                pid = p["portfolio_id"]
                old = store.load_impact(as_of, s.scenario_id, pid)
                inputs = load_portfolio_inputs(repo, as_of, pid)
                if inputs is not None and _current(old, impact_hash_now(inputs, v, model), force):
                    impacts[(s.scenario_id, pid)] = old
                    result.skipped["impact"] += 1
                else:
                    itodo.append((s, p))

        def one_impact(unit):
            s, p = unit
            try:
                i, ev = produce_portfolio_impact(registry, scenario=s, portfolio_id=p["portfolio_id"], as_of=as_of, store=store, models=models,
                                                 model_name=model, engine=engine, audit=the_audit())
                return s, p, i, ev, None
            except Exception as e:  # noqa: BLE001 - belt and braces: produce_portfolio_impact already never raises
                return s, p, _failed_impact(s, p["portfolio_id"], p["client_id"], as_of, e, model), [], e

        if itodo:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                for s, p, i, ev, err in pool.map(one_impact, itodo):
                    store.save_impact(i, ev)
                    impacts[(s.scenario_id, p["portfolio_id"])] = i
                    result.produced["impact"] += 1
                    if err:
                        fail(f"impact {s.scenario_id} x {p['portfolio_id']}", err)

        # ---- client roll-ups ------------------------------------------------------------------
        touched_clients = {p["client_id"] for p in todo_pf}
        client_results: dict[tuple[str, str], ClientRollup | None] = {}
        ctodo: list[tuple[ScenarioRecord, str, dict]] = []
        for s in scenarios:
            for cid in sorted(by_client):
                members = {p["portfolio_id"]: impacts.get((s.scenario_id, p["portfolio_id"])) or store.load_impact(as_of, s.scenario_id, p["portfolio_id"])
                           for p in by_client[cid]}
                old = store.load_client(as_of, s.scenario_id, cid)
                if cid not in touched_clients:
                    client_results[(s.scenario_id, cid)] = old
                    continue
                want = rollup_inputs_hash(member_hashes=[i.inputs_hash for i in members.values() if i is not None], model=model)
                if _current(old, want, force):
                    client_results[(s.scenario_id, cid)] = old
                    result.skipped["client"] += 1
                else:
                    ctodo.append((s, cid, members))

        def one_client(unit):
            s, cid, members = unit
            names = {p["portfolio_id"]: p["portfolio_name"] for p in by_client[cid]}
            try:
                return s, cid, produce_client_rollup(registry, scenario=s, as_of=as_of, client_id=cid, impacts=members, store=store, models=models,
                                                     names=names, model_name=model, engine=engine, audit=the_audit()), None
            except Exception as e:  # noqa: BLE001
                return s, cid, ClientRollup(scenario_id=s.scenario_id, client_id=cid, as_of=as_of, status="insufficient_data",
                                            gaps=[Gap(kind="agent_error", description=f"{type(e).__name__}: {e}", subject=cid)]), e

        if ctodo:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                for s, cid, r, err in pool.map(one_client, ctodo):
                    store.save_client(r)
                    client_results[(s.scenario_id, cid)] = r
                    result.produced["client"] += 1
                    if err:
                        fail(f"client {s.scenario_id} x {cid}", err)

        # ---- RM book roll-ups -----------------------------------------------------------------
        rollups: dict[str, RMRollup] = {}
        for s in scenarios:
            book = {cid: client_results.get((s.scenario_id, cid)) for cid in sorted(by_client)}
            want = rollup_inputs_hash(member_hashes=[c.inputs_hash for c in book.values() if c is not None], model=model)
            old = store.load_rollup(as_of, s.scenario_id)
            if _current(old, want, force):
                rollups[s.scenario_id] = old
                result.skipped["rollup"] += 1
                continue
            try:
                r = produce_rm_rollup(registry, scenario=s, as_of=as_of, rm_id=rm_id, clients=book, store=store, models=models, model_name=model,
                                      engine=engine, audit=the_audit())
            except Exception as e:  # noqa: BLE001
                fail(f"rollup {s.scenario_id}", e)
                r = RMRollup(scenario_id=s.scenario_id, as_of=as_of, rm_id=rm_id, status="insufficient_data",
                             gaps=[Gap(kind="agent_error", description=f"{type(e).__name__}: {e}", subject=s.scenario_id)])
            store.save_rollup(r)
            rollups[s.scenario_id] = r
            result.produced["rollup"] += 1

        result.summary = _summary(as_of, model, scenarios, vectors, impacts, client_results, rollups, result, audit_path.name)
        result.summary["llm"] = llm.counts()
        if sum(result.produced.values()) or result.failures:  # something ran: the summary describes the state after it
            summary_path = out_dir / "summary.json"
            result.summary = _merge(summary_path, result.summary)
            out_dir.mkdir(parents=True, exist_ok=True)
            summary_path.write_text(json.dumps(result.summary, indent=2))
        elif (out_dir / "summary.json").is_file():
            result.summary = json.loads((out_dir / "summary.json").read_text())
    return result


def _count(items) -> dict:
    c = Counter(i.status for i in items)
    return {s: c.get(s, 0) for s in STATUSES}


def _summary(as_of, model, scenarios, vectors, impacts, clients, rollups, result: ScenarioRunResult, audit_name: str) -> dict:
    detail = {}
    for s in scenarios:
        sid = s.scenario_id
        v, r = vectors.get(sid), rollups.get(sid)
        imps = [i for (k, _), i in impacts.items() if k == sid]
        cls = [c for (k, _), c in clients.items() if k == sid and c is not None]
        detail[sid] = {"vector": {"status": v.status, "channels": len(v.channels), "gaps": len(v.gaps)} if v else None,
                       "impacts": {"count": len(imps), "status_counts": _count(imps), "failed": sorted(i.portfolio_id for i in imps if i.status == "insufficient_data")},
                       "clients": {"count": len(cls), "status_counts": _count(cls)},
                       "rollup": {"status": r.status, "coverage": r.coverage.model_dump()} if r else None}
    return {"as_of": as_of.isoformat(), "model": model, "scenarios": detail, "audit_log": audit_name,
            "failures": [{"unit": f.unit, "error": f.error} for f in result.failures], "rejected_scenarios": result.rejected}


def _merge(path: Path, new: dict) -> dict:
    """A run limited to some scenarios keeps what an earlier run recorded for the others."""
    if not path.is_file():
        return new
    try:
        old = json.loads(path.read_text())
    except json.JSONDecodeError:
        return new
    return {**new, "scenarios": {**(old.get("scenarios") or {}), **new["scenarios"]}}


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="rm-dashboard-scenarios",
                                description="Compute the scenarios as of a date: a market shock vector per scenario, the impact on every portfolio, and "
                                            "the client and RM-book roll-ups. A result changes only when its inputs have.")
    p.add_argument("--as-of", required=True, type=date.fromisoformat, metavar="YYYY-MM-DD", help="analysis date (required)")
    p.add_argument("--scenario", action="append", metavar="ID", help="scenario id; repeat or comma-separate (default: every scenario in the catalogue)")
    p.add_argument("--portfolio", action="append", metavar="ID", help="portfolio id; repeat or comma-separate (default: every portfolio)")
    p.add_argument("--db", help="seeded SQLite database (or set RM_DASHBOARD_DB)")
    p.add_argument("--reports-dir", default="reports", help="folder holding <as-of>/scenarios/ and scenarios/catalogue.json (default: reports)")
    p.add_argument("--concurrency", type=int, help="units processed in parallel (default: RM_MAX_CONCURRENCY or 2)")
    p.add_argument("--force", action="store_true", help="regenerate even when the inputs are the same")
    return p.parse_args(argv)


def _ids(values: list[str] | None) -> list[str] | None:
    out = [i.strip() for v in values or [] for i in v.split(",") if i.strip()]
    return out or None


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
    with open_registry(settings, with_peer=False, reports_dir=args.reports_dir) as registry:
        try:
            result = run_scenarios(registry, as_of=args.as_of, reports_dir=Path(args.reports_dir), settings=settings, force=args.force,
                                   scenario_ids=_ids(args.scenario), portfolio_ids=_ids(args.portfolio))
        except ValueError as e:
            print(f"error: {e}", file=sys.stderr)
            return 2
    for msg in result.rejected:
        print(f"warning: {msg}", file=sys.stderr)
    if result.untouched:
        print(f"scenarios for {args.as_of} already exist with the same inputs: unchanged ({result.out_dir})")
        return 0
    made = ", ".join(f"{n} {k}" for k, n in result.produced.items() if n) or "nothing new"
    kept = ", ".join(f"{n} {k}" for k, n in result.skipped.items() if n)
    print(f"scenario results written to {result.out_dir}: {made}" + (f"; unchanged: {kept}" if kept else "") + f"; model: {settings.model_name}")
    for f in result.failures:
        print(f"failed: {f.unit}: {f.error}", file=sys.stderr)
    return 1 if result.failures else 0


if __name__ == "__main__":
    sys.exit(main())
