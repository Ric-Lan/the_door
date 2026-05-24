import uuid
import pytest
from pathlib import Path
from the_door.core.project_identity import ProjectIdentity, StoreResolutionResult


def test_resolve_not_found_when_no_id_and_no_legacy(tmp_path):
    result = ProjectIdentity.resolve_store_root(tmp_path)
    assert result.status == "not_found"
    assert result.store_root is None


def test_resolve_legacy_when_no_id_but_has_snapshots(tmp_path):
    snapshots = tmp_path / ".the-door" / "snapshots"
    snapshots.mkdir(parents=True)
    result = ProjectIdentity.resolve_store_root(tmp_path)
    assert result.status == "legacy"
    assert result.store_root == tmp_path / ".the-door"


def test_resolve_path_error_when_store_dir_missing(tmp_path):
    new_id = str(uuid.uuid4())
    id_file = tmp_path / ".the-door" / "project.id"
    id_file.parent.mkdir(parents=True)
    id_file.write_text(new_id, encoding="utf-8")
    result = ProjectIdentity.resolve_store_root(tmp_path)
    assert result.status == "path_error"
    assert result.store_root is not None


def test_resolve_empty_when_store_exists_but_no_json(tmp_path):
    new_id = str(uuid.uuid4())
    id_file = tmp_path / ".the-door" / "project.id"
    id_file.parent.mkdir(parents=True)
    id_file.write_text(new_id, encoding="utf-8")
    store_root = Path.home() / ".the-door" / "store" / new_id
    store_root.mkdir(parents=True, exist_ok=True)
    (store_root / "snapshots").mkdir(exist_ok=True)
    try:
        result = ProjectIdentity.resolve_store_root(tmp_path)
        assert result.status == "empty"
        assert result.store_root == store_root
    finally:
        import shutil
        shutil.rmtree(store_root, ignore_errors=True)


def test_resolve_ok_when_store_has_json(tmp_path):
    new_id = str(uuid.uuid4())
    id_file = tmp_path / ".the-door" / "project.id"
    id_file.parent.mkdir(parents=True)
    id_file.write_text(new_id, encoding="utf-8")
    store_root = Path.home() / ".the-door" / "store" / new_id
    snapshots_dir = store_root / "snapshots"
    snapshots_dir.mkdir(parents=True, exist_ok=True)
    (snapshots_dir / "snap.json").write_text("{}", encoding="utf-8")
    try:
        result = ProjectIdentity.resolve_store_root(tmp_path)
        assert result.status == "ok"
        assert result.store_root == store_root
    finally:
        import shutil
        shutil.rmtree(store_root, ignore_errors=True)


def test_resolve_path_error_on_invalid_uuid_content(tmp_path):
    id_file = tmp_path / ".the-door" / "project.id"
    id_file.parent.mkdir(parents=True)
    id_file.write_text("not-a-uuid", encoding="utf-8")
    result = ProjectIdentity.resolve_store_root(tmp_path)
    assert result.status == "path_error"
    assert "not-a-uuid" in result.detail


def test_get_or_create_creates_new_id(tmp_path):
    uid = ProjectIdentity.get_or_create(tmp_path)
    assert uuid.UUID(uid)  # valid UUID, raises if not
    id_file = tmp_path / ".the-door" / "project.id"
    assert id_file.exists()
    assert id_file.read_text(encoding="utf-8").strip() == uid


def test_get_or_create_idempotent(tmp_path):
    uid1 = ProjectIdentity.get_or_create(tmp_path)
    uid2 = ProjectIdentity.get_or_create(tmp_path)
    assert uid1 == uid2


def test_get_or_create_two_calls_same_value(tmp_path):
    uid1 = ProjectIdentity.get_or_create(tmp_path)
    uid2 = ProjectIdentity.get_or_create(tmp_path)
    assert uid1 == uid2


def test_store_resolution_result_none_store_root_not_found():
    r = StoreResolutionResult(store_root=None, status="not_found")
    assert r.store_root is None
    assert r.status == "not_found"


def test_store_resolution_result_ok_with_store_root(tmp_path):
    r = StoreResolutionResult(store_root=tmp_path, status="ok")
    assert r.store_root == tmp_path
    assert r.status == "ok"
