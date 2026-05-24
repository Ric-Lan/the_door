"""Integration tests: Store decoupling — SnapshotStore + ProjectIdentity end-to-end."""
from __future__ import annotations

import shutil
import uuid
import pytest
from pathlib import Path

from the_door.core.diff.snapshot_store import SnapshotStore
from the_door.core.project_identity import ProjectIdentity
from the_door.models import FeatureSummary


def _make_feature(fid: str) -> FeatureSummary:
    return FeatureSummary(
        feature_id=fid, label=fid, description="d",
        source_node_count=0, confidence="high",
    )


# ── New project init flow ──────────────────────────────────────────────────────

def test_new_project_init_creates_central_store(tmp_path):
    """ProjectIdentity.get_or_create → SnapshotStore uses central store."""
    uid = ProjectIdentity.get_or_create(tmp_path)
    central = Path.home() / ".the-door" / "store" / uid
    try:
        store = SnapshotStore(tmp_path)
        store._snapshots_dir.mkdir(parents=True, exist_ok=True)
        snap = store.create_snapshot(
            l1_snapshot={"feat-a": _make_feature("feat-a")},
            feature_relations=[], analyzed_files=[], label="v1",
        )
        listed = store.list_snapshots()
        assert any(s.version_id == snap.version_id for s in listed)
    finally:
        shutil.rmtree(central, ignore_errors=True)


def test_store_readable_after_project_id_moved_to_new_path(tmp_path):
    """Copying project.id to a new path → same UUID → same central store."""
    uid = ProjectIdentity.get_or_create(tmp_path)
    central = Path.home() / ".the-door" / "store" / uid

    try:
        store = SnapshotStore(tmp_path)
        store._snapshots_dir.mkdir(parents=True, exist_ok=True)
        snap = store.create_snapshot(
            l1_snapshot={"feat-x": _make_feature("feat-x")},
            feature_relations=[], analyzed_files=[], label="original",
        )

        # Simulate moving codebase to a new directory
        new_path = tmp_path.parent / (tmp_path.name + "_moved")
        new_path.mkdir()
        id_dir = new_path / ".the-door"
        id_dir.mkdir()
        (id_dir / "project.id").write_text(uid, encoding="utf-8")

        store_new = SnapshotStore(new_path)
        assert store_new._snapshots_dir == store._snapshots_dir
        listed = store_new.list_snapshots()
        assert any(s.version_id == snap.version_id for s in listed)
    finally:
        shutil.rmtree(central, ignore_errors=True)


# ── Legacy store backward compatibility ────────────────────────────────────────

def test_legacy_store_uses_codebase_snapshots(tmp_path):
    """No project.id + .the-door/snapshots/ exists → SnapshotStore uses legacy path."""
    snapshots_dir = tmp_path / ".the-door" / "snapshots"
    snapshots_dir.mkdir(parents=True)

    result = ProjectIdentity.resolve_store_root(tmp_path)
    assert result.status == "legacy"

    store = SnapshotStore(tmp_path)
    assert store._snapshots_dir == snapshots_dir


def test_legacy_store_list_snapshots_reads_existing(tmp_path):
    """Legacy store can list snapshots created in the old location."""
    store = SnapshotStore(tmp_path)  # uses default .the-door/snapshots
    snap = store.create_snapshot(
        l1_snapshot={}, feature_relations=[], analyzed_files=[], label="legacy-snap",
    )
    # A new SnapshotStore on the same path can read it (same resolved path)
    store2 = SnapshotStore(tmp_path)
    listed = store2.list_snapshots()
    assert any(s.version_id == snap.version_id for s in listed)


def test_legacy_snapshot_has_no_codebase_path(tmp_path):
    """A snapshot written without codebase_path (old format) deserializes cleanly."""
    import json
    snap_dir = tmp_path / ".the-door" / "snapshots"
    snap_dir.mkdir(parents=True)
    vid = str(uuid.uuid4())
    (snap_dir / f"{vid}.json").write_text(
        json.dumps({
            "version_id": vid,
            "timestamp": "2026-01-01T00:00:00+00:00",
            "trigger": "manual",
            "l1_snapshot": {},
            "analyzed_files": [],
            "git_tags": [],
        }),
        encoding="utf-8",
    )
    store = SnapshotStore(tmp_path)
    listed = store.list_snapshots()
    snap = next(s for s in listed if s.version_id == vid)
    assert snap.codebase_path is None  # backward compatible


# ── path_error store still constructs ────────────────────────────────────────

def test_path_error_store_constructs_without_raising(tmp_path):
    """project.id exists but store dir doesn't → SnapshotStore still constructs."""
    new_id = str(uuid.uuid4())
    id_file = tmp_path / ".the-door" / "project.id"
    id_file.parent.mkdir(parents=True)
    id_file.write_text(new_id, encoding="utf-8")
    # Don't create the central store dir

    result = ProjectIdentity.resolve_store_root(tmp_path)
    assert result.status == "path_error"

    store = SnapshotStore(tmp_path)  # should NOT raise
    assert store._snapshots_dir is not None


# ── Existing callers compatibility ────────────────────────────────────────────

def test_legacy_call_SnapshotStore_without_store_root(tmp_path):
    """SnapshotStore(path) without store_root arg works identically to before."""
    store = SnapshotStore(tmp_path)
    assert store._snapshots_dir == tmp_path / ".the-door" / "snapshots"


def test_create_snapshot_writes_codebase_path_field(tmp_path):
    """create_snapshot auto-populates codebase_path from project_root."""
    store = SnapshotStore(tmp_path)
    snap = store.create_snapshot(
        l1_snapshot={}, feature_relations=[], analyzed_files=[], label="test",
    )
    assert snap.codebase_path == tmp_path
