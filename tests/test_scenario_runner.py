from datetime import date

import pytest
from storehelp import snapshot

from rm_dashboard.agents import StubChatModel
from rm_dashboard.runners import open_registry
from rm_dashboard.runners import scenarios as runner
from rm_dashboard.runners.scenarios import main, run_scenarios
from rm_dashboard.scenarios import CatalogueStore, ScenarioRecord
from rm_dashboard.scenarios.store import ScenarioStore
from rm_dashboard.settings import Settings
from rm_dashboard.store import Kind
from rm_dashboard.store.audit import read_audit
from rm_dashboard.store.summary import get_summary

AS_OF = date(2026, 8, 26)
PFS = ["PF-0001", "PF-0002", "PF-0003"]  # CL-0001 has two portfolios, CL-0002 one


class Models:
    def __init__(self, **modes):
        self.made, self.modes = [], modes

    def __call__(self, role):
        m = StubChatModel(role=role, mode=self.modes.get(role, "normal"))
        self.made.append(m)
        return m

    @property
    def calls(self):
        return sum(m.calls for m in self.made)


@pytest.fixture(scope="module")
def reg(seeded_db):
    with open_registry(Settings(db_path=str(seeded_db)), with_peer=False) as r:
        yield r


def run(reg, tmp_path, models=None, scenario="gulf-deterioration", portfolios=PFS, **kw):
    models = models or Models()
    ids = [scenario] if isinstance(scenario, str) else scenario
    return run_scenarios(reg, as_of=AS_OF, store=tmp_path, models=models, scenario_ids=ids, portfolio_ids=portfolios, **kw), models


def files(root, scenario=None):
    """Everything saved, minus the audit trail (which only grows); optionally only one scenario's results."""
    snap = snapshot(root, skip=(Kind.AUDIT,))
    return {k: v for k, v in snap.items() if scenario is None or (k[1].startswith("scenario-") and k[2].split("/")[0] == scenario
                                                                    and k[1] != "scenario-catalogue")}


def test_a_run_saves_vector_impacts_roll_ups_evidence_summary_and_audit(reg, tmp_path):
    res, _ = run(reg, tmp_path)
    store = ScenarioStore(tmp_path).store
    sid = "gulf-deterioration"
    assert store.keys(AS_OF, Kind.SCENARIO_VECTOR) == [sid] and store.keys(AS_OF, Kind.SCENARIO_ROLLUP) == [sid]
    assert store.keys(AS_OF, Kind.SCENARIO_IMPACT) == [f"{sid}/PF-0001", f"{sid}/PF-0002", f"{sid}/PF-0003"]
    assert store.keys(AS_OF, Kind.SCENARIO_CLIENT) == [f"{sid}/CL-0001", f"{sid}/CL-0002"]
    assert store.keys(AS_OF, Kind.EVIDENCE_INDEX, f"scenario-vector/{sid}")
    assert get_summary(store, AS_OF, "scenarios") and read_audit(store, AS_OF, "scenarios") and CatalogueStore(tmp_path).exists()
    assert not [p for p in tmp_path.rglob("*.json")]  # no per-artifact files
    assert res.produced == {"vector": 1, "impact": 3, "client": 2, "rollup": 1} and not res.failures
    s = get_summary(store, AS_OF, "scenarios")
    assert s["model"] == "stub" and s["scenarios"]["gulf-deterioration"]["impacts"]["count"] == 3 and s["scenarios"]["gulf-deterioration"]["vector"]["status"] == "complete"
    roll = ScenarioStore(tmp_path).load_rollup(AS_OF, "gulf-deterioration")
    assert roll.coverage.computed == 2 and roll.coverage.total == 20 and roll.status == "partial" and roll.rm_id == "RM-SG-014"


def test_the_audit_lists_run_start_and_tool_calls(reg, tmp_path):
    res, _ = run(reg, tmp_path)
    trail = read_audit(res.store, AS_OF, "scenarios")
    assert {"decision", "tool_call"} <= {r["kind"] for r in trail}
    decisions = {r.get("detail", {}).get("checkpoint") for r in trail}
    assert "request_entitlement" in decisions


def test_same_inputs_make_no_model_call_and_change_no_file(reg, tmp_path):
    run(reg, tmp_path)
    before = files(tmp_path)
    res, models = run(reg, tmp_path)
    assert models.calls == 0 and res.untouched and files(tmp_path) == before
    assert sum(res.skipped.values()) == 1 + 3 + 2 + 1


def test_force_regenerates(reg, tmp_path):
    run(reg, tmp_path)
    res, models = run(reg, tmp_path, force=True)
    assert models.calls > 0 and res.produced["vector"] == 1 and res.produced["impact"] == 3


def test_an_edited_premise_regenerates_the_vector_and_every_dependent_impact(reg, tmp_path):
    run(reg, tmp_path)
    store = CatalogueStore(tmp_path)
    s = store.load().get("gulf-deterioration")
    store.add(s.model_copy(update={"premise": s.premise + " Insurers withdraw cover."}))
    res, models = run(reg, tmp_path)
    assert res.produced["vector"] == 1 and res.produced["impact"] == 3 and res.produced["client"] == 2 and res.produced["rollup"] == 1 and models.calls > 0


def test_adding_a_scenario_from_text_runs_only_that_scenario(reg, tmp_path):
    run(reg, tmp_path)
    before = files(tmp_path, "gulf-deterioration")
    CatalogueStore(tmp_path).add(ScenarioRecord(scenario_id="taiwan-strait", name="Taiwan Strait", premise="Shipping lanes around Taiwan close."))
    res, _ = run(reg, tmp_path, scenario=["gulf-deterioration", "taiwan-strait"])
    assert res.produced == {"vector": 1, "impact": 3, "client": 2, "rollup": 1}
    assert files(tmp_path, "gulf-deterioration") == before
    assert ScenarioStore(tmp_path).scenario_ids(AS_OF) == ["gulf-deterioration", "taiwan-strait"]
    s = get_summary(ScenarioStore(tmp_path).store, AS_OF, "scenarios")
    assert set(s["scenarios"]) == {"gulf-deterioration", "taiwan-strait"}


def test_an_interrupted_run_resumes_with_only_the_missing_units(reg, tmp_path):
    run(reg, tmp_path)
    store = ScenarioStore(tmp_path).store
    store.delete_prefix(AS_OF, Kind.SCENARIO_IMPACT, "gulf-deterioration/PF-0002")
    store.delete_prefix(AS_OF, Kind.SCENARIO_CLIENT, "gulf-deterioration/CL-0001")
    store.delete_prefix(AS_OF, Kind.SCENARIO_ROLLUP, "gulf-deterioration")
    res, _ = run(reg, tmp_path)
    assert res.produced == {"impact": 1, "client": 1, "rollup": 1} and res.skipped["vector"] == 1 and res.skipped["impact"] == 2
    assert store.get(AS_OF, Kind.SCENARIO_IMPACT, "gulf-deterioration/PF-0002") and store.get(AS_OF, Kind.SCENARIO_ROLLUP, "gulf-deterioration")


def test_one_failing_unit_does_not_stop_the_others(reg, tmp_path, monkeypatch):
    real = runner.produce_portfolio_impact

    def flaky(registry, **kw):
        if kw["portfolio_id"] == "PF-0003":
            raise RuntimeError("model gateway down")
        return real(registry, **kw)

    monkeypatch.setattr(runner, "produce_portfolio_impact", flaky)
    res, _ = run(reg, tmp_path)
    store = ScenarioStore(tmp_path)
    assert [f.unit for f in res.failures] == ["impact gulf-deterioration x PF-0003"] and "model gateway down" in res.failures[0].error
    assert store.load_impact(AS_OF, "gulf-deterioration", "PF-0001").status != "insufficient_data"
    failed = store.load_impact(AS_OF, "gulf-deterioration", "PF-0003")
    assert failed.status == "insufficient_data" and "model gateway down" in failed.gaps[0].description
    s = get_summary(res.store, AS_OF, "scenarios")
    assert s["failures"][0]["unit"].endswith("PF-0003") and s["scenarios"]["gulf-deterioration"]["impacts"]["failed"] == ["PF-0003"]
    assert store.load_client(AS_OF, "gulf-deterioration", "CL-0001").status != "insufficient_data"
    monkeypatch.setattr(runner, "produce_portfolio_impact", real)
    again, _ = run(reg, tmp_path)  # the failed unit is retried, the finished ones are not
    assert again.produced["impact"] == 1 and not again.failures


def test_a_model_failure_in_a_unit_is_a_gap_in_that_unit_only(reg, tmp_path):
    res, _ = run(reg, tmp_path, models=Models(scenario_impact="raise"))
    imp = ScenarioStore(tmp_path).load_impact(AS_OF, "gulf-deterioration", "PF-0001")
    assert imp.status == "partial" and imp.cases and any(g.kind == "agent_error" for g in imp.gaps)


def test_filters_reject_unknown_ids(reg, tmp_path):
    with pytest.raises(ValueError, match="unknown scenario"):
        run(reg, tmp_path, scenario="no-such")
    with pytest.raises(ValueError, match="unknown portfolio"):
        run(reg, tmp_path, portfolios=["PF-9999"])


def test_other_dates_are_never_touched(reg, tmp_path):
    store = ScenarioStore(tmp_path).store
    other = date(2026, 6, 30)
    store.put(other, Kind.SCENARIO_ROLLUP, "x", "keep")
    run(reg, tmp_path)
    assert store.get(other, Kind.SCENARIO_ROLLUP, "x") == "keep" and not store.keys(other, Kind.RUN_SUMMARY)


def test_command_line(seeded_db, tmp_path, capsys):
    argv = ["--as-of", "2026-08-26", "--db", str(seeded_db), "--reports-dir", str(tmp_path), "--scenario", "gulf-deterioration",
            "--portfolio", "PF-0003"]
    assert main(argv) == 0
    out = capsys.readouterr().out
    assert "1 vector" in out and "1 impact" in out and "model: stub" in out
    assert main(argv) == 0 and "unchanged" in capsys.readouterr().out
    assert main(["--as-of", "2026-08-26", "--db", str(seeded_db), "--reports-dir", str(tmp_path), "--scenario", "nope"]) == 2
