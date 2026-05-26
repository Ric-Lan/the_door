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


# ------------------------------------------------------------------
# /api/set-project route tests
# ------------------------------------------------------------------

import json
import socket
import time
from http.client import HTTPConnection


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def running_server(tmp_path):
    import threading as _threading
    viewer_dir = tmp_path / "viewer"
    viewer_dir.mkdir()
    (viewer_dir / "index.html").write_text("<html></html>", encoding="utf-8")
    port = _find_free_port()
    server = UIServer(project_root=tmp_path, viewer_dir=viewer_dir, port=port)
    t = _threading.Thread(target=server.start, daemon=True)
    t.start()
    for _ in range(20):
        try:
            conn = HTTPConnection("127.0.0.1", port, timeout=1)
            conn.request("GET", "/api/status")
            conn.getresponse().read()
            conn.close()
            break
        except Exception:
            time.sleep(0.05)
    yield tmp_path, port
    server.shutdown()


def test_post_set_project_returns_200(running_server, tmp_path):
    project_path, port = running_server
    new_path = tmp_path / "new_project"
    new_path.mkdir()
    conn = HTTPConnection("127.0.0.1", port)
    body = json.dumps({"path": str(new_path)}).encode()
    conn.request("POST", "/api/set-project", body=body,
                 headers={"Content-Type": "application/json", "Content-Length": str(len(body))})
    resp = conn.getresponse()
    data = json.loads(resp.read())
    conn.close()
    assert resp.status == 200
    assert data["status"] == "switched"


def test_get_set_project_returns_405(running_server):
    _, port = running_server
    conn = HTTPConnection("127.0.0.1", port)
    conn.request("GET", "/api/set-project")
    resp = conn.getresponse()
    resp.read()
    conn.close()
    assert resp.status == 405
