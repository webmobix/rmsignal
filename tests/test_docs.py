import re
from pathlib import Path

from rm_dashboard.analytics import METHODS
from rm_dashboard.tools import ToolContext, ToolRegistry

DOCS = Path(__file__).parent.parent / "docs"


def test_methods_doc_covers_every_tool_and_analytic():
    text = (DOCS / "methods.md").read_text()
    for name in ToolRegistry(ToolContext(None)).names():
        assert f"| `{name}` |" in text, name
    for name, method in METHODS.items():
        assert f"### {name}\n" in text and method in text, name
    for flag in ("stale_mark", "missing_cost_basis", "mid_period_position", "bond_nominal_unit",
                 "subscription_currency_mismatch", "facility_drawdown_mismatch", "assumed_known_since_relationship_start"):
        assert flag in text


def test_readme_documents_guard_tolerance():
    from rm_dashboard.agents.guard import RELATIVE_TOLERANCE

    text = (Path(__file__).parent.parent / "README.md").read_text()
    assert f"{RELATIVE_TOLERANCE * 100:g}%" in text and "Output guard" in text


# ---- docs/architecture.md stays in step with the agents, runners, tools and A2A skills ----------------------------------
ARCH = DOCS / "architecture.md"
MATRIX_ROLES = ("relationship_analyst", "portfolio_analyst", "instrument_analyst", "note_reconciler", "outlook_analyst",
                "outlook_instrument")
AGENT_FIELDS = ("Purpose", "Setup", "Subject and trigger", "Inputs and tools", "Delegation and callers", "Output and file",
                "Checks after the model", "Model used")
OTHER_AGENT_ROLES = ("note_reconciler", "mandate_reconciler", "client_actions", "rm_overview_summary", "outlook_analyst", "outlook_instrument")


def _section(text: str, start: str, end: str | None = None) -> str:
    i = text.index(start)
    j = text.index(end, i + len(start)) if end else len(text)
    return text[i:j]


def _agent_sections(text: str) -> dict[str, str]:
    """Heading '### 4.n Title (`role`)' -> its body, for section 4."""
    body = _section(text, "## 4. The agents", "## 5. Tools")
    parts = re.split(r"^### ", body, flags=re.M)[1:]
    out = {}
    for part in parts:
        head = part.splitlines()[0]
        m = re.search(r"\(`([a-z_]+)`\)", head)
        out[m.group(1) if m else head] = part
    return out


def test_architecture_tool_matrix_matches_registry_and_allowlists():
    from rm_dashboard.tools import ALLOWLISTS

    text = ARCH.read_text()
    rows = {}
    for line in _section(text, "## 5. Tools", "## 6.").splitlines():
        if line.startswith("| `"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            assert len(cells) == 3 + len(MATRIX_ROLES), line
            rows[cells[0].strip("`")] = cells
    registry = ToolRegistry(ToolContext(None))
    assert set(rows) == set(registry.names())
    for name, cells in rows.items():
        assert cells[1] == registry.specs[name].kind, name
        for role, mark in zip(MATRIX_ROLES, cells[3:]):
            assert (mark == "x") == (name in ALLOWLISTS[role]), (name, role)


def test_architecture_covers_every_agent_role_with_the_template_fields():
    from rm_dashboard.agents.analyst import ANALYSTS

    text = ARCH.read_text()
    sections = _agent_sections(text)
    for role in (*ANALYSTS, *OTHER_AGENT_ROLES):
        assert role in sections, role
        for field in AGENT_FIELDS:
            assert f"**{field}:**" in sections[role], (role, field)
    kyc = [s for k, s in sections.items() if "KYC peer" in k]
    assert kyc and all(f"**{f}:**" in kyc[0] for f in AGENT_FIELDS)
    assert "mock" in kyc[0].lower()


def test_architecture_lists_every_console_script_and_card_skill():
    import tomllib

    from rm_dashboard.a2a.cards import SKILLS

    text = ARCH.read_text()
    scripts = tomllib.loads((DOCS.parent / "pyproject.toml").read_text())["project"]["scripts"]
    runners = _section(text, "## 2. Runners", "## 3.")
    for name in scripts:
        assert f"`{name}`" in runners, name
    for skill_id, _, _ in SKILLS.values():
        assert f"`{skill_id}`" in text, skill_id


def test_architecture_diagrams_are_mermaid_and_links_resolve():
    text = ARCH.read_text()
    blocks = re.findall(r"```mermaid\n(.*?)```", text, flags=re.S)
    assert len(blocks) >= 6
    for b in blocks:
        assert b.lstrip().split()[0] in ("flowchart", "sequenceDiagram"), b[:40]
    for link in re.findall(r"\]\(([^)#]+\.md)\)", text):
        assert (DOCS / link).is_file(), link
    assert "architecture.md" in (DOCS.parent / "README.md").read_text()
    assert "architecture.md" in (DOCS / "agents.md").read_text()
