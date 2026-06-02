"""Characterization tests for PipelineOrchestrator.run() exit paths.

These pin the CURRENT behavior of run() before the straighten refactor.
They mock every _run_*_step so each exit path can be driven deterministically.

Interrupt is triggered by calling the SIGINT handler run() installs on the
main thread DIRECTLY (synchronous, no async signal-delivery timing).
"""
from __future__ import annotations

import signal
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from the_door.core.pipeline.pipeline_orchestrator import PipelineOrchestrator
from the_door.models import AnalyzeConfig, PipelineConfig, PipelineError, PipelineStep


# ── shared helpers (also used by task-02 tests in this file) ─────────────

def _fake_analyze_result():
    """Minimal AnalyzeResult-like object. run() reads only `.snapshot`,
    `.l1_output`; _build_result reads `.scan_result`."""
    result = MagicMock(name="AnalyzeResult")
    result.snapshot = MagicMock(name="snapshot")
    result.scan_result = MagicMock(name="scan_result")
    result.l1_output = MagicMock(name="l1_output")
    return result


def _completed(step_name: str) -> PipelineStep:
    return PipelineStep(step_name=step_name, status="completed", duration_ms=1)


def _failed(step_name: str) -> PipelineStep:
    return PipelineStep(
        step_name=step_name, status="failed", duration_ms=1, error_message="boom"
    )


def _make_config(tmp_path: Path, *, scope_name=None, skip_timeline=True) -> PipelineConfig:
    old_dir = tmp_path / "old"
    new_dir = tmp_path / "new"
    old_dir.mkdir(exist_ok=True)
    new_dir.mkdir(exist_ok=True)
    return PipelineConfig(
        old_path=old_dir,
        new_path=new_dir,
        analyze_config=AnalyzeConfig(skip_cost_confirm=True),
        force_reanalyze=True,
        scope_name=scope_name,
        skip_timeline=skip_timeline,
    )


def _trigger_interrupt() -> None:
    """Deterministically flip run()'s `interrupted` flag by invoking the
    SIGINT handler run() installed on the main thread."""
    handler = signal.getsignal(signal.SIGINT)
    handler(signal.SIGINT, None)


def _run_with_interrupt_before(orch: PipelineOrchestrator, config: PipelineConfig, step_no: int):
    """Drive orch.run() with all steps mocked, firing the interrupt right
    before pipeline step `step_no` (1..6). Returns (PipelineResult, fakes)."""
    fake_old = _fake_analyze_result()
    fake_new = _fake_analyze_result()
    diff_obj = MagicMock(name="diff_result")
    scope_obj = MagicMock(name="scope_result")
    timeline_obj = MagicMock(name="timeline_result")

    calls = {"analyze": 0}

    def analyze_se(path, step_name, config, *, reporter=None):
        calls["analyze"] += 1
        n = calls["analyze"]
        if step_no == 2 and n == 1:
            _trigger_interrupt()
        if step_no == 3 and n == 2:
            _trigger_interrupt()
        if n == 1:
            return _completed("analyze_old"), fake_old
        return _completed("analyze_new"), fake_new

    def diff_se(old_snap, new_snap):
        if step_no == 4:
            _trigger_interrupt()
        return _completed("diff"), diff_obj

    def scope_se(scope_name, new_path, new_l1_output):
        if step_no == 5:
            _trigger_interrupt()
        return _completed("scope_verify"), scope_obj

    def timeline_se(new_path):
        if step_no == 6:
            _trigger_interrupt()
        return _completed("timeline"), timeline_obj

    def count_files_se(path):
        if step_no == 1:
            _trigger_interrupt()
        return 0

    with (
        patch(
            "the_door.core.pipeline.pipeline_orchestrator._count_files",
            side_effect=count_files_se,
        ),
        patch.object(orch, "_run_analyze_step", side_effect=analyze_se),
        patch.object(orch, "_run_diff_step", side_effect=diff_se),
        patch.object(orch, "_run_scope_step", side_effect=scope_se),
        patch.object(orch, "_run_timeline_step", side_effect=timeline_se),
    ):
        result = orch.run(config)
    return result, (fake_old, fake_new, diff_obj, scope_obj, timeline_obj)


# ── interrupt path characterization ──────────────────────────────────────

@pytest.mark.parametrize("step_no", [1, 2, 3, 4, 5, 6])
def test_interrupt_before_step_returns_partial(tmp_path, step_no):
    """Interrupt fired before step N yields a partial PipelineResult with:
    interrupted=True, the (N-1) prior steps completed, the rest skipped, and
    accumulated results present exactly up to the completed steps."""
    orch = PipelineOrchestrator()
    config = _make_config(tmp_path, scope_name="dummy", skip_timeline=False)

    result, (fake_old, fake_new, diff_obj, scope_obj, timeline_obj) = \
        _run_with_interrupt_before(orch, config, step_no)

    assert result.interrupted is True

    # accumulated results present iff their step completed before the interrupt
    assert result.old_snapshot is (fake_old.snapshot if step_no >= 2 else None)
    assert result.new_snapshot is (fake_new.snapshot if step_no >= 3 else None)
    assert result.diff_result is (diff_obj if step_no >= 4 else None)
    assert result.scope_result is (scope_obj if step_no >= 5 else None)
    assert result.timeline_result is (timeline_obj if step_no >= 6 else None)

    # exactly (step_no - 1) completed steps, the remainder skipped, 6 total
    assert len(result.steps) == 6
    completed = [s for s in result.steps if s.status == "completed"]
    skipped = [s for s in result.steps if s.status == "skipped"]
    assert len(completed) == step_no - 1
    assert len(skipped) == 6 - (step_no - 1)


# ── analyze failure terminates ───────────────────────────────────────────

def test_analyze_old_failure_terminates(tmp_path):
    """analyze_old 失敗 → 終止；其餘步驟 skipped；snapshot 全 None；
    analyze_new 不被呼叫（side_effect 只給一個元素，被呼叫第二次會 StopIteration）。"""
    orch = PipelineOrchestrator()
    config = _make_config(tmp_path)

    with patch(
        "the_door.core.pipeline.pipeline_orchestrator._count_files",
        return_value=0,
    ), patch.object(
        orch, "_run_analyze_step",
        side_effect=[(_failed("analyze_old"), None)],
    ):
        result = orch.run(config)

    assert result.interrupted is False
    assert result.old_snapshot is None
    assert result.new_snapshot is None
    assert result.diff_result is None
    assert result.steps[0].step_name == "analyze_old"
    assert result.steps[0].status == "failed"
    assert [s.status for s in result.steps[1:]] == ["skipped"] * 5
    assert len(result.steps) == 6


def test_analyze_new_failure_terminates(tmp_path):
    """analyze_old 成功、analyze_new 失敗 → 終止；old_snapshot 設、new None；
    其餘 skipped。"""
    orch = PipelineOrchestrator()
    config = _make_config(tmp_path)
    fake_old = _fake_analyze_result()

    with patch(
        "the_door.core.pipeline.pipeline_orchestrator._count_files",
        return_value=0,
    ), patch.object(
        orch, "_run_analyze_step",
        side_effect=[
            (_completed("analyze_old"), fake_old),
            (_failed("analyze_new"), None),
        ],
    ):
        result = orch.run(config)

    assert result.interrupted is False
    assert result.old_snapshot is fake_old.snapshot
    assert result.new_snapshot is None
    assert result.diff_result is None
    assert result.steps[0].status == "completed"
    assert result.steps[1].step_name == "analyze_new"
    assert result.steps[1].status == "failed"
    assert [s.status for s in result.steps[2:]] == ["skipped"] * 4
    assert len(result.steps) == 6


# ── normal completion ────────────────────────────────────────────────────

def test_normal_completion_all_steps_present(tmp_path):
    """全步成功：6 步皆 completed、各 snapshot/result 齊全、interrupted=False。"""
    orch = PipelineOrchestrator()
    config = _make_config(tmp_path, scope_name="dummy", skip_timeline=False)
    fake_old = _fake_analyze_result()
    fake_new = _fake_analyze_result()
    diff_obj = MagicMock(name="diff_result")
    scope_obj = MagicMock(name="scope_result")
    timeline_obj = MagicMock(name="timeline_result")

    with patch(
        "the_door.core.pipeline.pipeline_orchestrator._count_files",
        return_value=0,
    ), patch.object(
        orch, "_run_analyze_step",
        side_effect=[
            (_completed("analyze_old"), fake_old),
            (_completed("analyze_new"), fake_new),
        ],
    ), patch.object(
        orch, "_run_diff_step",
        return_value=(_completed("diff"), diff_obj),
    ), patch.object(
        orch, "_run_scope_step",
        return_value=(_completed("scope_verify"), scope_obj),
    ), patch.object(
        orch, "_run_timeline_step",
        return_value=(_completed("timeline"), timeline_obj),
    ):
        result = orch.run(config)

    assert result.interrupted is False
    assert result.old_snapshot is fake_old.snapshot
    assert result.new_snapshot is fake_new.snapshot
    assert result.diff_result is diff_obj
    assert result.scope_result is scope_obj
    assert result.timeline_result is timeline_obj
    assert [s.step_name for s in result.steps] == [
        "analyze_old", "analyze_new", "diff", "scope_verify", "timeline", "report",
    ]
    assert all(s.status == "completed" for s in result.steps)


# ── _report_summary asymmetry (observable behavior to preserve) ──────────

def test_report_summary_called_once_on_normal_completion(tmp_path):
    orch = PipelineOrchestrator()
    config = _make_config(tmp_path, scope_name="dummy", skip_timeline=False)
    fake_old = _fake_analyze_result()
    fake_new = _fake_analyze_result()

    with patch.object(orch, "_report_summary") as spy, patch(
        "the_door.core.pipeline.pipeline_orchestrator._count_files",
        return_value=0,
    ), patch.object(
        orch, "_run_analyze_step",
        side_effect=[
            (_completed("analyze_old"), fake_old),
            (_completed("analyze_new"), fake_new),
        ],
    ), patch.object(
        orch, "_run_diff_step",
        return_value=(_completed("diff"), MagicMock()),
    ), patch.object(
        orch, "_run_scope_step",
        return_value=(_completed("scope_verify"), MagicMock()),
    ), patch.object(
        orch, "_run_timeline_step",
        return_value=(_completed("timeline"), MagicMock()),
    ):
        orch.run(config)

    assert spy.call_count == 1


def test_report_summary_not_called_when_interrupted(tmp_path):
    """早退路徑不發 summary。"""
    orch = PipelineOrchestrator()
    config = _make_config(tmp_path)

    def count_files_se(path):
        _trigger_interrupt()  # interrupt before step 1
        return 0

    with patch.object(orch, "_report_summary") as spy, patch(
        "the_door.core.pipeline.pipeline_orchestrator._count_files",
        side_effect=count_files_se,
    ):
        result = orch.run(config)

    assert result.interrupted is True
    assert spy.call_count == 0


# ── _validate_paths raises (the 10th exit, before the try) ───────────────

def test_validate_paths_raises_pipeline_error_for_missing_old(tmp_path):
    orch = PipelineOrchestrator()
    missing = tmp_path / "does_not_exist"
    new_dir = tmp_path / "new"
    new_dir.mkdir()
    config = PipelineConfig(
        old_path=missing,
        new_path=new_dir,
        analyze_config=AnalyzeConfig(skip_cost_confirm=True),
    )
    with pytest.raises(PipelineError):
        orch.run(config)
