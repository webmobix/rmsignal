"""Interactive use of the same analysts: a thread with persistent messages, evidence and a fixed ``as_of``."""

import uuid
from datetime import date

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver

from rm_dashboard.domain import Gap, Report
from rm_dashboard.llmlog import llm_config

from .analyst import ANALYSTS, ModelFactory, RECURSION_LIMIT, _final_text, assemble_report, build_agent, request_message
from .scope import RunScope


class AnalystSession:
    """One conversation about one subject.

    State per thread: the message history (LangGraph checkpointer), the evidence store and the ``as_of``.
    A follow-up can cite evidence from earlier turns; the date changes only through ``set_as_of``.
    The checkpointer is in-memory; a durable one (SQLite, Postgres) can replace it without other changes.
    """

    def __init__(self, role: str, subject: str, scope: RunScope, models: ModelFactory, *, thread_id: str | None = None,
                 requester: str = "user", checkpointer=None):
        self.spec = ANALYSTS[role]
        self.subject, self.scope = subject, scope
        self.thread_id = thread_id or f"thread_{uuid.uuid4().hex[:12]}"
        self.checkpointer = checkpointer or InMemorySaver()
        self.agent, self.toolbox = build_agent(self.spec, scope, models, requester=requester, checkpointer=self.checkpointer)
        self.requester = requester
        self.scope.run.thread_id = self.thread_id
        self.started = False
        self._notice: str | None = None

    @property
    def as_of(self) -> date:
        return self.scope.as_of

    def set_as_of(self, as_of: date) -> None:
        """Explicit date change; earlier evidence stays in the store with its own as_of."""
        self.scope.run.as_of = as_of
        self._notice = f"The analysis date is now {as_of.isoformat()}."

    def start(self) -> Report:
        self.scope.run.run_start(self.spec.name, self.requester)
        self.started = True
        return self._turn(request_message(self.spec, self.subject, self.scope))

    def ask(self, question: str) -> Report:
        if not self.started:
            self.start()
        text = f"{self._notice} {question}" if self._notice else question
        self._notice = None
        return self._turn(HumanMessage(content=text))

    def _turn(self, message: HumanMessage) -> Report:
        scope = self.scope
        scope.gaps, scope.children = [], []
        before = len(self.toolbox.produced)
        try:
            out = self.agent.invoke({"messages": [message]}, config={
                "recursion_limit": RECURSION_LIMIT, **llm_config(scope.run, self.spec.name)})
            text = _final_text(out)
        except Exception as e:  # noqa: BLE001 - always-deliver
            scope.gaps.append(Gap(kind="agent_error", description=f"{type(e).__name__}: {e}", subject=self.spec.name))
            text = None
        return assemble_report(self.spec, self.subject, scope, self.toolbox.produced[before:], text, True)
