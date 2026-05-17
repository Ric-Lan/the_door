"""MCP tool: timeline — analyze feature evolution timeline across snapshots."""
from __future__ import annotations

TOOL_SCHEMA = {
    "type": "object",
    "required": ["codebase_path"],
    "properties": {
        "codebase_path": {"type": "string", "description": "Codebase root directory path"},
        "feature_id": {"type": "string", "description": "Only query specified feature evolution"},
        "since": {"type": "string", "description": "Only analyze snapshots after this date (ISO 8601: YYYY-MM-DD)"},
    },
}


async def execute(arguments: dict) -> dict:
    """Execute the timeline MCP tool. Returns TimelineResult JSON."""
    from datetime import datetime
    from pathlib import Path

    from the_door.core.diff.snapshot_store import SnapshotStore
    from the_door.core.timeline.timeline_engine import TimelineEngine
    from the_door.mcp.tools._response_envelope import wrap

    codebase_path = arguments["codebase_path"]
    project_root = Path(arguments.get("codebase_path") or arguments.get("project_path") or Path.cwd())
    feature_id = arguments.get("feature_id")
    since = arguments.get("since")

    store = SnapshotStore(Path(codebase_path))
    snapshots = store.list_snapshots()

    if not snapshots:
        return {"error": "No snapshots found. Run analyze first."}

    # Filter by --since if provided
    if since is not None:
        try:
            since_date = datetime.fromisoformat(since)
        except ValueError:
            return {"error": "Invalid date format. Use ISO 8601 (YYYY-MM-DD)."}

        since_str = since_date.isoformat()
        snapshots = [s for s in snapshots if s.timestamp >= since_str]

        if not snapshots:
            return {"error": "No snapshots found after the specified date."}

    engine = TimelineEngine()

    # Single feature query
    if feature_id is not None:
        ft = engine.analyze_feature(snapshots, feature_id)
        if ft is None:
            # Collect all available feature_ids
            all_ids: set[str] = set()
            for snap in snapshots:
                all_ids.update(snap.l1_snapshot.keys())
            return {
                "error": "Feature not found",
                "available_features": sorted(all_ids),
            }
        return wrap(_serialize_feature_timeline(ft), project_path=project_root, context="mcp")

    # Full timeline analysis
    result = engine.analyze(snapshots)
    return wrap(_serialize_timeline_result(result), project_path=project_root, context="mcp")


def _serialize_timeline_result(result) -> dict:
    """Serialize TimelineResult to JSON-compatible dict."""
    return {
        "snapshot_count": result.snapshot_count,
        "time_range_start": result.time_range_start,
        "time_range_end": result.time_range_end,
        "feature_timelines": [
            _serialize_feature_timeline(ft)
            for ft in result.feature_timelines
        ],
        "summary": {
            "active_count": result.summary.active_count,
            "removed_count": result.summary.removed_count,
            "total_drift_events": result.summary.total_drift_events,
        },
    }


def _serialize_feature_timeline(ft) -> dict:
    """Serialize a single FeatureTimeline to JSON-compatible dict."""
    return {
        "feature_id": ft.feature_id,
        "first_seen_timestamp": ft.first_seen_timestamp,
        "last_seen_timestamp": ft.last_seen_timestamp,
        "change_count": ft.change_count,
        "current_state": ft.current_state,
        "current_label": ft.current_label,
        "drift_events": [
            {
                "snapshot_version_id": ev.snapshot_version_id,
                "previous_description": ev.previous_description,
                "new_description": ev.new_description,
                "timestamp": ev.timestamp,
            }
            for ev in ft.drift_events
        ],
    }
