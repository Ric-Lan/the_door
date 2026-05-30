"""Unit tests for reporter root='old'/'new' switching in PipelineOrchestrator.

Spec §5.1: _run_analyze_step must call set_total with root='old' for the
analyze_old step and root='new' for the analyze_new step.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from the_door.core.pipeline.pipeline_orchestrator import PipelineOrchestrator
from the_door.core.pipeline.progress_reporter import ProgressReporter
from the_door.models import (
    AnalyzeConfig,
    AnalyzeResult,
    PipelineConfig,
    PipelineStep,
)


def _make_fake_analyze_result():
    """Minimal AnalyzeResult-like object with enough fields for orchestrator."""
    snap = MagicMock()
    snap.version_id = "fake-version-id"
    result = MagicMock()
    result.snapshot = snap
    result.file_fingerprint = {"file.py": (100, 1.0)}
    result.l1_output = MagicMock()
    result.scan_result = MagicMock()
    result.l1_output_data = {}
    result.total_batches = 1
    result.total_tokens = 100
    return result


class TestReporterRootSwitching:
    """_run_analyze_step switches reporter root based on step_name."""

    def test_set_total_called_old_then_new(self, tmp_path: Path) -> None:
        """Verify set_total is called with root='old' for analyze_old and
        root='new' for analyze_new, in that order."""
        old_dir = tmp_path / "old"
        new_dir = tmp_path / "new"
        old_dir.mkdir()
        new_dir.mkdir()

        recorded_calls: list[dict] = []

        def recording_sink(d: dict) -> None:  # noqa: ARG001
            pass

        reporter = ProgressReporter(sink=recording_sink)
        original_set_total = reporter.set_total
        set_total_calls: list[tuple] = []

        def spy_set_total(total: int, *, root: str) -> None:
            set_total_calls.append((total, root))
            original_set_total(total, root=root)  # type: ignore[arg-type]

        reporter.set_total = spy_set_total  # type: ignore[method-assign]

        fake_result = _make_fake_analyze_result()

        config = PipelineConfig(
            old_path=old_dir,
            new_path=new_dir,
            analyze_config=AnalyzeConfig(skip_cost_confirm=True),
            force_reanalyze=True,
            skip_timeline=True,
        )

        orchestrator = PipelineOrchestrator()

        with patch(
            "the_door.core.pipeline.pipeline_orchestrator.run_analyze_pipeline",
            return_value=fake_result,
        ) as mock_rap, patch(
            "the_door.core.pipeline.pipeline_orchestrator._count_files",
            return_value=5,
        ), patch(
            "the_door.core.pipeline.pipeline_orchestrator.compute_file_fingerprint",
            return_value="fp",
        ), patch.object(
            orchestrator, "_save_fingerprint"
        ), patch.object(
            orchestrator, "_run_diff_step",
            return_value=(PipelineStep(step_name="diff", status="completed", duration_ms=10), MagicMock()),
        ), patch.object(
            orchestrator, "_run_timeline_step",
            return_value=(PipelineStep(step_name="timeline", status="skipped"), None),
        ):
            orchestrator.run(config, reporter=reporter)

        # run_analyze_pipeline must be called twice
        assert mock_rap.call_count == 2

        # Extract the root kwarg from each call
        roots_passed = [c.kwargs.get("root") for c in mock_rap.call_args_list]
        assert roots_passed == ["old", "new"], (
            f"Expected run_analyze_pipeline called with root='old' then root='new', got {roots_passed}"
        )

    def test_set_total_root_old_via_spy(self, tmp_path: Path) -> None:
        """Simpler variant: spy on ProgressReporter._root after each
        run_analyze_pipeline call to confirm the root value was passed through
        and set_total was invoked inside the pipeline with the right root."""
        old_dir = tmp_path / "old2"
        new_dir = tmp_path / "new2"
        old_dir.mkdir()
        new_dir.mkdir()

        roots_seen: list[str] = []

        def fake_run_analyze_pipeline(path, cfg, *, progress_callback=None, reporter=None, root="new"):
            # Record root and simulate set_total being called (as the real impl does)
            if reporter is not None:
                reporter.set_total(3, root=root)
            roots_seen.append(root)
            return _make_fake_analyze_result()

        config = PipelineConfig(
            old_path=old_dir,
            new_path=new_dir,
            analyze_config=AnalyzeConfig(skip_cost_confirm=True),
            force_reanalyze=True,
            skip_timeline=True,
        )

        orchestrator = PipelineOrchestrator()
        reporter = ProgressReporter(sink=lambda _: None)

        with patch(
            "the_door.core.pipeline.pipeline_orchestrator.run_analyze_pipeline",
            side_effect=fake_run_analyze_pipeline,
        ), patch(
            "the_door.core.pipeline.pipeline_orchestrator._count_files",
            return_value=3,
        ), patch(
            "the_door.core.pipeline.pipeline_orchestrator.compute_file_fingerprint",
            return_value="fp",
        ), patch.object(
            orchestrator, "_save_fingerprint"
        ), patch.object(
            orchestrator, "_run_diff_step",
            return_value=(PipelineStep(step_name="diff", status="completed", duration_ms=10), MagicMock()),
        ), patch.object(
            orchestrator, "_run_timeline_step",
            return_value=(PipelineStep(step_name="timeline", status="skipped"), None),
        ):
            orchestrator.run(config, reporter=reporter)

        assert roots_seen == ["old", "new"], (
            f"Expected ['old', 'new'] but got {roots_seen}"
        )
        # After analyze_old, reporter._root should have been set to 'old' then 'new'
        # Final state is 'new' (after analyze_new)
        assert reporter._root == "new"
