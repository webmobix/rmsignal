import importlib

import pytest

from rm_dashboard.settings import Settings


@pytest.mark.parametrize("pkg", ["pit", "domain", "analytics", "tools", "policy", "agents", "a2a", "runners"])
def test_packages_import(pkg):
    importlib.import_module(f"rm_dashboard.{pkg}")


def test_dependencies_import():
    for mod in ["polars", "pydantic", "langgraph", "deepagents", "langchain_openai", "a2a", "hypothesis"]:
        importlib.import_module(mod)


def test_settings_from_env():
    s = Settings.from_env({
        "RM_DASHBOARD_DB": "x.db", "RM_GATEWAY_URL": "http://gw/v1",
        "RM_MODEL_NAME": "m1", "RM_HORIZON_DAYS": "30",
    })
    assert (s.db_path, s.gateway_url, s.model_name, s.horizon_days) == ("x.db", "http://gw/v1", "m1", 30)


def test_settings_defaults():
    assert Settings.from_env({}).horizon_days == 365
