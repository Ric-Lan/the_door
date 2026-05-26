"""Tests for handle_post_set_project and JobStore.get_running_job_id."""
from __future__ import annotations

import pytest

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
