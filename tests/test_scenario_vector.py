from datetime import date

import pytest

from rm_dashboard.agents import StubChatModel
from rm_dashboard.policy import AuditLog, ScriptedEngine
from rm_dashboard.scenarios import SEED_SCENARIOS, ScenarioRecord
from rm_dashboard.scenarios.agent import current_hash, produce_shock_vector, vector_hash
from rm_dashboard.scenarios.channels import vocabulary
from rm_dashboard.scenarios.contracts import NOT_ANCHORED
from rm_dashboard.scenarios.store import ScenarioStore

AS_OF = date(2026, 8, 26)
DETERIORATION = next(s for s in SEED_SCENARIOS if s.scenario_id == "gulf-deterioration")


def run(registry, tmp_path, mode="normal", scenario=DETERIORATION, as_of=AS_OF, **kw):
    store = ScenarioStore(tmp_path)
    models = lambda role: StubChatModel(role=role, mode=mode)  # noqa: E731
    return produce_shock_vector(registry, scenario=scenario, as_of=as_of, store=store, models=models, model_name="stub", **kw)


def vocab(registry, as_of=AS_OF):
    return [c.channel for c in vocabulary(registry.ctx.repo.instruments(as_of=as_of).frame.to_dicts())]


def test_a_vector_has_best_likely_worst_for_each_channel_of_the_data(registry, tmp_path):
    v, evidence = run(registry, tmp_path)
    assert v.status == "complete" and not v.gaps and v.horizon_months == 3
    assert [c.channel for c in v.channels] == vocab(registry)
    for c in v.channels:
        assert c.worst <= c.likely <= c.best and c.rationale and c.explainer and c.evidence_ids
    assert v.summary and "not a probability" in v.not_a_probability
    assert {e.evidence_id for e in evidence} >= {i for c in v.channels for i in c.evidence_ids}
    assert v.vector_hash == vector_hash(v.channels) and v.inputs_hash


def test_a_move_is_anchored_to_the_mirrored_event_or_says_it_is_not(registry, tmp_path):
    v, _ = run(registry, tmp_path)
    c = v.channels[0]
    assert c.anchored_event and c.anchored_event.event_date == date(2026, 8, 5) and c.anchor_note == ""
    plain = ScenarioRecord(scenario_id="plain", name="Plain", premise="Something new happens.")
    v2, _ = run(registry, tmp_path, scenario=plain)
    assert all(c.anchored_event is None and c.anchor_note == NOT_ANCHORED for c in v2.channels)


def test_misordered_values_are_reordered_by_code_and_recorded(registry, tmp_path):
    v, _ = run(registry, tmp_path, "misordered")
    first = v.channels[0]
    assert first.worst <= first.likely <= first.best and first.best == 4.0  # the model's likely (4.0) is now the best
    assert v.status == "partial" and any("reordered" in g.description and g.subject == first.channel for g in v.gaps)


def test_an_uncited_move_is_removed(registry, tmp_path):
    v, _ = run(registry, tmp_path, "uncited")
    gone = vocab(registry)[0]
    assert gone not in [c.channel for c in v.channels] and v.status == "partial"
    assert any(g.subject == gone and "no evidence" in g.description for g in v.gaps)


def test_a_single_instrument_move_is_removed(registry, tmp_path):
    v, _ = run(registry, tmp_path, "single")
    assert "SYN-EQ-0001" not in [c.channel for c in v.channels]
    assert any("single instrument" in g.description for g in v.gaps) and v.status == "partial"


def test_a_figure_that_is_not_in_the_evidence_removes_the_move(registry, tmp_path):
    v, _ = run(registry, tmp_path, "bad_figure")
    assert vocab(registry)[0] not in [c.channel for c in v.channels]
    assert any("98765" in g.description for g in v.gaps)


def test_model_failure_still_returns_a_vector_without_channels(registry, tmp_path):
    v, evidence = run(registry, tmp_path, "raise")
    assert v.channels == [] and v.status == "insufficient_data" and evidence == []
    assert any("stub model failure" in g.description for g in v.gaps)


def test_unusable_output_is_a_gap_not_a_vector(registry, tmp_path):
    v, _ = run(registry, tmp_path, "unparsable")
    assert v.channels == [] and v.status == "insufficient_data" and any(g.kind == "agent_error" for g in v.gaps)


def test_only_evidence_dated_on_or_before_the_date_is_used(registry, tmp_path):
    early = date(2026, 3, 31)
    v, evidence = run(registry, tmp_path, as_of=early)
    assert v.as_of == early and v.channels
    assert all(e.as_of == early for e in evidence)
    for e in evidence:
        for ev in (e.data or {}).get("news", []) if isinstance(e.data, dict) else []:
            assert date.fromisoformat(str(ev["event_date"])) <= early
    assert all(c.anchored_event is None for c in v.channels)  # the mirrored 2026-08-05 event did not exist yet


def test_a_policy_denial_is_a_gap_not_an_error(registry, tmp_path):
    v, _ = run(registry, tmp_path, engine=ScriptedEngine({"request_entitlement": "deny"}))
    assert v.status == "insufficient_data" and v.channels == [] and any(g.kind == "policy_denied" for g in v.gaps)


def test_the_run_is_audited(registry, tmp_path):
    audit = AuditLog()
    run(registry, tmp_path, audit=audit)
    kinds = [r.kind for r in audit.records]
    assert "tool_call" in kinds and any(r.detail.get("checkpoint") == "request_entitlement" for r in audit.records)


def test_hash_follows_scenario_text_and_model(registry):
    repo = registry.ctx.repo
    a = current_hash(repo, DETERIORATION, AS_OF, "m1")
    assert a == current_hash(repo, DETERIORATION, AS_OF, "m1")
    assert a != current_hash(repo, DETERIORATION.model_copy(update={"premise": "Edited."}), AS_OF, "m1")
    assert a != current_hash(repo, DETERIORATION, AS_OF, "m2") and a != current_hash(repo, DETERIORATION, date(2026, 6, 30), "m1")


def test_store_round_trip_touches_only_its_scenario_and_date(registry, tmp_path):
    v, evidence = run(registry, tmp_path)
    store = ScenarioStore(tmp_path)
    store.save_vector(v, evidence)
    assert store.load_vector(AS_OF, "gulf-deterioration") == v and store.load_vector(date(2026, 6, 30), "gulf-deterioration") is None
    assert [e.evidence_id for e in store.load_vector_evidence(AS_OF, "gulf-deterioration")] == [e.evidence_id for e in evidence]
    assert store.scenario_ids(AS_OF) == ["gulf-deterioration"]
    assert sorted(p.name for p in tmp_path.rglob("*") if p.is_file()) == ["vector.json", "vector.json"]
