from pathlib import Path

import pytest


def test_systemstate_is_frozen_hashable():
    from the_door.core.guidance.state import SystemState, SnapshotEntry, StateWarning

    state = SystemState(
        project_path=Path("/tmp/x"),
        has_dot_the_door=False,
        has_structure_json=False,
        snapshots=(),
        l2_features_analyzed=frozenset(),
        has_api_key=False,
        api_provider=None,
        warnings=(),
    )
    # Frozen
    with pytest.raises((AttributeError, Exception)):
        state.has_dot_the_door = True
    # Hashable
    hash(state)
    # has_snapshots derived
    assert state.has_snapshots is False
    assert state.latest_snapshot is None

    # Re-export identity: SnapshotEntry from state IS the authoritative class
    from the_door.core.diff.snapshot_store import SnapshotEntry as _AuthoritativeEntry
    assert SnapshotEntry is _AuthoritativeEntry


def test_to_json_dict_serializes_systemstate():
    from the_door.core.guidance.state import SystemState, SnapshotEntry, StateWarning, to_json_dict
    state = SystemState(
        project_path=Path("/tmp/x"),
        has_dot_the_door=True,
        has_structure_json=True,
        snapshots=(SnapshotEntry(
            version_id="vid1", label="v1.0.0",
            git_tags=("v1.0.0",), commit_hash="abc123",
            timestamp="2026-01-01T00:00:00Z",
            has_persisted_structure=True,
        ),),
        l2_features_analyzed=frozenset({"feat-b", "feat-a"}),
        has_api_key=True,
        api_provider="anthropic",
        warnings=(),
    )
    out = to_json_dict(state)
    assert out["project_path"] == Path("/tmp/x").as_posix()
    assert out["has_snapshots"] is True  # property
    assert out["latest_snapshot"]["version_id"] == "vid1"
    # frozenset → sorted list
    assert out["l2_features_analyzed"] == ["feat-a", "feat-b"]
    # tuple → list
    assert isinstance(out["snapshots"], list)
    assert isinstance(out["snapshots"][0]["git_tags"], list)
