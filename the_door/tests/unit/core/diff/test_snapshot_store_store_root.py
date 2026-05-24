"""Tests for SnapshotStore store_root parameter and ProjectIdentity integration."""
import pytest
from pathlib import Path
from the_door.core.diff.snapshot_store import SnapshotStore


def test_no_project_id_no_legacy_uses_default_snapshots_dir(tmp_path):
    """store_root=None, no project.id, no legacy → default .the-door/snapshots location."""
    store = SnapshotStore(tmp_path)
    assert store._snapshots_dir == tmp_path / ".the-door" / "snapshots"


def test_no_project_id_no_legacy_does_not_raise(tmp_path):
    """SnapshotStore init must not raise even when nothing is initialized."""
    store = SnapshotStore(tmp_path)  # should not raise
    assert store is not None


def test_legacy_store_uses_codebase_snapshots_dir(tmp_path):
    """No project.id but has old .the-door/snapshots/ → legacy fallback, dir preserved."""
    (tmp_path / ".the-door" / "snapshots").mkdir(parents=True)
    store = SnapshotStore(tmp_path)
    assert store._snapshots_dir == tmp_path / ".the-door" / "snapshots"


def test_explicit_store_root_used_directly(tmp_path):
    """store_root=Path(...) passed → used directly, ProjectIdentity not consulted."""
    explicit_root = tmp_path / "custom_store"
    store = SnapshotStore(tmp_path, store_root=explicit_root)
    assert store._snapshots_dir == explicit_root / "snapshots"
    assert store._structures_dir == explicit_root / "structures"


def test_explicit_store_root_no_project_identity_side_effects(tmp_path):
    """When store_root is explicit, project.id file must NOT be created."""
    explicit_root = tmp_path / "custom_store"
    SnapshotStore(tmp_path, store_root=explicit_root)
    assert not (tmp_path / ".the-door" / "project.id").exists()


def test_project_id_ok_uses_central_store(tmp_path):
    """project.id exists + central store dir exists + has json → snapshots_dir points to central store."""
    import uuid, shutil
    new_id = str(uuid.uuid4())
    id_file = tmp_path / ".the-door" / "project.id"
    id_file.parent.mkdir(parents=True)
    id_file.write_text(new_id, encoding="utf-8")

    central = Path.home() / ".the-door" / "store" / new_id
    snaps = central / "snapshots"
    snaps.mkdir(parents=True, exist_ok=True)
    (snaps / "snap.json").write_text("{}", encoding="utf-8")

    try:
        store = SnapshotStore(tmp_path)
        assert store._snapshots_dir == snaps
        assert store._structures_dir == central / "structures"
    finally:
        shutil.rmtree(central, ignore_errors=True)


def test_existing_call_without_store_root_compatible(tmp_path):
    """Legacy call: SnapshotStore(path) with no store_root arg works and returns default dir."""
    store = SnapshotStore(tmp_path)
    # Must be callable, no TypeError
    assert store._snapshots_dir == tmp_path / ".the-door" / "snapshots"
