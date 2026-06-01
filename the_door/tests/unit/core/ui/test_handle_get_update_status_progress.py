"""Test update_status payload includes progress field when set."""
from __future__ import annotations

import pytest


def _make_handler(tmp_path):
    from the_door.core.ui.api.context import APIContext
    from the_door.core.ui.api.handlers.analysis import AnalysisHandlers
    from the_door.core.ui.job_store import JobStore
    store = JobStore()
    ctx = APIContext(
        _project_root_fn=lambda: tmp_path,
        _job_store_fn=lambda: store,
        _switch_project_fn=lambda path, force: None,
    )
    return AnalysisHandlers(ctx), store


def test_payload_includes_progress_null_by_default(tmp_path):
    handler, store = _make_handler(tmp_path)
    job = store.try_create_job()
    code, body = handler.update_status(job_id=job.job_id)
    assert code == 200
    assert "progress" in body
    assert body["progress"] is None


def test_payload_includes_progress_dict_when_set(tmp_path):
    handler, store = _make_handler(tmp_path)
    job = store.try_create_job()
    job.update_progress({
        "files_done": 42, "files_total": 100,
        "current_file": "src/foo.py", "current_root": "new",
    })
    code, body = handler.update_status(job_id=job.job_id)
    assert body["progress"] == {
        "files_done": 42, "files_total": 100,
        "current_file": "src/foo.py", "current_root": "new",
    }


def test_payload_progress_reflects_latest_update(tmp_path):
    handler, store = _make_handler(tmp_path)
    job = store.try_create_job()
    job.update_progress({"files_done": 1, "files_total": 10, "current_file": "a.py", "current_root": "new"})
    job.update_progress({"files_done": 9, "files_total": 10, "current_file": "z.py", "current_root": "new"})
    code, body = handler.update_status(job_id=job.job_id)
    assert body["progress"]["files_done"] == 9
    assert body["progress"]["current_file"] == "z.py"
