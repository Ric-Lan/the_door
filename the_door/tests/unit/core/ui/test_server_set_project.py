"""Tests for UIServer._switch_project() and lock behavior."""
from __future__ import annotations
from pathlib import Path
from unittest.mock import MagicMock
import pytest
from the_door.core.ui.server import UIServer
from the_door.core.ui.job_store import JobStore


def _make_server(tmp_path: Path) -> UIServer:
    viewer_dir = tmp_path / "viewer"
    viewer_dir.mkdir()
    (viewer_dir / "index.html").write_text("<html></html>", encoding="utf-8")
    return UIServer(project_root=tmp_path, viewer_dir=viewer_dir, port=0)


def test_switch_project_returns_switched_on_valid_path(tmp_path):
    server = _make_server(tmp_path)
    new_path = tmp_path / "new_project"
    new_path.mkdir()
    result = server._switch_project(new_path, force=False)
    assert result["status"] == "switched"
    assert result["path"] == str(new_path)
    assert server._project_root == new_path


def test_switch_project_returns_conflict_when_job_running(tmp_path):
    server = _make_server(tmp_path)
    job = server._job_store.try_create_job()
    new_path = tmp_path / "new_project"
    new_path.mkdir()
    result = server._switch_project(new_path, force=False)
    assert result["status"] == "conflict"
    assert result["active_job_id"] == job.job_id
    # project_root NOT changed
    assert server._project_root == tmp_path


def test_switch_project_force_cancels_running_job(tmp_path):
    server = _make_server(tmp_path)
    old_store = server._job_store
    job = server._job_store.try_create_job()
    new_path = tmp_path / "new_project"
    new_path.mkdir()
    result = server._switch_project(new_path, force=True)
    assert result["status"] == "switched"
    # old job was failed by _switch_project; new store is empty
    assert old_store.get_running_job_id() is None
    assert not server._job_store.has_running_job


def test_switch_project_replaces_job_store_on_success(tmp_path):
    server = _make_server(tmp_path)
    old_job_store = server._job_store
    new_path = tmp_path / "new_project"
    new_path.mkdir()
    server._switch_project(new_path, force=False)
    assert server._job_store is not old_job_store


def test_switch_project_api_handlers_sees_new_root(tmp_path):
    server = _make_server(tmp_path)
    new_path = tmp_path / "new_project"
    new_path.mkdir()
    server._switch_project(new_path, force=False)
    # APIHandlers uses lambda — must return new path
    assert server._api_handlers._project_root == new_path
