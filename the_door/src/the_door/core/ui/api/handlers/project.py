"""ProjectHandlers — GET /api/project, POST /api/set-project, GET /api/status."""
from __future__ import annotations

import os
from pathlib import Path

from the_door.core.diff.snapshot_store import SnapshotStore
from the_door.core.guidance.actions import NextAction, to_json_dict as action_to_json
from the_door.core.guidance.state import StateInspector, to_json_dict as state_to_json
from the_door.core.guidance.suggester import NextActionSuggester
from the_door.core.scope.doubt_store import DoubtStore
from the_door.core.ui.api.context import APIContext
from the_door.core.ui.api.report_paths import find_latest_report_path


class ProjectHandlers:
    def __init__(self, ctx: APIContext) -> None:
        self._ctx = ctx

    # ------------------------------------------------------------------
    # GET /api/project
    # ------------------------------------------------------------------

    def get(self, ctx=None, **_) -> tuple[int, dict]:
        """Return project path and available data status."""
        dot_dir = self._ctx.project_root / ".the-door"
        dot_exists = dot_dir.exists()

        if not dot_exists:
            return 200, {
                "project_path": str(self._ctx.project_root.resolve()),
                "dot_the_door_exists": False,
                "available_data": {
                    "has_snapshots": False,
                    "has_latest_report": False,
                    "has_doubts": False,
                    "has_scope_config": False,
                },
            }

        try:
            snapshots = SnapshotStore(self._ctx.project_root).list_snapshots()
            doubts = DoubtStore(self._ctx.project_root).list_doubts()
            has_scope_config = (dot_dir / "scope-config.json").exists()
            has_latest_report = find_latest_report_path(self._ctx.project_root) is not None

            return 200, {
                "project_path": str(self._ctx.project_root.resolve()),
                "dot_the_door_exists": True,
                "available_data": {
                    "has_snapshots": len(snapshots) > 0,
                    "has_latest_report": has_latest_report,
                    "has_doubts": len(doubts) > 0,
                    "has_scope_config": has_scope_config,
                },
            }
        except Exception as exc:
            return 500, self._make_error(
                code="project_read_error",
                message=str(exc),
                source="handle_get_project",
            )

    # ------------------------------------------------------------------
    # POST /api/set-project
    # ------------------------------------------------------------------

    def set_project(self, ctx=None, *, body=None, **_) -> tuple[int, dict]:
        """Switch to a new project, validating the path and checking for conflicts."""
        if body is None:
            body = {}
        path_str = body.get("path", "")
        force = bool(body.get("force", False))

        if not path_str:
            return 400, {"status": "error", "message": "路徑不存在或無法讀取"}

        try:
            path = Path(path_str)
        except Exception:
            return 400, {"status": "error", "message": "路徑格式無效"}

        if not path.exists() or not path.is_dir() or not os.access(path, os.R_OK):
            return 400, {"status": "error", "message": "路徑不存在或無法讀取"}

        result = self._ctx.switch_project(path, force)
        if result["status"] == "switched":
            return 200, result
        if result["status"] == "conflict":
            return 409, result
        return 400, result

    # ------------------------------------------------------------------
    # GET /api/status
    # ------------------------------------------------------------------

    def status(self, ctx=None, **_) -> tuple[int, dict]:
        """GET /api/status — SystemState + next_actions for the project root."""
        state = StateInspector(self._ctx.project_root).inspect()
        actions = NextActionSuggester().suggest(state, context="viewer")
        return 200, {
            "state": state_to_json(state),
            "next_actions": [action_to_json(a) for a in actions],
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _make_error(code: str, message: str, source: str) -> dict:
        return {"error": {"code": code, "message": message, "source": source}}
