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
