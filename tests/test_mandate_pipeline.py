"""The whole batch order with the stub model: each stage reads what the previous one wrote."""

import json
from datetime import date

import pytest

from rm_dashboard.agents import StubChatModel
from rm_dashboard.runners import open_registry, run_batch
from rm_dashboard.runners.actions import run_actions
from rm_dashboard.runners.mandate_reconcile import run_mandate_reconcile
from rm_dashboard.runners.overview import run_overview
from rm_dashboard.runners.reconcile import run_reconcile
from rm_dashboard.settings import Settings
from rm_dashboard.store import Kind, as_store
from rm_dashboard.store.audit import read_audit
from rm_dashboard.store.summary import get_summary

AS_OF = date(2026, 8, 26)
CLIENTS = ["CL-0005", "CL-0007", "CL-0009", "CL-0012"]


def stub(role):
    return StubChatModel(role=role)


@pytest.fixture(scope="module")
def pipeline(seeded_db, tmp_path_factory):
    out = tmp_path_factory.mktemp("pipeline")
    with open_registry(Settings(db_path=str(seeded_db), max_concurrency=4)) as reg:
        run_batch(reg, as_of=AS_OF, store=out, client_ids=CLIENTS, models=stub)
        run_reconcile(reg, as_of=AS_OF, store=out, client_ids=CLIENTS, models=stub)
        mandate = run_mandate_reconcile(reg, as_of=AS_OF, store=out, client_ids=CLIENTS, models=stub)
        actions = run_actions(reg, as_of=AS_OF, store=out, client_ids=CLIENTS, models=stub)
        overview = run_overview(reg, as_of=AS_OF, store=out, models=stub)
    return as_store(out), mandate, actions, overview


def test_each_stage_reads_the_previous_output(pipeline):
    store, mandate, actions, overview = pipeline
    assert set(store.keys(AS_OF, Kind.MANDATE_RECONCILIATION)) == set(CLIENTS)
    assert get_summary(store, AS_OF, "mandate-reconcile") and read_audit(store, AS_OF, "mandate-reconcile")
    assert all(r.status == "complete" for r in mandate.reconciliations.values())
    # the analysis stage supplied the exclusion evidence the mandate stage reconciled
    ex = [r for r in mandate.reconciliations["CL-0005"].results if r.kind == "exclusion"]
    assert {r.key for r in ex} == {"SYN-EQ-0008", "SYN-ST-0105"}
    # actions link the mandate results of the previous stage, and no gap says they were missing
    for cid in ("CL-0005", "CL-0007"):
        res = actions.results[cid]
        linked = [s for a in res.actions for s in a.sources if s.kind == "mandate"]
        assert linked, cid
        assert not any("mandate breaches were not reconciled" in g.description for g in res.gaps)
    assert not any("mandate breaches were not reconciled" in g.description for g in actions.results["CL-0012"].gaps)
    waiver = next(a for a in actions.results["CL-0007"].actions if any(s.kind == "mandate" and s.mandate_status == "client_directed" for s in a.sources))
    assert "waiver" in waiver.what and waiver.importance == "high"


def test_overview_ranks_the_new_actions_and_links_resolve(pipeline):
    store, _, actions, overview = pipeline
    ov = json.loads(store.get(AS_OF, Kind.OVERVIEW, "RM-SG-014"))
    titles = {(a["client_id"], a["title"]) for a in ov["actions"]}
    assert ("CL-0007", "Review the client's instruction on the breach") in titles
    critical = [a for a in ov["actions"] if a["importance"] == "critical" and a["client_id"] == "CL-0005"]
    assert critical and ov["actions"][0]["importance"] == "critical" and ov["actions"][0]["rank"] == 1
    assert not any("link_broken" in g["description"] for g in ov["gaps"])
    assert any(s["kind"] == "mandate" for a in ov["actions"] for s in a["sources"])
