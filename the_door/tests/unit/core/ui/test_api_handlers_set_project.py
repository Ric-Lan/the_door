"""Tests for handle_post_set_project and JobStore.get_running_job_id."""
from __future__ import annotations

import pytest

from the_door.core.ui.api_handlers import APIHandlers
from the_door.core.ui.job_store import JobStore


def test_get_running_job_id_returns_none_when_no_job():
    store = JobStore()
    assert store.get_running_job_id() is None


def test_get_running_job_id_returns_id_when_running():
    store = JobStore()
    job = store.try_create_job()
    assert store.get_running_job_id() == job.job_id


def test_get_running_job_id_returns_none_after_complete():
    store = JobStore()
    job = store.try_create_job()
    store.complete_job(job.job_id)
    assert store.get_running_job_id() is None


def test_api_handlers_backward_compatible_with_direct_values(tmp_path):
    """Old call style still works."""
    store = JobStore()
    handlers = APIHandlers(project_root=tmp_path, job_store=store)
    assert handlers._project_root == tmp_path
    assert handlers._job_store is store


def test_api_handlers_callable_injection_returns_current_value(tmp_path):
    """project_root_fn is called each time _project_root is accessed."""
    store = JobStore()
    path_holder = [tmp_path]
    handlers = APIHandlers(
        project_root_fn=lambda: path_holder[0],
        job_store_fn=lambda: store,
    )
    assert handlers._project_root == tmp_path
    new_path = tmp_path / "sub"
    new_path.mkdir()
    path_holder[0] = new_path
    assert handlers._project_root == new_path   # sees updated value


def test_api_handlers_switch_project_fn_is_called(tmp_path):
    """switch_project_fn is stored and callable."""
    called_with = []
    def my_switch(path, force):
        called_with.append((path, force))
        return {"status": "switched", "path": str(path)}

    handlers = APIHandlers(
        project_root=tmp_path,
        job_store=JobStore(),
        switch_project_fn=my_switch,
    )
    handlers._switch_project_fn(tmp_path, False)
    assert called_with == [(tmp_path, False)]


# ------------------------------------------------------------------
# handle_post_set_project tests
# ------------------------------------------------------------------

import os


def _make_handlers(tmp_path, switch_fn=None):
    return APIHandlers(
        project_root=tmp_path,
        job_store=JobStore(),
        switch_project_fn=switch_fn or (lambda path, force: {"status": "switched", "path": str(path)}),
    )


def test_set_project_returns_200_on_valid_path(tmp_path):
    handlers = _make_handlers(tmp_path)
    result_path = tmp_path / "proj"
    result_path.mkdir()
    status, body = handlers.handle_post_set_project({"path": str(result_path)})
    assert status == 200
    assert body["status"] == "switched"


def test_set_project_returns_400_on_nonexistent_path(tmp_path):
    handlers = _make_handlers(tmp_path)
    status, body = handlers.handle_post_set_project({"path": str(tmp_path / "nonexistent")})
    assert status == 400
    assert body["status"] == "error"


def test_set_project_returns_400_on_file_not_dir(tmp_path):
    f = tmp_path / "file.txt"
    f.write_text("x", encoding="utf-8")
    handlers = _make_handlers(tmp_path)
    status, body = handlers.handle_post_set_project({"path": str(f)})
    assert status == 400
    assert body["status"] == "error"


def test_set_project_returns_400_on_empty_path(tmp_path):
    handlers = _make_handlers(tmp_path)
    status, body = handlers.handle_post_set_project({"path": ""})
    assert status == 400
    assert body["status"] == "error"


def test_set_project_returns_409_on_conflict(tmp_path):
    new_path = tmp_path / "new"
    new_path.mkdir()
    handlers = _make_handlers(
        tmp_path,
        switch_fn=lambda path, force: {"status": "conflict", "active_job_id": "job-1", "message": "busy"},
    )
    status, body = handlers.handle_post_set_project({"path": str(new_path)})
    assert status == 409
    assert body["status"] == "conflict"
    assert "active_job_id" in body


def test_set_project_passes_force_true(tmp_path):
    new_path = tmp_path / "new"
    new_path.mkdir()
    received = []
    def capture_switch(path, force):
        received.append(force)
        return {"status": "switched", "path": str(path)}

    handlers = _make_handlers(tmp_path, switch_fn=capture_switch)
    handlers.handle_post_set_project({"path": str(new_path), "force": True})
    assert received == [True]


def test_set_project_force_defaults_to_false(tmp_path):
    new_path = tmp_path / "new"
    new_path.mkdir()
    received = []
    def capture_switch(path, force):
        received.append(force)
        return {"status": "switched", "path": str(path)}

    handlers = _make_handlers(tmp_path, switch_fn=capture_switch)
    handlers.handle_post_set_project({"path": str(new_path)})
    assert received == [False]
