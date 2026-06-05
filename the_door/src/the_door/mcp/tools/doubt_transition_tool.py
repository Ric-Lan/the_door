"""MCP tool: doubt_transition — transition a doubt to a new state."""
from __future__ import annotations

from the_door.core.scope import doubt_membrane

TOOL_SCHEMA = {
    "type": "object",
    "required": ["doubt_id", "target_state", "actor"],
    "properties": {
        "doubt_id": {
            "type": "string",
            "description": "疑義 ID",
        },
        "target_state": doubt_membrane.target_state_schema(),
        "actor": {
            "type": "string",
            "description": "操作者",
        },
        "reason": {
            "type": "string",
            "description": "原因說明",
        },
        "assignee": {
            "type": "string",
            "description": "指派對象（assign 時使用）",
        },
        "codebase_path": {
            "type": "string",
            "description": "Codebase 根目錄路徑（預設 '.'）",
        },
    },
}


async def execute(arguments: dict) -> dict:
    from pathlib import Path
    from the_door.core.scope.doubt_store import DoubtStore
    from the_door.mcp.tools._response_envelope import wrap
    from the_door.models import (
        DoubtNotFoundError,
        DoubtTerminalError,
        InvalidTransitionError,
    )

    doubt_id = arguments["doubt_id"]
    target_state = arguments["target_state"]
    actor = arguments["actor"]
    reason = arguments.get("reason")
    assignee = arguments.get("assignee")
    codebase_path = arguments.get("codebase_path", ".")

    project_root = Path(codebase_path)
    store = DoubtStore(project_root)

    if target_state == "investigating" and not assignee:
        return {"error": True, "message": "assignee is required for investigating transition"}
    if target_state in ("explained", "fixed", "escalated", "accepted_risk") and not reason:
        return {"error": True, "message": f"reason is required for {target_state} transition"}
    if target_state not in ("investigating", "explained", "fixed", "escalated", "accepted_risk"):
        return {"error": True, "message": f"Unknown target_state: {target_state}"}

    try:
        doubt = store.transition(
            doubt_id, target_state, actor=actor,
            reason=reason, assignee=assignee, description=reason,
        )
    except DoubtNotFoundError:
        return {"error": True, "message": f"Doubt not found: {doubt_id}"}
    except DoubtTerminalError as e:
        return {"error": True, "message": str(e)}
    except InvalidTransitionError as e:
        return {"error": True, "message": str(e)}

    from the_door.core.scope.doubt_membrane import project_doubt

    return wrap(
        project_doubt(doubt),
        project_path=project_root,
        context="mcp",
    )
