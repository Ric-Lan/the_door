"""Unit tests for timeline_renderer module."""
from __future__ import annotations

from the_door.core.timeline.timeline_renderer import TimelineRenderer
from the_door.models import (
    FeatureSummary,
    FeatureTimeline,
    VersionSnapshot,
)


def _make_feature_summary(
    feature_id: str = "feat-x",
    label: str = "X",
    description: str = "d",
    source_node_count: int = 99,
    confidence: str = "high",
    source_nodes: tuple[str, ...] = ("a", "b", "c"),
    trigger_description: str | None = "td",
) -> FeatureSummary:
    return FeatureSummary(
        feature_id=feature_id,
        label=label,
        description=description,
        source_node_count=source_node_count,
        confidence=confidence,
        trigger_description=trigger_description,
        source_nodes=source_nodes,
    )


def _make_snapshot(
    feature: FeatureSummary,
    version_id: str = "v1",
    timestamp: str = "2024-01-15T00:00:00Z",
) -> VersionSnapshot:
    return VersionSnapshot(
        version_id=version_id,
        timestamp=timestamp,
        trigger="manual",
        l1_snapshot={feature.feature_id: feature},
    )


def _make_feature_timeline(
    feature_id: str = "feat-x",
    label: str = "X",
    timestamp: str = "2024-01-15T00:00:00Z",
) -> FeatureTimeline:
    return FeatureTimeline(
        feature_id=feature_id,
        first_seen_timestamp=timestamp,
        last_seen_timestamp=timestamp,
        change_count=0,
        current_state="active",
        current_label=label,
    )


def test_timeline_renders_source_node_count_from_list_length():
    """render_feature_detail must display len(source_nodes), not source_node_count."""
    feature = _make_feature_summary(
        source_node_count=99,
        source_nodes=("a", "b", "c"),
    )
    snapshot = _make_snapshot(feature)
    timeline = _make_feature_timeline()

    renderer = TimelineRenderer()
    output = renderer.render_feature_detail(timeline, [snapshot])

    assert "Source Nodes: 3" in output
    assert "Source Nodes: 99" not in output
