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
