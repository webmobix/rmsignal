# Policy checkpoints

Policy checks go through one interface, `PolicyEngine.check(checkpoint, context) -> Decision`
(`allow | deny | escalate`, with a reason and policy id). The shipped `MockPolicyEngine` allows
everything and labels each decision `mock`, which the report carries. A real engine (OPA, Cedar)
replaces it without touching agents or tools.

| Checkpoint | Requested at | Where in code |
|---|---|---|
| `request_entitlement` | run start | `RunContext.run_start` |
| `tool_authorisation` | before each tool call | `PolicyToolObserver.before` |
| `freshness_pit` | after each tool call (snapshot lag, current-only data) | `PolicyToolObserver.after` |
| `a2a_inbound`, `a2a_outbound` | each agent-to-agent call | `RunContext.a2a` |
| `pii_minimisation` | before each model call | `RunContext.model_call` |
| `suitability_mandate`, `evidence_provenance`, `compliance_content` | report assembly | `RunContext.assemble` |
| `human_approval` | approval gate, before client-facing or action-proposing output | `RunContext.assemble` |

## Effect of a decision

- `deny` blocks the guarded step only. A denied tool is not executed (`PolicyDenied`, a
  `ToolRefused`), the agent run continues, and the always-deliver layer reports the gap. A denial
  at report assembly becomes a `policy_denied` gap and the status is at most `partial`.
- `escalate` pauses the guarded step (`PolicyEscalated` with a `pending_id`). The step runs only
  after `RunContext.resolve_escalation(pending_id, approve=True, by=...)`; other calls stay gated.
- The report lists one `policy_decisions` entry per checkpoint reached: the most restrictive
  decision, with how many times it was requested (`count`).

## Audit

`AuditLog` is append-only (no update, no delete; optional JSON-lines file). Each record holds run
id, kind (`decision`, `tool_call`, `tool_error`, `tool_refused`, `model_call`, `a2a_call`), agent,
subject, `as_of`, a hash of the inputs, evidence ids, the delegation chain of the original
requester and decision details. Every tool call, success or not, has a record.

## Personal data

`Pseudonymiser` replaces client names (and, for individuals, name parts of four or more letters)
with stable pseudonyms in all model input, including tool results fed back to the model.
`restore` is applied only to the final report. Client and portfolio ids are internal keys and are
not replaced.
