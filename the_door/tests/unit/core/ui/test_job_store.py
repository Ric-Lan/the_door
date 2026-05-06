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
