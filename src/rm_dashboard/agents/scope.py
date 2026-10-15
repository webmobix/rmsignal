"""Run-scoped state shared by an agent, its tools and its subagents."""

from dataclasses import dataclass, field

from rm_dashboard.domain import Gap, Report
from rm_dashboard.policy import RunContext
from rm_dashboard.tools import EvidenceStore, ToolRegistry


@dataclass
class RunScope:
    """One analysis run: policy/audit context, evidence produced so far, gaps and child reports."""

    run: RunContext
    registry: ToolRegistry
    store: EvidenceStore = field(default_factory=EvidenceStore)
    gaps: list[Gap] = field(default_factory=list)
    children: list[Report] = field(default_factory=list)

    @property
    def as_of(self):
        return self.run.as_of


def register_people(run: RunContext, repo, as_of) -> None:
    """Pseudonyms for client names and covering RM names. ``as_of`` is only used to read the roster."""
    for r in repo.clients(as_of=as_of).frame.iter_rows(named=True):
        run.pseudonymiser.register(r["client_name"], key=r["client_id"], entity=r["gender"] == "Entity")
        run.pseudonymiser.register(r["rm_name"], key=r["rm_id"])
