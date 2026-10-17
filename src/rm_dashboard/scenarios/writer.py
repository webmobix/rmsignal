"""Layer B's model calls: place the holdings the rules cannot place, and write the prose of an impact or a roll-up.

The model never supplies a figure. Prose is checked against the computed figures it was given and replaced by code-built text
when it quotes anything else."""

import json
from datetime import date

from langchain_core.messages import HumanMessage

from rm_dashboard.agents import prompts
from rm_dashboard.agents.analyst import RECURSION_LIMIT, AnalystSpec, ModelFactory, _final_text, build_agent
from rm_dashboard.agents.outputs import parse_json_object
from rm_dashboard.agents.scope import RunScope
from rm_dashboard.domain import Gap
from rm_dashboard.llmlog import llm_config
from rm_dashboard.policy import PolicyDenied, PolicyEscalated
from rm_dashboard.tools import ALLOWLISTS

from .channels import Channel
from .figures import figure_problems
from .guard import guard_mappings
from .mapping import Ambiguity

ROLE = "scenario_impact"
SPEC = AnalystSpec(ROLE, "portfolio", r"PF-\d{4}", prompts.SCENARIO_IMPACT, ALLOWLISTS[ROLE], (),
                   "Places holdings the rules cannot map onto scenario channels and writes the summaries of scenario results.")


class Writer:
    """One compiled agent, asked for one task at a time. Every method returns a result and gaps; none raises except a policy stop."""

    def __init__(self, scope: RunScope, models: ModelFactory):
        self.scope = scope
        self.agent, self.toolbox = build_agent(SPEC, scope, models)

    def ask(self, text: str) -> tuple[dict | None, str | None]:
        result = self.agent.invoke({"messages": [HumanMessage(content=text)]},
                                   config={"recursion_limit": RECURSION_LIMIT, **llm_config(self.scope.run, SPEC.name)})
        return parse_json_object(_final_text(result))

    def mappings(self, header: str, ambiguous: list[Ambiguity], channels: list[Channel], vector_channels: list[str]):
        """(accepted instrument -> [(channel, reason)], every proposal with its verdict, gaps)."""
        usable = [c for c in channels if c.channel in vector_channels]
        lines = [f"TASK mapping", header, "Channels of the vector (use only these; never an fx channel):",
                 *[f"- {c.channel} [{c.kind}]: {c.label}" for c in usable], "Holdings the rules could not place:",
                 *[f"- {a.instrument_id}: {a.instrument_name} ({a.asset_class}, sector {a.sector or 'none'}); {a.reason}" for a in ambiguous]]
        try:
            obj, err = self.ask("\n".join(lines))
        except (PolicyDenied, PolicyEscalated):
            raise
        except Exception as e:  # noqa: BLE001 - always delivered
            return {}, [], [Gap(kind="agent_error", description=f"mapping not obtained: {type(e).__name__}: {e}", subject=ROLE)]
        if err or obj is None:
            return {}, [], [Gap(kind="agent_error", description=f"mapping not obtained: {err}", subject=ROLE)]
        return guard_mappings(obj.get("mappings"), {a.instrument_id: a.reason for a in ambiguous}, vector_channels)

    def summary(self, task: str, header: str, figures: dict, fallback: str, *, direction: float | None) -> tuple[str, list[Gap]]:
        """(the agent's summary when it quotes only computed figures, else ``fallback``; gaps)."""
        text = f"TASK {task}\n{header}\nFIGURES {json.dumps(figures, default=str, separators=(',', ':'))}"
        try:
            obj, err = self.ask(text)
        except (PolicyDenied, PolicyEscalated):
            raise
        except Exception as e:  # noqa: BLE001 - always delivered
            return fallback, [Gap(kind="agent_error", description=f"summary not obtained, built by code instead: {type(e).__name__}: {e}", subject=ROLE)]
        said = obj.get("summary") if obj else None
        if err or not isinstance(said, str) or not said.strip():
            return fallback, [Gap(kind="agent_error", description=f"summary not obtained, built by code instead: {err or 'no summary in the answer'}",
                                  subject=ROLE)]
        problems = figure_problems(said, figures, direction=direction)
        if problems:
            return fallback, [Gap(kind="guard_removed", subject="summary",
                                  description="summary replaced by one built by code: it " + "; ".join(problems))]
        return said.strip(), []


def header_for(scenario_name: str, premise: str, horizon: int, as_of: date, subject: str) -> str:
    return f"Scenario: {scenario_name}. {premise}\nHorizon: {horizon} months. As of {as_of.isoformat()}. {subject}"
