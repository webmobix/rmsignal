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
