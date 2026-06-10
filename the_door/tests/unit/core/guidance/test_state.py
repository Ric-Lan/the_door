import json
from pathlib import Path

import pytest

from the_door.core.guidance.state import StateInspector


def test_inspect_empty_dir_returns_valid_state(tmp_path):
    state = StateInspector(tmp_path).inspect()
    assert state.has_dot_the_door is False
    assert state.snapshots == ()
    assert state.warnings == ()
    assert state.l2_features_analyzed == frozenset()
    assert state.edge_residue_stamped is False  # C5: no .the-door → not stamped


def test_c5_1_edge_residue_stamped_reflects_checklist(tmp_path):
    """C5-1：checklist 有 edge_residue 蓋章 → True；無 checklist／只有別的 stage → False。"""
    from the_door.core.checklist import STAGE_EDGE_RESIDUE, STAGE_SNAPSHOT_WRITE, stamp_stage

    # 無 checklist（但有 .the-door 目錄）→ False
    (tmp_path / ".the-door").mkdir()
    assert StateInspector(tmp_path).inspect().edge_residue_stamped is False

    # 只有非 edge_residue 的 stage → False
    stamp_stage(tmp_path, STAGE_SNAPSHOT_WRITE, contract_version="1", details={"version_id": "v"})
    assert StateInspector(tmp_path).inspect().edge_residue_stamped is False

    # edge_residue 蓋章 → True
    stamp_stage(tmp_path, STAGE_EDGE_RESIDUE, covered_nodes=["a"], contract_version="1")
    assert StateInspector(tmp_path).inspect().edge_residue_stamped is True


def _write_snapshot(tmp_path, vid, drift=False):
    snap_dir = tmp_path / ".the-door" / "snapshots"
    snap_dir.mkdir(parents=True, exist_ok=True)
    feat = {"feature_id": "feat-x", "label": "x", "description": "d",
            "trigger": "t", "trigger_description": "td",
            "confidence": "high", "confidence_reason": "r",
            "source_node_count": 5 if drift else 2,
            "source_nodes": [] if drift else ["a", "b"]}
    (snap_dir / f"{vid}.json").write_text(json.dumps({
        "version_id": vid,
        "label": None,
        "git_tags": [],
        "commit_hash": None,
        "timestamp": "2026-01-01T00:00:00Z",
        "analyzed_files": [],
        "feature_relations_snapshot": [],
        "l1_snapshot": {"feat-x": feat},
    }))


def test_inspect_snapshot_with_persisted_structure(tmp_path):
    _write_snapshot(tmp_path, "vid1")
    struct_dir = tmp_path / ".the-door" / "structures"
    struct_dir.mkdir()
    (struct_dir / "vid1.json.gz").write_bytes(b"placeholder")
    state = StateInspector(tmp_path).inspect()
    assert len(state.snapshots) == 1
    assert state.snapshots[0].has_persisted_structure is True


def test_inspect_snapshot_missing_structure_no_warning(tmp_path):
    _write_snapshot(tmp_path, "vid1")
    state = StateInspector(tmp_path).inspect()
    assert state.snapshots[0].has_persisted_structure is False
    assert not any(w.code == "structure_corrupted" for w in state.warnings)


def test_inspect_detects_source_nodes_drift(tmp_path):
    _write_snapshot(tmp_path, "vid1", drift=True)
    state = StateInspector(tmp_path).inspect()
    drift_warnings = [w for w in state.warnings if w.code == "source_nodes_drift"]
    assert len(drift_warnings) == 1
    assert "feat-x" in drift_warnings[0].location


def test_inspect_corrupted_snapshot_emits_warning_continues(tmp_path):
    (tmp_path / ".the-door" / "snapshots").mkdir(parents=True)
    (tmp_path / ".the-door" / "snapshots" / "bad.json").write_text("{not-json")
    _write_snapshot(tmp_path, "good_vid")
    state = StateInspector(tmp_path).inspect()
    assert len(state.snapshots) == 1
    assert state.snapshots[0].version_id == "good_vid"
    assert any(w.code == "snapshot_corrupted" for w in state.warnings)


def test_inspect_completes_under_50ms(perf_project_fixture):
    import time
    start = time.perf_counter()
    state = StateInspector(perf_project_fixture).inspect()
    elapsed = time.perf_counter() - start
    assert state.has_dot_the_door is True
    assert len(state.snapshots) == 10
    assert elapsed < 0.05, f"inspection took {elapsed*1000:.1f}ms, over 50ms budget"


def test_systemstate_is_frozen_hashable():
    from the_door.core.guidance.state import SystemState, SnapshotEntry, StateWarning

    state = SystemState(
        project_path=Path("/tmp/x"),
        has_dot_the_door=False,
        has_structure_json=False,
        snapshots=(),
        l2_features_analyzed=frozenset(),
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
