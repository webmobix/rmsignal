import pytest
from fastapi.testclient import TestClient

from storehelp import mark_run

from rm_dashboard.api import create_app

def test_missing_reports_folder_names_the_path(seeded_db, tmp_path):
    with pytest.raises(FileNotFoundError, match="nope"):
        create_app(seeded_db, tmp_path / "nope")


def test_serve_fails_on_missing_reports(seeded_db, tmp_path, capsys):
    from rm_dashboard.api.serve import main

    with pytest.raises(SystemExit) as e:
        main(["--db", str(seeded_db), "--reports", str(tmp_path / "gone")])
    assert "gone" in str(e.value)


def test_empty_reports_folder(seeded_db, tmp_path):
    c = TestClient(create_app(seeded_db, tmp_path))
    assert c.get("/api/as-of").json() == {"as_of_dates": [], "latest": None}
    r = c.get("/api/rm")
    assert r.status_code == 404 and "rm-dashboard-analyse" in r.json()["detail"]


def test_without_reports_option_sources_still_work(seeded_db):
    c = TestClient(create_app(seeded_db))
    assert c.get("/api/sources").status_code == 200
    assert c.get("/api/rm").status_code == 404


def test_latest_is_newest_run_not_the_clock(seeded_db, tmp_path):
    for d in ("2026-03-31", "2026-08-26"):
        mark_run(tmp_path, d)
    c = TestClient(create_app(seeded_db, tmp_path))
    assert c.get("/api/as-of").json() == {"as_of_dates": ["2026-03-31", "2026-08-26"], "latest": "2026-08-26"}
    assert c.get("/api/rm?as_of=latest").json()["as_of"] == "2026-08-26"
    assert c.get("/api/rm?as_of=2026-03-31").json()["as_of"] == "2026-03-31"


def test_unknown_and_invalid_as_of(seeded_db, tmp_path):
    mark_run(tmp_path, "2026-08-26")
    c = TestClient(create_app(seeded_db, tmp_path))
    r = c.get("/api/rm?as_of=2026-01-01")
    assert r.status_code == 404 and "2026-08-26" in r.json()["detail"]
    assert c.get("/api/rm?as_of=banana").status_code == 422


def test_rm_profile(api):
    r = api.get("/api/rm").json()
    assert r["rm_name"] == "Priscilla Ong" and r["rm_id"] == "RM-SG-014"
    assert r["client_count"] == 20 and set(r["booking_centres"]) == {"Singapore", "Hong Kong"}


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
def test_read_api_is_read_only(api, method):
    for path in ("/api/rm", "/api/as-of", "/api/sources/clients"):
        assert getattr(api, method)(path).status_code == 405


def test_docs_list_new_endpoints(api):
    paths = api.get("/openapi.json").json()["paths"]
    assert "/api/rm" in paths and "/api/as-of" in paths
    assert "$ref" in paths["/api/rm"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
