"""Tests for UpdateJob and JobStore."""
from __future__ import annotations

import threading
import time

import pytest


def test_create_job_returns_job():
    from the_door.core.ui.job_store import JobStore
    store = JobStore()
    job = store.try_create_job()
    assert job is not None
    assert job.status == "running"
    assert job.job_id is not None


def test_create_job_when_running_returns_none():
    from the_door.core.ui.job_store import JobStore
    store = JobStore()
    job1 = store.try_create_job()
    assert job1 is not None
    job2 = store.try_create_job()
    assert job2 is None


def test_get_job_running():
    from the_door.core.ui.job_store import JobStore
    store = JobStore()
    job = store.try_create_job()
    assert job is not None
    retrieved = store.get_job(job.job_id)
    assert retrieved is not None
    assert retrieved.status == "running"


def test_get_job_completed():
    from the_door.core.ui.job_store import JobStore
    store = JobStore()
    job = store.try_create_job()
    assert job is not None
    store.complete_job(job.job_id)
    retrieved = store.get_job(job.job_id)
    assert retrieved is not None
    assert retrieved.status == "completed"


def test_get_job_unknown_returns_none():
    from the_door.core.ui.job_store import JobStore
    store = JobStore()
    assert store.get_job("nonexistent-id") is None


def test_complete_job():
    from the_door.core.ui.job_store import JobStore
    store = JobStore()
    job = store.try_create_job()
    assert job is not None
    assert store.has_running_job is True
    store.complete_job(job.job_id)
    assert store.has_running_job is False


def test_fail_job():
    from the_door.core.ui.job_store import JobStore
    store = JobStore()
    job = store.try_create_job()
    assert job is not None
    store.fail_job(job.job_id, "err")
    retrieved = store.get_job(job.job_id)
    assert retrieved is not None
    assert retrieved.status == "failed"
    assert retrieved.error_message == "err"
    assert store.has_running_job is False


def test_update_step_parses_completed_message():
    from the_door.core.ui.job_store import JobStore
    store = JobStore()
    job = store.try_create_job()
    assert job is not None
    job.update_step("[步驟 1/6] ✓ analyze_old（耗時 2.3s）")
    assert len(job.steps) == 1
    assert job.steps[0]["status"] == "completed"
    assert job.current_step is None


def test_update_step_parses_failed_message():
    from the_door.core.ui.job_store import JobStore
    store = JobStore()
    job = store.try_create_job()
    assert job is not None
    job.update_step("[步驟 2/6] ✗ analyze_new — some error")
    assert len(job.steps) == 1
    assert job.steps[0]["status"] == "failed"
    assert job.current_step is None


def test_update_step_parses_skipped_message():
    from the_door.core.ui.job_store import JobStore
    store = JobStore()
    job = store.try_create_job()
    assert job is not None
    job.update_step("[步驟 4/6] ⊘ scope_verify（已跳過：未指定 scope）")
    assert len(job.steps) == 1
    assert job.steps[0]["status"] == "skipped"
    assert job.current_step is None


def test_update_step_sets_current_step():
    from the_door.core.ui.job_store import JobStore
    store = JobStore()
    job = store.try_create_job()
    assert job is not None
    job.update_step("[步驟 3/6] 正在執行：diff...")
    assert job.current_step == "diff"
    assert len(job.steps) == 0


def test_update_step_thread_safety():
    from the_door.core.ui.job_store import JobStore
    store = JobStore()
    job = store.try_create_job()
    assert job is not None

    errors = []

    def worker(n):
        try:
            for i in range(n):
                job.update_step(f"[步驟 {i+1}/6] ✓ step_{i}（耗時 0.1s）")
        except Exception as e:
            errors.append(e)

    t1 = threading.Thread(target=worker, args=(5,))
    t2 = threading.Thread(target=worker, args=(5,))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert not errors
    assert len(job.steps) == 10


def test_job_progress_default_none():
    from the_door.core.ui.job_store import UpdateJob
    job = UpdateJob(job_id="t")
    assert job.progress is None


def test_update_progress_sets_field():
    from the_door.core.ui.job_store import UpdateJob
    job = UpdateJob(job_id="t")
    job.update_progress({
        "files_done": 5, "files_total": 10,
        "current_file": "a.py", "current_root": "new",
    })
    assert job.progress == {
        "files_done": 5, "files_total": 10,
        "current_file": "a.py", "current_root": "new",
    }


def test_update_progress_overwrites():
    from the_door.core.ui.job_store import UpdateJob
    job = UpdateJob(job_id="t")
    job.update_progress({"files_done": 1, "files_total": 10, "current_file": "a.py", "current_root": "new"})
    job.update_progress({"files_done": 2, "files_total": 10, "current_file": "b.py", "current_root": "new"})
    assert job.progress["files_done"] == 2
    assert job.progress["current_file"] == "b.py"


def test_update_progress_thread_safe():
    """Calling update_progress while holding job._lock must not deadlock."""
    import threading
    from the_door.core.ui.job_store import UpdateJob
    job = UpdateJob(job_id="t")
    barrier = threading.Barrier(5)
    def worker(i):
        barrier.wait()
        for _ in range(20):
            job.update_progress({
                "files_done": i, "files_total": 100,
                "current_file": f"f{i}.py", "current_root": "new",
            })
    threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
    for t in threads: t.start()
    for t in threads: t.join(timeout=5)
    assert all(not t.is_alive() for t in threads)
    assert job.progress is not None
