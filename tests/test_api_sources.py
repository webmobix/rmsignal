import pytest
from fastapi.testclient import TestClient

from rm_dashboard.api import create_app

TABLES = {
    "clients", "portfolios", "holdings", "instruments", "mandates", "transactions",
    "credit_facilities", "commitments", "planned_cash_needs", "market_context",
    "event_log", "rm_notes",
}


@pytest.fixture
def client(seeded_db):
    return TestClient(create_app(seeded_db))


def test_catalogue(client):
    r = client.get("/api/sources")
    assert r.status_code == 200
    body = {t["table"]: t for t in r.json()}
    assert set(body) == TABLES
    assert body["clients"]["count"] == 20
    assert body["mandates"]["primary_key"] == ["mandate_code", "asset_class"]
    assert {"name": "age", "type": "int", "nullable": True} in body["clients"]["columns"]


def test_default_and_explicit_page(client):
    r = client.get("/api/sources/clients").json()
    assert r["total"] == 20 and len(r["rows"]) == 20 and r["limit"] == 100
    total = client.get("/api/sources/transactions").json()["total"]
    page = client.get("/api/sources/transactions?limit=5&offset=10").json()
    assert len(page["rows"]) == 5 and page["total"] == total and page["offset"] == 10
    full = client.get("/api/sources/transactions?limit=1000").json()["rows"]
    assert page["rows"] == full[10:15]


@pytest.mark.parametrize("q", ["limit=0", "limit=1001", "offset=-1", "limit=abc"])
def test_invalid_paging(client, q):
    assert client.get(f"/api/sources/clients?{q}").status_code == 422


def test_filters(client):
    r = client.get("/api/sources/portfolios?client_id=CL-0001").json()
    assert r["total"] == len(r["rows"]) > 0
    assert all(p["client_id"] == "CL-0001" for p in r["rows"])
    # total reflects the filter, not the page
    r = client.get("/api/sources/portfolios?client_id=CL-0001&limit=1").json()
    assert len(r["rows"]) == 1
    assert r["total"] == client.get("/api/sources/portfolios?client_id=CL-0001").json()["total"]


def test_typed_filters(client):
    pep = client.get("/api/sources/clients?pep_status=true").json()
    nope = client.get("/api/sources/clients?pep_status=false").json()
    assert pep["total"] + nope["total"] == 20
    assert all(c["pep_status"] is True for c in pep["rows"])
    c = client.get("/api/sources/clients/CL-0001").json()
    by_date = client.get(f"/api/sources/clients?kyc_review_due={c['kyc_review_due']}").json()
    assert c in by_date["rows"]
    assert client.get("/api/sources/clients?kyc_review_due=garbage").status_code == 422


def test_unknown_filter_and_table(client):
    r = client.get("/api/sources/clients?nope=1")
    assert r.status_code == 422 and "nope" in r.json()["detail"]
    r = client.get("/api/sources/nope")
    assert r.status_code == 404 and "clients" in r.json()["detail"]
    assert client.get("/api/sources/nope/x").status_code == 404


def test_get_by_key(client):
    r = client.get("/api/sources/portfolios/PF-0001")
    assert r.status_code == 200 and r.json()["portfolio_id"] == "PF-0001"
    assert client.get("/api/sources/portfolios/PF-NOPE").status_code == 404


def test_composite_key(client):
    m = client.get("/api/sources/mandates").json()["rows"][0]
    r = client.get(f"/api/sources/mandates/{m['mandate_code']}/{m['asset_class']}")
    assert r.status_code == 200 and r.json() == m
    assert client.get(f"/api/sources/mandates/{m['mandate_code']}").status_code == 404
    assert client.get(f"/api/sources/mandates/{m['mandate_code']}/a/b").status_code == 404


def test_keyless_table(client):
    assert client.get("/api/sources/holdings/anything").status_code == 404
    assert client.get("/api/sources/event_log/anything").status_code == 404


def test_typed_json_values(client):
    c = client.get("/api/sources/clients/CL-0001").json()
    assert c["pep_status"] is False and isinstance(c["total_aum_usd"], float)
    assert isinstance(c["client_since"], str) and len(c["client_since"]) == 10
    rows = client.get("/api/sources/clients").json()["rows"]
    assert any(r["age"] is None for r in rows)
    p = client.get("/api/sources/portfolios/PF-0001").json()
    assert any(k.startswith("aum_2026_") for k in p)


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
@pytest.mark.parametrize("path", ["/api/sources", "/api/sources/clients", "/api/sources/clients/CL-0001"])
def test_write_methods_rejected(client, method, path):
    assert getattr(client, method)(path).status_code == 405


def test_missing_database(tmp_path):
    with pytest.raises(FileNotFoundError, match="rm-dashboard-seed"):
        create_app(tmp_path / "nope.db")


def test_serve_missing_database_exits_with_seed_hint(tmp_path, monkeypatch):
    from rm_dashboard.api import serve

    monkeypatch.delenv("RM_DASHBOARD_DB", raising=False)
    with pytest.raises(SystemExit) as exc:
        serve.main(["--db", str(tmp_path / "nope.db")])
    assert "rm-dashboard-seed" in str(exc.value)


def test_serve_runs_app_with_db_from_env(seeded_db, monkeypatch):
    from rm_dashboard.api import serve

    calls = {}
    monkeypatch.setattr(serve.uvicorn, "run", lambda app, **kw: calls.update(app=app, **kw))
    monkeypatch.setenv("RM_DASHBOARD_DB", str(seeded_db))
    serve.main(["--port", "9000"])
    assert calls["host"] == "127.0.0.1" and calls["port"] == 9000
    assert TestClient(calls["app"]).get("/docs").status_code == 200


def test_docs_page_uses_local_assets(client):
    page = client.get("/docs")
    assert page.status_code == 200
    assert "http" not in page.text.split("<body>")[0].replace("http-equiv", "")
    assert "cdn" not in page.text
    for path in ("/static/swagger/swagger-ui.css", "/static/swagger/swagger-ui-bundle.js"):
        assert client.get(path).status_code == 200
