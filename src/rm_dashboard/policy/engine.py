"""Policy decision interface, the checkpoint names and the mock implementation."""

from dataclasses import dataclass
from typing import Any, Literal, Protocol

# Names of the places where a decision is requested.
REQUEST_ENTITLEMENT = "request_entitlement"
TOOL_AUTHORISATION = "tool_authorisation"
A2A_INBOUND = "a2a_inbound"
A2A_OUTBOUND = "a2a_outbound"
PII_MINIMISATION = "pii_minimisation"
FRESHNESS_PIT = "freshness_pit"
SUITABILITY = "suitability_mandate"
EVIDENCE_PROVENANCE = "evidence_provenance"
COMPLIANCE_CONTENT = "compliance_content"
HUMAN_APPROVAL = "human_approval"

CHECKPOINTS = (
    REQUEST_ENTITLEMENT, TOOL_AUTHORISATION, A2A_INBOUND, A2A_OUTBOUND, PII_MINIMISATION, FRESHNESS_PIT,
    SUITABILITY, EVIDENCE_PROVENANCE, COMPLIANCE_CONTENT, HUMAN_APPROVAL,
)

DecisionKind = Literal["allow", "deny", "escalate"]


@dataclass(frozen=True, slots=True)
class Decision:
    checkpoint: str
    decision: DecisionKind
    reason: str
    policy_id: str
    mock: bool = False


class PolicyEngine(Protocol):
    def check(self, checkpoint: str, context: dict[str, Any]) -> Decision: ...


MOCK_POLICY_ID = "mock-allow-all"


class MockPolicyEngine:
    """Allows everything and says so. Real engines (OPA, Cedar) replace it without touching agents."""

    def check(self, checkpoint: str, context: dict[str, Any]) -> Decision:
        return Decision(checkpoint, "allow", "mock policy engine: no rules evaluated, request allowed",
                        MOCK_POLICY_ID, mock=True)


class ScriptedEngine:
    """Test engine: answers per checkpoint (optionally per tool) from a table, allow otherwise."""

    def __init__(self, rules: dict[str, DecisionKind] | None = None, by_tool: dict[str, DecisionKind] | None = None):
        self.rules = rules or {}
        self.by_tool = by_tool or {}
        self.seen: list[tuple[str, dict[str, Any]]] = []

    def check(self, checkpoint: str, context: dict[str, Any]) -> Decision:
        self.seen.append((checkpoint, context))
        kind = self.by_tool.get(context.get("tool", ""), None) if checkpoint == TOOL_AUTHORISATION else None
        kind = kind or self.rules.get(checkpoint, "allow")
        return Decision(checkpoint, kind, f"scripted engine: {kind}", "scripted")
