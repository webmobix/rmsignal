"""Run-scoped policy and audit: where checkpoints are requested and recorded."""

import uuid
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from rm_dashboard.domain import Gap, PolicyDecisionRecord, Report, ToolResult
from rm_dashboard.tools import ToolRefused

from .audit import AuditLog, input_hash
from .engine import (
    A2A_INBOUND, A2A_OUTBOUND, COMPLIANCE_CONTENT, EVIDENCE_PROVENANCE, FRESHNESS_PIT, HUMAN_APPROVAL,
    PII_MINIMISATION, REQUEST_ENTITLEMENT, SUITABILITY, TOOL_AUTHORISATION, Decision, MockPolicyEngine, PolicyEngine,
)
from .pii import Pseudonymiser

_RANK = {"allow": 0, "escalate": 1, "deny": 2}


class PolicyDenied(ToolRefused):
    def __init__(self, agent: str, step: str, decision: Decision):
        super().__init__(agent, step, f"denied by policy {decision.policy_id}: {decision.reason}")
        self.decision = decision


class PolicyEscalated(ToolRefused):
    def __init__(self, agent: str, step: str, decision: Decision, pending_id: str):
        super().__init__(agent, step, f"awaiting human decision ({pending_id}): {decision.reason}")
        self.decision, self.pending_id = decision, pending_id


@dataclass
class PendingEscalation:
    pending_id: str
    checkpoint: str
    key: str
    agent: str
    resolved: bool = False
    approved: bool | None = None
    by: str | None = None


@dataclass
class RunContext:
    subject: str
    as_of: date
    engine: PolicyEngine = field(default_factory=MockPolicyEngine)
    audit: AuditLog = field(default_factory=AuditLog)
    pseudonymiser: Pseudonymiser = field(default_factory=Pseudonymiser)
    requester_chain: tuple[str, ...] = ()
    run_id: str = ""
    decisions: list[Decision] = field(default_factory=list)
    pending: dict[str, PendingEscalation] = field(default_factory=dict)
    _approved: set[tuple[str, str]] = field(default_factory=set)

    def __post_init__(self):
        if not self.run_id:
            self.run_id = f"run_{uuid.uuid4().hex[:12]}"

    # ---- core --------------------------------------------------------------------
    def _log(self, kind: str, agent: str, payload: Any, evidence_ids=(), **detail) -> None:
        self.audit.append(
            run_id=self.run_id, kind=kind, agent=agent, subject=self.subject, as_of=self.as_of.isoformat(),
            input_hash=input_hash(payload), evidence_ids=tuple(evidence_ids),
            requester_chain=self.requester_chain, detail=detail,
        )

    def checkpoint(self, name: str, agent: str, **context: Any) -> Decision:
        ctx = {"agent": agent, "subject": self.subject, "as_of": self.as_of.isoformat(),
               "requester_chain": list(self.requester_chain), **context}
        d = self.engine.check(name, ctx)
        self.decisions.append(d)
        self._log("decision", agent, ctx, checkpoint=name, decision=d.decision, reason=d.reason,
                  policy_id=d.policy_id, mock=d.mock)
        return d

    def guard(self, name: str, agent: str, step: str, key: str = "", **context: Any) -> Decision:
        """Request a decision and enforce it: deny raises PolicyDenied, escalate raises PolicyEscalated."""
        d = self.checkpoint(name, agent, step=step, **context)
        if d.decision == "deny":
            raise PolicyDenied(agent, step, d)
        if d.decision == "escalate" and (name, key or step) not in self._approved:
            pid = f"pending_{len(self.pending) + 1}"
            self.pending[pid] = PendingEscalation(pid, name, key or step, agent)
            raise PolicyEscalated(agent, step, d, pid)
        return d

    def resolve_escalation(self, pending_id: str, *, approve: bool, by: str) -> None:
        p = self.pending[pending_id]
        p.resolved, p.approved, p.by = True, approve, by
        if approve:
            self._approved.add((p.checkpoint, p.key))
        self._log("decision", p.agent, {"pending": pending_id}, checkpoint=p.checkpoint,
                  decision="human_approved" if approve else "human_rejected", by=by)

    def child(self, requester: str) -> "RunContext":
        """Same run, delegation chain extended with ``requester`` (used at A2A boundaries)."""
        c = RunContext(self.subject, self.as_of, self.engine, self.audit, self.pseudonymiser,
                       (*self.requester_chain, requester), self.run_id)
        c.decisions, c.pending, c._approved = self.decisions, self.pending, self._approved
        return c

    # ---- checkpoints at their places -----------------------------------------------
    def run_start(self, agent: str, requester: str = "user") -> Decision:
        if not self.requester_chain:
            self.requester_chain = (requester,)
        return self.guard(REQUEST_ENTITLEMENT, agent, "run_start", requester=requester)

    def tool_observer(self) -> "PolicyToolObserver":
        return PolicyToolObserver(self)

    def model_call(self, agent: str, messages: list[dict]) -> list[dict]:
        self.guard(PII_MINIMISATION, agent, "model_call", messages=len(messages))
        safe = self.pseudonymiser.protect_messages(messages)
        self._log("model_call", agent, safe, messages=len(safe))
        return safe

    def a2a(self, direction: str, agent: str, peer: str, payload: Any) -> Decision:
        name = A2A_OUTBOUND if direction == "outbound" else A2A_INBOUND
        d = self.guard(name, agent, f"a2a_{direction}", peer=peer)
        self._log("a2a_call", agent, payload, direction=direction, peer=peer)
        return d

    def assemble(self, report: Report, agent: str) -> Report:
        """Report-assembly and approval-gate checkpoints; denials become gaps, never errors."""
        gaps = list(report.gaps)
        for name in (SUITABILITY, EVIDENCE_PROVENANCE, COMPLIANCE_CONTENT, HUMAN_APPROVAL):
            try:
                self.guard(name, agent, "report_assembly" if name != HUMAN_APPROVAL else "approval_gate",
                           findings=len(report.findings))
            except PolicyDenied as e:
                gaps.append(Gap(kind="policy_denied", description=e.reason, subject=name))
            except PolicyEscalated as e:
                gaps.append(Gap(kind="policy_denied", description=e.reason, subject=name))
        status = report.status
        if len(gaps) > len(report.gaps) and status == "complete":
            status = "partial"
        return report.model_copy(update={"gaps": gaps, "status": status, "policy_decisions": self.report_decisions()})

    def report_decisions(self) -> list[PolicyDecisionRecord]:
        """One entry per checkpoint reached: the most restrictive decision, with how often it was asked."""
        best: dict[str, Decision] = {}
        counts: dict[str, int] = {}
        for d in self.decisions:
            counts[d.checkpoint] = counts.get(d.checkpoint, 0) + 1
            if d.checkpoint not in best or _RANK[d.decision] > _RANK[best[d.checkpoint].decision]:
                best[d.checkpoint] = d
        return [PolicyDecisionRecord(checkpoint=c, decision=d.decision, reason=d.reason, policy_id=d.policy_id,
                                     mock=d.mock, count=counts[c]) for c, d in best.items()]


class PolicyToolObserver:
    """Plugs a ``RunContext`` into the tool registry."""

    def __init__(self, run: RunContext):
        self.run = run

    def before(self, agent: str, tool: str, args: dict[str, Any]) -> None:
        self.run.guard(TOOL_AUTHORISATION, agent, tool, key=f"{tool}:{input_hash(args)}", tool=tool, args=args)

    def after(self, agent: str, tool: str, args: dict[str, Any], result: ToolResult) -> None:
        self.run._log("tool_call", agent, {"tool": tool, "args": args}, [result.evidence_id], tool=tool,
                      status=result.status)
        self.run.guard(FRESHNESS_PIT, agent, tool, key=f"{tool}:{input_hash(args)}", tool=tool,
                       effective_snapshot_date=str(result.effective_snapshot_date), gap_days=result.gap_days,
                       pit=result.pit)

    def refused(self, agent: str, tool: str, reason: str) -> None:
        self.run._log("tool_refused", agent, {"tool": tool}, tool=tool, reason=reason)

    def failed(self, agent: str, tool: str, args: dict[str, Any], error: Exception) -> None:
        self.run._log("tool_error", agent, {"tool": tool, "args": args}, tool=tool, error=type(error).__name__)
