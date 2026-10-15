"""Agent Cards: what each analyst is, what it accepts and how callers authenticate."""

from google.protobuf.struct_pb2 import Struct

from a2a.types.a2a_pb2 import (
    AgentCapabilities, AgentCard, AgentExtension, AgentInterface, AgentProvider, AgentSkill, HTTPAuthSecurityScheme,
    SecurityRequirement, SecurityScheme, StringList,
)

from rm_dashboard.agents.analyst import ANALYSTS

CARD_VERSION = "1"
INPUT_EXTENSION = "urn:rm-dashboard:ext:required-input"
JSON_MODE = "application/json"

SKILLS = {
    "relationship_analyst": ("client_relationship_analysis", "Client relationship analysis",
                             "Profile, KYC status, concentration with look-through, liquidity, credit and notes for one client."),
    "portfolio_analyst": ("portfolio_analysis", "Portfolio analysis",
                          "Composition, mandate band drift, unrealised P&L and delegated instrument analysis for one portfolio."),
    "instrument_analyst": ("instrument_analysis", "Instrument analysis",
                           "Reference data, price path, events and market context for one instrument."),
}


def required_inputs(role: str) -> list[str]:
    return ["as_of", f"{ANALYSTS[role].subject_kind}_id"]


def _security() -> tuple[dict, list]:
    scheme = SecurityScheme(http_auth_security_scheme=HTTPAuthSecurityScheme(
        scheme="bearer", description="Bank-internal bearer token (not enforced by the MVP server)."))
    req = SecurityRequirement(schemes={"bearer": StringList(list=[])})
    return {"bearer": scheme}, [req]


def build_card(role: str, base_url: str) -> AgentCard:
    skill_id, skill_name, desc = SKILLS[role]
    params = Struct()
    params.update({"required": required_inputs(role), "date_format": "YYYY-MM-DD",
                   "output": "analysis report (status, findings with evidence ids, gaps, flags, policy decisions)"})
    schemes, reqs = _security()
    return AgentCard(
        name=role, description=ANALYSTS[role].description, version=CARD_VERSION,
        provider=AgentProvider(organization="rm-dashboard", url=base_url),
        supported_interfaces=[AgentInterface(url=base_url, protocol_binding="JSONRPC", protocol_version="1.0")],
        capabilities=AgentCapabilities(streaming=False, push_notifications=False, extensions=[
            AgentExtension(uri=INPUT_EXTENSION, description="Inputs every task must carry", required=True, params=params)]),
        default_input_modes=[JSON_MODE], default_output_modes=[JSON_MODE],
        skills=[AgentSkill(id=skill_id, name=skill_name,
                           description=f"{desc} Requires {' and '.join(required_inputs(role))}.",
                           tags=["wealth", "analysis", role], examples=[f'{{"as_of": "2026-08-26", "{ANALYSTS[role].subject_kind}_id": "..."}}'],
                           input_modes=[JSON_MODE], output_modes=[JSON_MODE])],
        security_schemes=schemes, security_requirements=reqs,
    )
