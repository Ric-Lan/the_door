"""CatalogHandlers — GET /api/snapshots, GET /api/timeline, GET /api/report/latest."""
from __future__ import annotations

import json
from pathlib import Path

from the_door.core.diff.snapshot_store import SnapshotStore
from the_door.core.timeline.timeline_engine import TimelineEngine
from the_door.core.ui.api.context import APIContext
from the_door.core.ui.serializers import (
    empty_timeline_result,
    serialize_snapshot,
    serialize_timeline_result,
)


class CatalogHandlers:
    def __init__(self, ctx: APIContext) -> None:
        self._ctx = ctx

    # ------------------------------------------------------------------
    # GET /api/snapshots
    # ------------------------------------------------------------------

    def snapshots(self, ctx=None, **_) -> tuple[int, dict]:
        """Return all snapshots sorted by timestamp descending."""
        try:
            snapshots = SnapshotStore(self._ctx.project_root).list_snapshots()
            sorted_snapshots = sorted(snapshots, key=lambda s: s.timestamp, reverse=True)
            return 200, {"snapshots": [serialize_snapshot(s) for s in sorted_snapshots]}
        except Exception as exc:
            return 500, self._make_error(
                code="snapshot_read_error",
                message=str(exc),
                source="handle_get_snapshots",
            )

    # ------------------------------------------------------------------
    # GET /api/timeline
    # ------------------------------------------------------------------

    def timeline(self, ctx=None, **_) -> tuple[int, dict]:
        """Return timeline analysis result."""
        try:
            snapshots = SnapshotStore(self._ctx.project_root).list_snapshots()
            if not snapshots:
                return 200, empty_timeline_result()
            result = TimelineEngine().analyze(snapshots)
            return 200, serialize_timeline_result(result)
        except Exception as exc:
            return 500, self._make_error(
                code="timeline_error",
                message=str(exc),
                source="handle_get_timeline",
            )

    # ------------------------------------------------------------------
    # GET /api/report/latest
    # ------------------------------------------------------------------

    def report_latest(self, ctx=None, **_) -> tuple[int, dict]:
        """Return the latest UpdateReport JSON."""
        latest_path = self._find_latest_report_path()
        if latest_path is None:
            return 404, self._make_error(
                code="no_report_found",
                message="No update report found in .the-door/",
                source="handle_get_report_latest",
            )
        try:
            content = latest_path.read_text(encoding="utf-8")
            return 200, json.loads(content)
        except json.JSONDecodeError as exc:
            return 500, self._make_error(
                code="report_parse_error",
                message=str(exc),
                source="handle_get_report_latest",
            )
        except Exception as exc:
            return 500, self._make_error(
                code="report_read_error",
                message=str(exc),
                source="handle_get_report_latest",
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _find_latest_report_path(self) -> Path | None:
        """Find the newest update-report-*.json by generated_at (fallback: mtime)."""
        dot_dir = self._ctx.project_root / ".the-door"
        if not dot_dir.exists():
            return None
        candidates = list(dot_dir.glob("update-report-*.json"))
        if not candidates:
            return None

        def sort_key(p: Path):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                val = data.get("generated_at", "")
                if val:
                    return (1, val)
                return (0, p.stat().st_mtime_ns)
            except Exception:
                return (0, p.stat().st_mtime_ns)

        return max(candidates, key=sort_key)

    @staticmethod
    def _make_error(code: str, message: str, source: str) -> dict:
        return {"error": {"code": code, "message": message, "source": source}}
