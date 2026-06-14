"""MCP tool: project_list — list all projects registered in ProjectRegistry."""
from __future__ import annotations

from pathlib import Path

from the_door.core.registry import ProjectRegistry
from the_door.mcp.tools._response_envelope import wrap

TOOL_SCHEMA = {
    "type": "object",
    "properties": {},
}


async def execute(arguments: dict) -> dict:
    """Return all registered projects with group membership from ~/.the-door/registry.json."""
    reg = ProjectRegistry()
    raw_projects = reg.list_projects()
    groups = reg.list_groups()

    # Build group lookup: project_id → {id, name}
    group_by_pid: dict[str, dict] = {}
    for g in groups:
        for m in g["members"]:
            group_by_pid[m["id"]] = {"id": g["id"], "name": g["name"]}

    projects = []
    for p in raw_projects:
        group_info = group_by_pid.get(p["id"])
        projects.append({
            **p,
            "group_id": group_info["id"] if group_info else None,
            "group_name": group_info["name"] if group_info else None,
        })

    ungrouped_count = sum(1 for p in projects if p["group_id"] is None)

    payload: dict = {
        "projects": projects,
        "groups": [
            {"id": g["id"], "name": g["name"], "member_ids": [m["id"] for m in g["members"]]}
            for g in groups
        ],
        "count": len(projects),
        "ungrouped_count": ungrouped_count,
    }

    if ungrouped_count > 0:
        ungrouped_names = [p["name"] for p in projects if p["group_id"] is None]
        payload["hint"] = (
            f"專案 {', '.join(repr(n) for n in ungrouped_names[:3])}"
            + (" 等" if len(ungrouped_names) > 3 else "")
            + " 尚未加入群組。執行 `the-door group add <name> <path>` 建立比較群組。"
        )

    return wrap(payload, project_path=Path.cwd(), context="mcp")
