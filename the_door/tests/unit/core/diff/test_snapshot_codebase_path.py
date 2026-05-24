"""Tests for VersionSnapshot.codebase_path serialization / deserialization."""
import json
import pytest
from pathlib import Path
from the_door.core.diff.snapshot_store import SnapshotStore
from the_door.models import VersionSnapshot


def _make_store_with_snapshot(tmp_path, codebase_path=None):
    """Helper: create SnapshotStore using explicit root and write one snapshot."""
    store = SnapshotStore(tmp_path, store_root=tmp_path / "store")
    snapshot = store.create_snapshot(
        l1_snapshot={},
        feature_relations=[],
        analyzed_files=[],
        label="test",
    )
    return store, snapshot


def test_serialize_codebase_path_present(tmp_path):
    """codebase_path on VersionSnapshot is written to JSON."""
    store = SnapshotStore(tmp_path, store_root=tmp_path / "store")
    snap = store.create_snapshot(
        l1_snapshot={}, feature_relations=[], analyzed_files=[], label="t"
    )
    snap_file = (tmp_path / "store" / "snapshots" / f"{snap.version_id}.json")
    data = json.loads(snap_file.read_text(encoding="utf-8"))
    # codebase_path should be present in JSON (value may be None or str)
    assert "codebase_path" in data


def test_serialize_codebase_path_is_project_root(tmp_path):
    """codebase_path in JSON equals str(project_root) passed to SnapshotStore."""
    store = SnapshotStore(tmp_path, store_root=tmp_path / "store")
    snap = store.create_snapshot(
        l1_snapshot={}, feature_relations=[], analyzed_files=[], label="t"
    )
    snap_file = (tmp_path / "store" / "snapshots" / f"{snap.version_id}.json")
    data = json.loads(snap_file.read_text(encoding="utf-8"))
    assert data["codebase_path"] == str(tmp_path)


def test_serialize_codebase_path_none_when_missing(tmp_path):
    """If VersionSnapshot.codebase_path is None, JSON field is null."""
    store = SnapshotStore(tmp_path, store_root=tmp_path / "store")
    # Use _serialize_snapshot directly with a snapshot that has codebase_path=None
    snap = VersionSnapshot(
        version_id="test-id",
        timestamp="2026-01-01T00:00:00+00:00",
        trigger="manual",
        codebase_path=None,
    )
    data = store._serialize_snapshot(snap)
    assert data["codebase_path"] is None


def test_deserialize_codebase_path_from_json(tmp_path):
    """Deserializing JSON with codebase_path string yields Path object."""
    store = SnapshotStore(tmp_path, store_root=tmp_path / "store")
    raw = {
        "version_id": "abc",
        "timestamp": "2026-01-01T00:00:00+00:00",
        "trigger": "manual",
        "l1_snapshot": {},
        "analyzed_files": [],
        "codebase_path": "/some/path",
        "git_tags": [],
    }
    snap = store._deserialize_snapshot(raw)
    assert snap.codebase_path == Path("/some/path")


def test_deserialize_old_format_no_codebase_path(tmp_path):
    """Old JSON without codebase_path field → codebase_path is None (backward compat)."""
    store = SnapshotStore(tmp_path, store_root=tmp_path / "store")
    raw = {
        "version_id": "abc",
        "timestamp": "2026-01-01T00:00:00+00:00",
        "trigger": "manual",
        "l1_snapshot": {},
        "analyzed_files": [],
        "git_tags": [],
    }
    snap = store._deserialize_snapshot(raw)
    assert snap.codebase_path is None


def test_roundtrip_codebase_path(tmp_path):
    """Serialize then deserialize preserves codebase_path."""
    store = SnapshotStore(tmp_path, store_root=tmp_path / "store")
    original = VersionSnapshot(
        version_id="abc",
        timestamp="2026-01-01T00:00:00+00:00",
        trigger="manual",
        codebase_path=tmp_path / "my_project",
    )
    data = store._serialize_snapshot(original)
    restored = store._deserialize_snapshot(data)
    assert restored.codebase_path == original.codebase_path


def test_create_snapshot_writes_codebase_path(tmp_path):
    """create_snapshot auto-sets codebase_path to project_root."""
    store = SnapshotStore(tmp_path, store_root=tmp_path / "store")
    snap = store.create_snapshot(
        l1_snapshot={}, feature_relations=[], analyzed_files=[], label="t"
    )
    assert snap.codebase_path == tmp_path
