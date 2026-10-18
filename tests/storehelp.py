"""Helpers for tests that need to look into, or change, what a run saved."""

import json
from datetime import date

from rm_dashboard.store import Kind, as_store


def mark_run(base, day: str) -> None:
    """Make a date exist in the store, as an empty run folder used to."""
    as_store(base).put(date.fromisoformat(day), Kind.RUN_SUMMARY, "analyse", "{}")


def saved(base, day: str, kind: Kind) -> dict:
    """Every body of a kind and date, by key."""
    store = as_store(base)
    d = date.fromisoformat(day)
    return {k: store.get(d, kind, k) for k in store.keys(d, kind)}


def saved_json(base, day: str, kind: Kind, key: str):
    body = as_store(base).get(date.fromisoformat(day), kind, key)
    return None if body is None else json.loads(body)


def snapshot(base, *, skip: tuple[Kind, ...] = ()) -> dict:
    """Everything in the store: (as_of, kind, key) -> body."""
    from rm_dashboard.store import GLOBAL

    store = as_store(base)
    out = {}
    for d in [GLOBAL, *store.dates()]:
        for kind in Kind:
            if kind not in skip:
                for k in store.keys(d, kind):
                    out[(d.isoformat(), str(kind), k)] = store.get(d, kind, k)
    return out


_STAGE_FOLDERS = {Kind.RECONCILIATION: ("reconciliation", "reconcile"), Kind.MANDATE_RECONCILIATION: ("mandate-reconciliation", "mandate-reconcile"),
                  Kind.ACTIONS: ("actions", "actions"), Kind.OVERVIEW: ("overview", "overview")}


def export_folder(base, root) -> None:
    """Write a store's artifacts as the old ``reports/<as_of>/...`` folder tree (the inverse of the loader's folder import)."""
    from pathlib import Path

    from rm_dashboard.store import GLOBAL
    from rm_dashboard.store import evidence as ev
    from rm_dashboard.store.audit import read_audit

    store, root = as_store(base), Path(root)

    def write(path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def evidence_json(d, ns, subject) -> str:
        return json.dumps([r.model_dump(mode="json") for r in ev.get_evidence(store, d, ns, subject) or []], default=str)

    def stage(folder: Path, d: date, name: str) -> None:
        summary = store.get(d, Kind.RUN_SUMMARY, name)
        if summary is not None:
            write(folder / "summary.json", summary)
        audit = read_audit(store, d, name)
        if audit:
            write(folder / "audit.jsonl", "".join(json.dumps(r, default=str) + "\n" for r in audit))

    cat = store.get(GLOBAL, Kind.SCENARIO_CATALOGUE, "catalogue")
    if cat is not None:
        write(root / "scenarios" / "catalogue.json", cat)
    for d in store.dates():
        run = root / d.isoformat()
        run.mkdir(parents=True, exist_ok=True)
        for k in store.keys(d, Kind.REPORT):
            write(run / f"{k}.json", store.get(d, Kind.REPORT, k))
            write(run / "evidence" / f"{k}.json", evidence_json(d, ev.REPORT, k))
        stage(run, d, "analyse")
        for kind, (folder, name) in _STAGE_FOLDERS.items():
            for k in store.keys(d, kind):
                write(run / folder / f"{k}.json", store.get(d, kind, k))
            stage(run / folder, d, name)
        out = run / "outlook"
        for k in store.keys(d, Kind.OUTLOOK_MARKET):
            write(out / "market.json", store.get(d, Kind.OUTLOOK_MARKET, k))
            write(out / "evidence" / "market.json", evidence_json(d, ev.OUTLOOK_MARKET, "market"))
        for k in store.keys(d, Kind.OUTLOOK_INSTRUMENT):
            write(out / "instruments" / f"{k}.json", store.get(d, Kind.OUTLOOK_INSTRUMENT, k))
            write(out / "evidence" / "instruments" / f"{k}.json", evidence_json(d, ev.OUTLOOK_INSTRUMENT, k))
        stage(out, d, "outlook")
        sc = run / "scenarios"
        for k in store.keys(d, Kind.SCENARIO_VECTOR):
            write(sc / k / "vector.json", store.get(d, Kind.SCENARIO_VECTOR, k))
            write(sc / k / "evidence" / "vector.json", evidence_json(d, ev.SCENARIO_VECTOR, k))
        for k in store.keys(d, Kind.SCENARIO_IMPACT):
            sid, pid = k.split("/", 1)
            write(sc / sid / "impacts" / f"{pid}.json", store.get(d, Kind.SCENARIO_IMPACT, k))
            if store.get(d, Kind.EVIDENCE_INDEX, f"{ev.SCENARIO_IMPACT}/{k}") is not None:
                write(sc / sid / "evidence" / "impacts" / f"{pid}.json", evidence_json(d, ev.SCENARIO_IMPACT, k))
        for k in store.keys(d, Kind.SCENARIO_CLIENT):
            sid, cid = k.split("/", 1)
            write(sc / sid / "clients" / f"{cid}.json", store.get(d, Kind.SCENARIO_CLIENT, k))
        for k in store.keys(d, Kind.SCENARIO_ROLLUP):
            write(sc / k / "rollup.json", store.get(d, Kind.SCENARIO_ROLLUP, k))
        stage(sc, d, "scenarios")
