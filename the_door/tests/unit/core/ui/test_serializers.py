"""Tests for API serializers."""
from __future__ import annotations

import json


def _make_snapshot(**kwargs):
    from the_door.models import VersionSnapshot
    defaults = {
        "version_id": "v1",
        "timestamp": "2025-01-01T00:00:00+00:00",
        "trigger": "manual",
        "label": "release-1",
        "git_tags": ["v1.0"],
    }
    defaults.update(kwargs)
    return VersionSnapshot(**defaults)


def _make_doubt(**kwargs):
    from the_door.models import DoubtRecord
    defaults = {
        "doubt_id": "d1",
        "source_node": "feat-auth",
        "doubt_type": "out_of_scope",
        "current_state": "discovered",
        "created_by": "system",
        "created_at": "2025-01-01T00:00:00+00:00",
        "updated_at": "2025-01-01T00:00:00+00:00",
        "assigned_to": "alice",
    }
    defaults.update(kwargs)
    return DoubtRecord(**defaults)


def _make_timeline_result(**kwargs):
    from the_door.models import TimelineResult, TimelineSummary
    defaults = {
        "snapshot_count": 2,
        "time_range_start": "2025-01-01T00:00:00+00:00",
        "time_range_end": "2025-06-01T00:00:00+00:00",
        "feature_timelines": [],
        "summary": TimelineSummary(active_count=3, removed_count=1, total_drift_events=2),
    }
    defaults.update(kwargs)
    return TimelineResult(**defaults)


def test_serialize_snapshot_fields():
    from the_door.core.ui.serializers import serialize_snapshot
    snap = _make_snapshot()
    result = serialize_snapshot(snap)
    assert result["version_id"] == "v1"
    assert result["timestamp"] == "2025-01-01T00:00:00+00:00"
    assert result["trigger"] == "manual"
    assert result["label"] == "release-1"
    assert result["git_tags"] == ["v1.0"]
    json.dumps(result)


def test_serialize_snapshot_null_label():
    from the_door.core.ui.serializers import serialize_snapshot
    snap = _make_snapshot(label=None)
    result = serialize_snapshot(snap)
    assert result["label"] is None
    json.dumps(result)


def test_serialize_snapshot_provenance_current():
    from the_door.core.ui.serializers import serialize_snapshot
    from the_door.models.snapshot import SNAPSHOT_CONTRACT_VERSION
    snap = _make_snapshot(contract_version=SNAPSHOT_CONTRACT_VERSION)
    result = serialize_snapshot(snap)
    assert result["provenance"] == "current"
    json.dumps(result)


def test_serialize_snapshot_provenance_legacy():
    from the_door.core.ui.serializers import serialize_snapshot
    snap = _make_snapshot(contract_version="0-nonexistent")
    result = serialize_snapshot(snap)
    assert result["provenance"] == "legacy"


def test_serialize_snapshot_provenance_unknown_for_prestamp():
    from the_door.core.ui.serializers import serialize_snapshot
    snap = _make_snapshot(contract_version=None)
    result = serialize_snapshot(snap)
    assert result["provenance"] == "unknown"


def test_serialize_doubt_field_mapping():
    from the_door.core.ui.serializers import serialize_doubt
    doubt = _make_doubt()
    result = serialize_doubt(doubt)
    assert result["state"] == "discovered"
    assert "current_state" not in result
    assert result["assignee"] == "alice"
    assert "assigned_to" not in result
    assert result["source_node"] == "feat-auth"
    assert result["doubt_id"] == "d1"
    assert result["doubt_type"] == "out_of_scope"
    assert result["created_at"] == "2025-01-01T00:00:00+00:00"
    json.dumps(result)


def test_serialize_doubt_null_assignee():
    from the_door.core.ui.serializers import serialize_doubt
    doubt = _make_doubt(assigned_to=None)
    result = serialize_doubt(doubt)
    assert result["assignee"] is None
    json.dumps(result)


def test_serialize_timeline_result():
    from the_door.core.ui.serializers import serialize_timeline_result
    tr = _make_timeline_result()
    result = serialize_timeline_result(tr)
    assert result["snapshot_count"] == 2
    assert result["time_range_start"] == "2025-01-01T00:00:00+00:00"
    assert result["time_range_end"] == "2025-06-01T00:00:00+00:00"
    assert isinstance(result["feature_timelines"], list)
    assert result["summary"]["active_count"] == 3
    assert result["summary"]["removed_count"] == 1
    assert result["summary"]["total_drift_events"] == 2
    json.dumps(result)


def test_empty_timeline_result():
    from the_door.core.ui.serializers import empty_timeline_result
    result = empty_timeline_result()
    assert result["snapshot_count"] == 0
    assert result["time_range_start"] is None
    assert result["time_range_end"] is None
    assert result["feature_timelines"] == []
    assert result["summary"]["active_count"] == 0
    assert result["summary"]["removed_count"] == 0
    assert result["summary"]["total_drift_events"] == 0
    json.dumps(result)
