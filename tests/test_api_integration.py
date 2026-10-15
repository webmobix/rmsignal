"""Every read endpoint for every id, and proof that the API writes nothing."""

import hashlib
from pathlib import Path

import pytest


def _digest(root: Path) -> dict[str, str]:
    files = [root] if root.is_file() else [p for p in sorted(root.rglob("*")) if p.is_file()]
    return {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}


def _all_paths(api):
    cids = [c["client_id"] for c in api.get("/api/clients").json()]
    pids = sorted({p["portfolio_id"] for cid in cids for p in api.get(f"/api/clients/{cid}").json()["portfolios"]})
    iids = [i["instrument_id"] for i in api.get("/api/instruments").json()]
    paths = ["/api/as-of", "/api/rm", "/api/overview", "/api/clients", "/api/instruments", "/api/market-outlook",
             "/api/events", "/api/scenarios"]
    for cid in cids:
        paths += [f"/api/clients/{cid}", f"/api/clients/{cid}/aum-history", f"/api/clients/{cid}/snapshot-changes",
                  f"/api/clients/{cid}/scenarios"]
    paths += [f"/api/portfolios/{p}" for p in pids] + [f"/api/instruments/{i}" for i in iids]
    return paths, cids


def test_every_endpoint_answers_for_every_id(api):
    paths, cids = _all_paths(api)
    assert len(cids) == 20 and len(paths) > 150
    bad = {p: api.get(p).status_code for p in paths if api.get(p).status_code != 200}
    assert not bad


def test_every_evidence_id_in_the_overview_resolves(api):
    refs = [e for a in api.get("/api/overview").json()["actions"] for r in a["refs"] for e in r["evidence_ids"]]
    assert refs
    bad = [e for e in set(refs) if api.get(f"/api/evidence/{e}").status_code != 200]
    assert not bad


def test_openapi_has_a_response_schema_for_every_read_endpoint(api):
    spec = api.get("/openapi.json").json()
    for path, ops in spec["paths"].items():
        if path.startswith("/api/sources"):
            continue
        assert set(ops) == {"get"}, path
        ok = ops["get"]["responses"]["200"]["content"]["application/json"]["schema"]
        assert ok.get("$ref") or ok.get("items") or ok.get("type"), path


def test_nothing_is_written_to_the_database_or_the_reports(api, seeded_db, reports_dir):
    before = (_digest(seeded_db), _digest(reports_dir))
    paths, _ = _all_paths(api)
    for p in paths:
        api.get(p)
    api.get("/api/sources/clients")
    assert (_digest(seeded_db), _digest(reports_dir)) == before


def test_sources_endpoints_are_unchanged(api):
    cat = {t["table"]: t["count"] for t in api.get("/api/sources").json()}
    assert cat["clients"] == 20 and cat["holdings"] == 1015 and len(cat) == 12
    assert api.get("/api/sources/portfolios/PF-0001").json()["client_id"] == "CL-0001"
    assert api.get("/api/sources/nope").status_code == 404
    assert api.post("/api/sources/clients").status_code == 405
