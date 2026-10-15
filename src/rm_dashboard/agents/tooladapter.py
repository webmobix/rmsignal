"""Exposes registry tools to LangChain agents.

``as_of`` is taken from the run, never from the model, so a model-chosen date cannot leak
look-ahead. Every call goes through ``Toolbox.call`` so allow-list, policy, audit and the
evidence store all apply. Failures become gaps; the model gets a short error it can adapt to.
"""

import json
from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, ValidationError, create_model

from rm_dashboard.domain import Gap, ToolResult
from rm_dashboard.policy import PolicyDenied, PolicyEscalated
from rm_dashboard.tools import Toolbox, ToolRefused, ToolSpec

from .scope import RunScope


def lc_name(tool: str) -> str:
    """Provider-safe tool name: OpenAI-style APIs reject dots."""
    return tool.replace(".", "_")


def args_model(spec: ToolSpec) -> type[BaseModel]:
    fields: dict[str, Any] = {n: (f.annotation, f) for n, f in spec.params.model_fields.items() if n != "as_of"}
    return create_model(f"{spec.params.__name__}Args", **fields)


def result_payload(r: ToolResult) -> dict[str, Any]:
    return {
        "evidence_id": r.evidence_id, "tool": r.computation.tool, "status": r.status, "reason": r.reason,
        "as_of": r.as_of, "effective_snapshot_date": r.effective_snapshot_date, "gap_days": r.gap_days,
        "pit": r.pit, "mock": r.mock,
        "flags": [{"code": f.code, "message": f.message, "subject": f.subject} for f in r.flags],
        "method": r.computation.method, "data": r.data,
    }


def to_json(obj: Any) -> str:
    return json.dumps(obj, default=str, separators=(",", ":"))


def make_tool(spec: ToolSpec, toolbox: Toolbox, scope: RunScope) -> StructuredTool:
    def call(**kwargs: Any) -> str:
        args = {**kwargs, "as_of": scope.as_of.isoformat()}
        try:
            return to_json(result_payload(toolbox.call(spec.name, args)))
        except (PolicyDenied, PolicyEscalated, ToolRefused) as e:
            scope.gaps.append(Gap(kind="policy_denied", description=e.reason, subject=spec.name))
            msg = e.reason
        except ValidationError as e:
            scope.gaps.append(Gap(kind="tool_error", description=f"invalid arguments: {e.error_count()} error(s)", subject=spec.name))
            msg = f"invalid arguments: {e.errors(include_url=False, include_context=False)}"
        except Exception as e:  # noqa: BLE001 - always-deliver: any tool failure becomes a gap
            scope.gaps.append(Gap(kind="tool_error", description=f"{type(e).__name__}: {e}", subject=spec.name))
            msg = f"{type(e).__name__}: {e}"
        return to_json({"error": True, "tool": spec.name, "message": msg})

    return StructuredTool.from_function(
        func=call, name=lc_name(spec.name), description=spec.description, args_schema=args_model(spec),
    )


def make_tools(toolbox: Toolbox, scope: RunScope) -> list[StructuredTool]:
    return [make_tool(s, toolbox, scope) for s in toolbox.specs()]
