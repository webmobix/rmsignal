# Domain contracts

Defined in `rm_dashboard.domain`. All models are pydantic v2.

## Entities

`Party`, `Person`, `Relationship`, `Client`, `Portfolio`, `Position`, `Instrument`, `Event`.
The dataset has no persons, related parties or news: those entities have schemas and
adapters that return `no_data`, so richer sources can be added without changing consumers.
Attributes without history carry `pit: current_only`.

## ToolResult (evidence envelope)

Every tool returns one. `evidence_id` is a hash of the content (never supplied by the
caller), so the same call on the same data yields the same id and a different `as_of`
resolving to different data yields a different id. Any status other than `ok`
(`partial`, `insufficient_data`, `insufficient_history`, `no_data`) requires a `reason`.

```json tool-result
{
  "data": {"weight_pct": 12.5},
  "as_of": "2026-08-26",
  "effective_snapshot_date": "2026-08-26",
  "gap_days": 0,
  "status": "ok",
  "sources": [{"dataset": "holdings", "key": "PF-0001/SYN-EQ-0001", "snapshot_date": "2026-08-26"}],
  "computation": {"tool": "portfolio.weights", "version": "1", "parameters": {"portfolio_id": "PF-0001"}, "method": "market value / portfolio total"},
  "flags": [{"code": "stale_mark", "message": "valuation 2026-06-30 before snapshot 2026-08-26", "subject": "SYN-AL-0308"}]
}
```

## Report

Delivered by every run. A `Finding` must cite at least one evidence id.
`status` is `complete`, `partial` or `insufficient_data`; gaps explain anything missing.

```json report
{
  "subject": "CL-0001",
  "as_of": "2026-08-26",
  "status": "partial",
  "agent": "relationship_analyst",
  "findings": [{"claim": "Equity weight is above the mandate maximum.", "confidence": "high", "evidence_ids": ["ev_0123456789abcdef"]}],
  "gaps": [{"kind": "no_data", "description": "Related-party data unavailable", "subject": "relationships"}],
  "flags": [],
  "policy_decisions": [{"checkpoint": "run_start", "decision": "allow", "reason": "mock policy engine", "policy_id": "mock", "mock": true}]
}
```

## Later stages

The stages after the batch read the persisted `Report` and write their own contracts under `reports/<as_of>/`. Every one is
always delivered (`complete`, `partial` or `insufficient_data`, with gaps) and carries the policy decisions of its run.
Finding references (`CL-0001#f7`, `CL-0001/PF-0001#f3`) are 1-based positions in the report tree; evidence ids are copied by
code from the finding they come from, never taken from a model.

### Reconciliation (`reconciliation/<client>.json`)

One result per RM note dated on or before `as_of`. `kind` is the source being reconciled: `rm_note` only for now
(mandate reconciliation is a later, separate stage). `verdict` is `consistent`, `contradicted` or `unverifiable`; the first
two need evidence.

```json reconciliation
{
  "client_id": "CL-0001",
  "as_of": "2026-08-26",
  "status": "complete",
  "agent": "note_reconciler",
  "results": [{
    "kind": "rm_note", "note_id": "N-001", "note_date": "2026-01-08",
    "note_quote": "Did not want to discuss reducing the legacy shareholding.",
    "verdict": "contradicted", "rationale": "The legacy energy name is still 42.61% of the client's assets.",
    "finding_refs": ["CL-0001#f5"], "evidence_ids": ["ev_0123456789abcdef"]
  }],
  "gaps": [],
  "policy_decisions": []
}
```

### Client actions (`actions/<client>.json`)

`category` is one of `compliance_kyc`, `concentration_risk`, `mandate_drift`, `liquidity_cash_needs`, `credit_collateral`,
`client_contact`, `data_quality`; `importance` one of `critical`, `high`, `medium`, `low` (a raise to the rubric floor is kept in
`importance_raised_from`); `horizon` one of `immediate`, `within_30_days`, `within_90_days`, `later`, `none`, derived with
`due_date` from dates in the linked evidence. `sources` are finding refs (`kind: finding`) or note ids (`kind: note`).

```json client-actions
{
  "client_id": "CL-0001",
  "as_of": "2026-08-26",
  "status": "complete",
  "agent": "client_actions",
  "actions": [{
    "rank": 1, "title": "Discuss the single-name concentration",
    "what": "Review the largest single-name exposure with the client and agree on a diversification path.",
    "why": "One energy name is 42.61% of the client's assets.",
    "category": "concentration_risk", "importance": "high", "importance_raised_from": "medium",
    "horizon": "none", "due_date": null,
    "sources": [{"kind": "finding", "ref": "CL-0001#f5", "report_path": "CL-0001", "evidence_ids": ["ev_0123456789abcdef"]}]
  }],
  "not_actioned": [],
  "gaps": [],
  "policy_decisions": []
}
```

### RM overview (`overview/<rm_id>.json`)

All client actions of one RM, ranked (importance, horizon, due date, client AUM descending, client id, title). Content
is copied from the client actions; `origin` is `coverage` for a `data_quality` action made by code for a client whose report
or actions are missing. `clients_without_actions` gives each such client a reason: `actions_missing`, `report_missing` or
`no_action_needed`. `summary` and `themes` come from the optional briefing and are empty if it was rejected or failed.

```json overview
{
  "rm_id": "RM-SG-014",
  "rm_name": "Priscilla Ong",
  "as_of": "2026-08-26",
  "status": "complete",
  "agent": "rm_overview",
  "summary": "",
  "themes": [],
  "actions": [{
    "rank": 1, "action_id": "CL-0001-A1", "origin": "client_actions", "client_id": "CL-0001", "client_name": "Hartono Wijaya Kusuma",
    "title": "Discuss the single-name concentration",
    "what": "Review the largest single-name exposure with the client and agree on a diversification path.",
    "why": "One energy name is 42.61% of the client's assets.",
    "category": "concentration_risk", "importance": "high", "horizon": "none", "due_date": null,
    "sources": [{"kind": "finding", "ref": "CL-0001#f5", "report_path": "CL-0001", "evidence_ids": ["ev_0123456789abcdef"]}]
  }],
  "by_category": [{"category": "concentration_risk", "count": 1, "action_ids": ["CL-0001-A1"]}],
  "clients_without_actions": [{"client_id": "CL-0002", "client_name": "Example Client", "reason": "no_action_needed"}],
  "clients": ["CL-0001", "CL-0002"],
  "gaps": [],
  "policy_decisions": []
}
```
