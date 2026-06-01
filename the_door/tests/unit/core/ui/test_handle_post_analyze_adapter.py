"""Test handle_post_analyze adapter wraps run_analyze_pipeline progress.

Adapter must:
1. Emit 3 skipped steps (1/3/4) on first transferred message.
2. Map "Extracting structure from ..." → "[步驟 2/6] 正在執行：analyze_new..."
3. Swallow "Provider:", "Structure JSON persisted to ...", "Running batch analysis..."
4. On "Snapshot saved: <sha>" emit 3 messages: step 2 ✓, step 5 ✓, step 6 ✓.
"""
from __future__ import annotations

import pytest

from the_door.core.ui.job_store import UpdateJob


def _adapter_for(job):
    """Reach into analysis handlers to build adapter; expose helper."""
    from the_door.core.ui.api.handlers.analysis import _make_analyze_progress_adapter
    return _make_analyze_progress_adapter(job)


def test_adapter_emits_skipped_steps_on_first_call():
    job = UpdateJob(job_id="t")
    adapter = _adapter_for(job)
    adapter("Provider: anthropic")
    names_status = [(s["step_name"], s["status"]) for s in job.steps]
    assert ("analyze_old", "skipped") in names_status
    assert ("diff", "skipped") in names_status
    assert ("scope_verify", "skipped") in names_status


def test_adapter_skipped_steps_only_emitted_once():
    job = UpdateJob(job_id="t")
    adapter = _adapter_for(job)
    adapter("Provider: anthropic")
    n1 = len(job.steps)
    adapter("Provider: anthropic")
    assert len(job.steps) == n1


def test_adapter_maps_extracting_to_running_step2():
    job = UpdateJob(job_id="t")
    adapter = _adapter_for(job)
    adapter("Provider: x")
    adapter("Extracting structure from /foo...")
    assert job.current_step == "analyze_new"


def test_adapter_swallows_intermediate_messages():
    job = UpdateJob(job_id="t")
    adapter = _adapter_for(job)
    adapter("Provider: x")
    adapter("Extracting structure from /foo...")
    before_steps = list(job.steps)
    adapter("Structure JSON persisted to /tmp/x.json")
    adapter("Running batch analysis...")
    assert job.steps == before_steps  # nothing added
    assert job.current_step == "analyze_new"  # still running


def test_adapter_snapshot_saved_emits_three_completed():
    job = UpdateJob(job_id="t")
    adapter = _adapter_for(job)
    adapter("Provider: x")
    adapter("Extracting structure from /foo...")
    adapter("Snapshot saved: abc12345")
    completed = [s["step_name"] for s in job.steps if s.get("status") == "completed"]
    assert "analyze_new" in completed
    assert "timeline" in completed
    assert "report" in completed
