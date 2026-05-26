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
