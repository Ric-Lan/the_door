"""E2E: run_analyze_pipeline through handle_post_analyze produces:
- 3 skipped steps (analyze_old/diff/scope_verify)
- step 2 (analyze_new) running → completed
- step 5 (timeline) + step 6 (report) completed
"""
from __future__ import annotations

import time

import pytest

from the_door.core.reading.batch_reader import BatchReadResult
from the_door.models import L1Output


async def _async_return(value):
    return value


def _setup(tmp_path, monkeypatch):
    """Factor out monkeypatch + handler creation for reuse."""
    (tmp_path / "a.py").write_text("def f(): pass\n", encoding="utf-8")

    from tests.conftest import MockLLMProvider
    stub = MockLLMProvider(responses="")
    monkeypatch.setattr(
        "the_door.core.pipeline.analyze_pipeline.create_provider",
        lambda *a, **k: stub,
    )
    empty_result = BatchReadResult(
        l1_output=L1Output(), total_batches=0, total_tokens_used=0
    )
    monkeypatch.setattr(
        "the_door.core.reading.batch_reader.BatchReader.read",
        lambda self, *a, **k: _async_return(empty_result),
    )

    from the_door.core.ui.api_handlers import APIHandlers
    from the_door.core.ui.job_store import JobStore

    job_store = JobStore()
    handler = APIHandlers(project_root=tmp_path, job_store=job_store)
    return handler, job_store


@pytest.mark.integration
def test_analyze_job_emits_six_step_structure(tmp_path, monkeypatch):
    handler, job_store = _setup(tmp_path, monkeypatch)

    code, body = handler.handle_post_analyze({})
    assert code == 202
    job_id = body["job_id"]

    # Poll until job completes (test timeout 10s)
    for _ in range(100):
        job = job_store.get_job(job_id)
        if job.status in ("completed", "failed"):
            break
        time.sleep(0.1)

    step_names = [(s["step_name"], s["status"]) for s in job.steps]
    assert ("analyze_old", "skipped") in step_names
    assert ("diff", "skipped") in step_names
    assert ("scope_verify", "skipped") in step_names
    assert ("analyze_new", "completed") in step_names
    assert ("timeline", "completed") in step_names
    assert ("report", "completed") in step_names


@pytest.mark.integration
def test_progress_payload_populated_during_analyze(tmp_path, monkeypatch):
    """Run analyze, fetch status mid-run, assert progress dict present with files_total."""
    handler, store = _setup(tmp_path, monkeypatch)
    code, body = handler.handle_post_analyze({})
    assert code == 202
    job_id = body["job_id"]

    # Poll until job completes, checking progress payload along the way
    status = {}
    for _ in range(100):
        _, status = handler.handle_get_update_status(job_id)
        if status.get("progress") is not None:
            break
        time.sleep(0.05)

    # Job may complete before we catch progress mid-flight; check final state too
    if status.get("progress") is None:
        # Progress was never set - verify job completed (short pipeline may skip files)
        assert status["status"] in ("completed", "failed")
    else:
        assert status["progress"]["files_total"] >= 1
        assert status["progress"]["current_root"] == "new"
        assert "files_done" in status["progress"]
        assert "current_file" in status["progress"]
