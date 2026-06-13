"""API serializers — convert core model objects to JSON-safe dicts.

All functions are pure: no I/O, no side effects.
Field mappings follow the API contract defined in requirements.md:
- DoubtRecord.current_state → "state"
- DoubtRecord.assigned_to  → "assignee"
"""
from __future__ import annotations

from the_door.core.diff.provenance_membrane import derive_provenance
from the_door.models import DoubtRecord, TimelineResult, VersionSnapshot


def serialize_snapshot(snapshot: VersionSnapshot) -> dict:
    """Serialize VersionSnapshot to API response format (Req 4 AC3).

    Returns: {version_id, timestamp, trigger, label, git_tags, provenance}

    provenance 是 bare 字串（current/legacy/unknown）——viewer 是人類面，
    依 report_membrane 慣例不升膜；膜投影只在 agent 邊界（MCP snapshot_list）。
    """
    return {
        "version_id": snapshot.version_id,
        "timestamp": snapshot.timestamp,
        "trigger": snapshot.trigger,
        "label": snapshot.label,
        "git_tags": list(snapshot.git_tags),
        "provenance": derive_provenance(snapshot.contract_version),
    }


def serialize_doubt(doubt: DoubtRecord) -> dict:
    """Serialize DoubtRecord to API response format (Req 8 AC3).

    Field mappings:
    - current_state → state   (clearer for frontend)
    - assigned_to   → assignee (clearer for frontend)
    - source_node preserved as-is
    """
    return {
        "doubt_id": doubt.doubt_id,
        "doubt_type": doubt.doubt_type,
        "state": doubt.current_state,
        "source_node": doubt.source_node,
        "created_at": doubt.created_at,
        "assignee": doubt.assigned_to,
    }


def serialize_timeline_result(result: TimelineResult) -> dict:
    """Serialize TimelineResult to API response format (Req 9 AC3)."""
    return {
        "snapshot_count": result.snapshot_count,
        "time_range_start": result.time_range_start,
        "time_range_end": result.time_range_end,
        "feature_timelines": [
            {
                "feature_id": ft.feature_id,
                "current_state": ft.current_state,
                "current_label": ft.current_label,
                "change_count": ft.change_count,
                "first_seen_timestamp": ft.first_seen_timestamp,
                "last_seen_timestamp": ft.last_seen_timestamp,
                "drift_event_count": len(ft.drift_events),
            }
            for ft in result.feature_timelines
        ],
        "summary": {
            "active_count": result.summary.active_count,
            "removed_count": result.summary.removed_count,
            "total_drift_events": result.summary.total_drift_events,
        },
    }


def empty_timeline_result() -> dict:
    """Return empty TimelineResult JSON (Req 9 AC2).

    Used when no snapshots exist — avoids calling TimelineEngine unnecessarily.
    """
    return {
        "snapshot_count": 0,
        "time_range_start": None,
        "time_range_end": None,
        "feature_timelines": [],
        "summary": {
            "active_count": 0,
            "removed_count": 0,
            "total_drift_events": 0,
        },
    }
