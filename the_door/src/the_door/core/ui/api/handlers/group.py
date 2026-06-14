"""GroupHandlers — GET /api/group."""
from __future__ import annotations

from the_door.core.registry import ProjectRegistry, UNGROUPED_HINT
from the_door.core.ui.api.context import APIContext


class GroupHandlers:
    def __init__(self, ctx: APIContext) -> None:
        self._ctx = ctx

    def get_group(self, ctx=None, **_) -> tuple[int, dict]:
        """GET /api/group — return current project's group membership and sibling members."""
        reg = ProjectRegistry()
        project_root = str(self._ctx.project_root.resolve())
        project = reg.get_by_path(project_root)

        if project is None:
            return 200, {
                "current_project": {"name": self._ctx.project_root.name, "path": project_root},
                "group": None,
                "hint": UNGROUPED_HINT,
            }

        group_info = reg.get_group_for_project(project["id"])

        current_project = {
            "id": project["id"],
            "name": project["name"],
            "path": project["path"],
        }

        if group_info is None:
            return 200, {
                "current_project": current_project,
                "group": None,
                "hint": UNGROUPED_HINT,
            }

        groups = reg.list_groups()
        target_group = next((g for g in groups if g["id"] == group_info["id"]), None)
        members = []
        if target_group:
            for m in target_group["members"]:
                members.append({
                    "id": m["id"],
                    "name": m["name"],
                    "path": m["path"],
                    "is_current": m["id"] == project["id"],
                })

        return 200, {
            "current_project": current_project,
            "group": {
                "id": group_info["id"],
                "name": group_info["name"],
                "members": members,
            },
        }
