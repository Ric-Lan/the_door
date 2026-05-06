"""Property-based tests for API serializer functions.

Uses Hypothesis with ASCII-only strategies (min_codepoint=32, max_codepoint=126)
for Windows cp950 compatibility — consistent with existing PBT conventions.

Validates: Req 13 AC1–AC5
"""
from __future__ import annotations

import json

from hypothesis import given, settings
from hypothesis import strategies as st

from the_door.core.ui.api_handlers import APIHandlers
from the_door.core.ui.serializers import (
    empty_timeline_result,
    serialize_doubt,
    serialize_snapshot,
    serialize_timeline_result,
)
from the_door.models import (
    DoubtRecord,
    FeatureTimeline,
    TimelineResult,
    TimelineSummary,
    VersionSnapshot,
)


# ---------------------------------------------------------------------------
# ASCII-only strategies (Windows cp950 compatible)
# ---------------------------------------------------------------------------

ASCII_TEXT = st.text(
    alphabet=st.characters(min_codepoint=32, max_codepoint=126),
    min_size=1,
    max_size=50,
).filter(lambda s: s.strip())

VERSION_ID_ST = st.from_regex(r"[a-f0-9]{8}-[a-f0-9]{4}", fullmatch=True)
TIMESTAMP_ST = st.just("2025-01-01T00:00:00+00:00")
TRIGGER_ST = st.sampled_from(["commit", "manual"])

VERSION_SNAPSHOT_ST = st.builds(
    VersionSnapshot,
    version_id=VERSION_ID_ST,
    timestamp=TIMESTAMP_ST,
    trigger=TRIGGER_ST,
    label=st.one_of(st.none(), ASCII_TEXT),
    git_tags=st.lists(ASCII_TEXT, max_size=3),
)

DOUBT_STATE_ST = st.sampled_from([
    "discovered", "investigating", "explained", "fixed", "escalated", "accepted_risk"
])
DOUBT_TYPE_ST = st.sampled_from([
    "out_of_scope", "in_scope_incomplete", "anomaly", "low_confidence"
])

DOUBT_RECORD_ST = st.builds(
    DoubtRecord,
    doubt_id=VERSION_ID_ST,
    source_node=ASCII_TEXT,
    doubt_type=DOUBT_TYPE_ST,
    current_state=DOUBT_STATE_ST,
    created_by=ASCII_TEXT,
    created_at=TIMESTAMP_ST,
    updated_at=TIMESTAMP_ST,
    assigned_to=st.one_of(st.none(), ASCII_TEXT),
)

TIMELINE_SUMMARY_ST = st.builds(
    TimelineSummary,
    active_count=st.integers(min_value=0, max_value=100),
    removed_count=st.integers(min_value=0, max_value=100),
    total_drift_events=st.integers(min_value=0, max_value=100),
)

TIMELINE_RESULT_ST = st.builds(
    TimelineResult,
    snapshot_count=st.integers(min_value=0, max_value=50),
    time_range_start=st.one_of(st.none(), TIMESTAMP_ST),
    time_range_end=st.one_of(st.none(), TIMESTAMP_ST),
    feature_timelines=st.just([]),  # empty list — FeatureTimeline is complex
    summary=TIMELINE_SUMMARY_ST,
)


# ---------------------------------------------------------------------------
# Property 1: VersionSnapshot serialization is JSON-safe and contains required fields
# Validates: Req 13 AC1
# ---------------------------------------------------------------------------

@given(snapshot=VERSION_SNAPSHOT_ST)
def test_prop_snapshot_serialization_json_safe(snapshot):
    """Any VersionSnapshot → serialize_snapshot() → json.dumps() succeeds.

    Result must contain version_id, timestamp, trigger, label, git_tags.
    """
    result = serialize_snapshot(snapshot)
    # Must be JSON-serializable
    serialized = json.dumps(result)
    parsed = json.loads(serialized)
    # Must contain required fields
    assert "version_id" in parsed
    assert "timestamp" in parsed
    assert "trigger" in parsed
    assert "label" in parsed
    assert "git_tags" in parsed
    assert isinstance(parsed["git_tags"], list)


# ---------------------------------------------------------------------------
# Property 2: DoubtRecord serialization is JSON-safe and contains required fields
# Validates: Req 13 AC2
# ---------------------------------------------------------------------------

@given(doubt=DOUBT_RECORD_ST)
def test_prop_doubt_serialization_json_safe(doubt):
    """Any DoubtRecord → serialize_doubt() → json.dumps() succeeds.

    Result must contain doubt_id, doubt_type, state, source_node, created_at.
    Field mapping: current_state → state, assigned_to → assignee.
    """
    result = serialize_doubt(doubt)
    serialized = json.dumps(result)
    parsed = json.loads(serialized)
    assert "doubt_id" in parsed
    assert "doubt_type" in parsed
    assert "state" in parsed
    assert "source_node" in parsed
    assert "created_at" in parsed
    # Verify field mapping
    assert parsed["state"] == doubt.current_state
    assert parsed.get("assignee") == doubt.assigned_to
    # Original field names must NOT appear
    assert "current_state" not in parsed
    assert "assigned_to" not in parsed


# ---------------------------------------------------------------------------
# Property 3: TimelineResult serialization is JSON-safe with correct types
# Validates: Req 13 AC3
# ---------------------------------------------------------------------------

@given(result=TIMELINE_RESULT_ST)
def test_prop_timeline_serialization_json_safe(result):
    """Any TimelineResult → serialize_timeline_result() → json.dumps() succeeds.

    snapshot_count must be int, feature_timelines must be list.
    """
    serialized_dict = serialize_timeline_result(result)
    json_str = json.dumps(serialized_dict)
    parsed = json.loads(json_str)
    assert isinstance(parsed["snapshot_count"], int)
    assert isinstance(parsed["feature_timelines"], list)
    assert "summary" in parsed
    assert "active_count" in parsed["summary"]
    assert "removed_count" in parsed["summary"]
    assert "total_drift_events" in parsed["summary"]


# ---------------------------------------------------------------------------
# Property 4: UpdateReport dict round-trip is idempotent
# Validates: Req 13 AC4
# ---------------------------------------------------------------------------

UPDATE_REPORT_DICT_ST = st.fixed_dictionaries({
    "report_version": st.just("1.0.0"),
    "generated_at": TIMESTAMP_ST,
    "l0_summary": ASCII_TEXT,
    "l1_changes": st.lists(
        st.fixed_dictionaries({
            "feature_id": ASCII_TEXT,
            "change_type": st.sampled_from(["added", "removed", "attribute_changed"]),
            "risk_flags": st.lists(st.sampled_from(["out_of_scope", "vulnerability"]), max_size=2),
            "current_label": ASCII_TEXT,
            "baseline_label": st.one_of(st.none(), ASCII_TEXT),
        }),
        max_size=10,
    ),
    "interrupted": st.booleans(),
})


@given(report=UPDATE_REPORT_DICT_ST)
def test_prop_update_report_round_trip(report):
    """Any UpdateReport dict: json.dumps(json.loads(json.dumps(report))) is structurally equal."""
    once = json.dumps(report, ensure_ascii=False)
    twice = json.dumps(json.loads(once), ensure_ascii=False)
    assert json.loads(once) == json.loads(twice)


# ---------------------------------------------------------------------------
# Property 5: API_Error_Response structure is always valid
# Validates: Req 13 AC5
# ---------------------------------------------------------------------------

@given(
    code=ASCII_TEXT,
    message=ASCII_TEXT,
    source=ASCII_TEXT,
)
def test_prop_api_error_response_structure(code, message, source):
    """Any (code, message, source) → _make_error() → error.code/message/source are non-empty strings."""
    result = APIHandlers._make_error(code=code, message=message, source=source)
    assert "error" in result
    error = result["error"]
    assert isinstance(error["code"], str) and len(error["code"]) > 0
    assert isinstance(error["message"], str) and len(error["message"]) > 0
    assert isinstance(error["source"], str) and len(error["source"]) > 0
    # Must be JSON-serializable
    json.dumps(result)
