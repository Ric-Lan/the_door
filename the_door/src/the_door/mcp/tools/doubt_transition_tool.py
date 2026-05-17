"""MCP tool: doubt_transition — transition a doubt to a new state."""
from __future__ import annotations

TOOL_SCHEMA = {
    "type": "object",
    "required": ["doubt_id", "target_state", "actor"],
    "properties": {
        "doubt_id": {
            "type": "string",
            "description": "疑義 ID",
        },
        "target_state": {
            "type": "string",
            "description": "目標狀態",
        },
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

    try:
        if target_state == "investigating":
            if not assignee:
                return {"error": True, "message": "assignee is required for investigating transition"}
            doubt = store.assign(doubt_id, assignee, actor)

        elif target_state == "explained":
            if not reason:
                return {"error": True, "message": "reason is required for explained transition"}
            # Check current state to decide which method to use
            current = store.get_doubt(doubt_id)
            if current.current_state == "escalated":
                doubt = store.resolve_escalation(doubt_id, "explained", reason, actor)
            else:
                doubt = store.explain(doubt_id, reason, actor)

        elif target_state == "fixed":
            if not reason:
                return {"error": True, "message": "reason is required for fixed transition"}
            current = store.get_doubt(doubt_id)
            if current.current_state == "escalated":
                doubt = store.resolve_escalation(doubt_id, "fixed", reason, actor)
            else:
                doubt = store.fix(doubt_id, reason, actor)

        elif target_state == "escalated":
            if not reason:
                return {"error": True, "message": "reason is required for escalated transition"}
            doubt = store.escalate(doubt_id, reason, actor)

        elif target_state == "accepted_risk":
            if not reason:
                return {"error": True, "message": "reason is required for accepted_risk transition"}
            doubt = store.resolve_escalation(doubt_id, "accepted_risk", reason, actor)

        else:
            return {"error": True, "message": f"Unknown target_state: {target_state}"}

    except DoubtNotFoundError:
        return {"error": True, "message": f"Doubt not found: {doubt_id}"}
    except DoubtTerminalError as e:
        return {"error": True, "message": str(e)}
    except InvalidTransitionError as e:
        return {"error": True, "message": str(e)}

    return wrap({
        "doubt_id": doubt.doubt_id,
        "source_node": doubt.source_node,
        "doubt_type": doubt.doubt_type,
        "current_state": doubt.current_state,
        "created_by": doubt.created_by,
        "created_at": doubt.created_at,
        "updated_at": doubt.updated_at,
        "assigned_to": doubt.assigned_to,
        "resolution": (
            {
                "type": doubt.resolution.type,
                "description": doubt.resolution.description,
                "resolved_by": doubt.resolution.resolved_by,
                "resolved_at": doubt.resolution.resolved_at,
            }
            if doubt.resolution is not None
            else None
        ),
    }, project_path=project_root, context="mcp")
