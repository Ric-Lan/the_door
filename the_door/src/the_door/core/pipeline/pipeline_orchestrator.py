"""Pipeline Orchestrator — version update pipeline engine.

Pure orchestration — no new analysis logic. All analysis capabilities are
delegated to existing Phase 1–4 modules.

Step execution order:
1. analyze(old_path) — analyse old version
2. analyze(new_path) — analyse new version
3. diff — version comparison
4. scope_verify — scope verification (optional)
5. timeline — timeline update (optional)
6. report — generate report (placeholder, rendered externally)

Error handling:
- analyze failure → pipeline terminates
- diff/scope/timeline failure → mark failed, continue

All file I/O uses encoding="utf-8" for Windows compatibility.
"""
from __future__ import annotations

import json
import logging
import os
import signal
import threading
import time
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from the_door.core.diff.diff_engine import DiffEngine
from the_door.core.diff.snapshot_store import SnapshotStore
from the_door.core.pipeline.analyze_pipeline import (
    compute_file_fingerprint,
    run_analyze_pipeline,
    validate_snapshot_fingerprint,
)
from the_door.core.pipeline.progress_reporter import NoOpProgressReporter, ProgressReporter
from the_door.core.scope.scope_verifier import (
    ScopeVerifier,
    parse_scope_definition,
    resolve_scope_path,
)
from the_door.core.timeline.timeline_engine import TimelineEngine
from the_door.models import (
    AnalyzeResult,
    DiffResult,
    PipelineConfig,
    PipelineError,
    PipelineResult,
    PipelineStep,
    ScopeResult,
    TimelineResult,
    VersionSnapshot,
)

logger = logging.getLogger(__name__)

# Step definitions: (step_name, timeout_attr)
_STEP_DEFS = [
    ("analyze_old", "analyze_old"),
    ("analyze_new", "analyze_new"),
    ("diff", "diff"),
    ("scope_verify", "scope_verify"),
    ("timeline", "timeline"),
    ("report", "report"),
]

_TOTAL_STEPS = len(_STEP_DEFS)


def _noop_progress(msg: str) -> None:
    """Default no-op progress callback."""


def _now_iso() -> str:
    """Return current UTC time as ISO8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _elapsed_ms(start: float) -> int:
    """Return elapsed milliseconds since *start* (time.monotonic)."""
    return int((time.monotonic() - start) * 1000)


def _count_files(path: Path) -> int:
    """Count files in a directory tree (quick estimate for time prediction)."""
    try:
        return sum(1 for _ in path.rglob("*") if _.is_file())
    except OSError:
        return 0


class PipelineOrchestrator:
    """版本更新管線編排引擎。

    Pure orchestration — 不包含任何新的分析邏輯。
    所有分析能力完全委派給既有模組。
    """

    def run(
        self,
        config: PipelineConfig,
        *,
        progress_callback: Callable[[str], None] | None = None,
        reporter: ProgressReporter | None = None,
    ) -> PipelineResult:
        """Execute the full version update pipeline.

        Parameters
        ----------
        config : PipelineConfig
            Complete pipeline configuration.
        progress_callback : Callable[[str], None] | None
            Progress reporter. Messages go to stderr in CLI mode.

        Returns
        -------
        PipelineResult
            Complete pipeline result with all step states.

        Raises
        ------
        PipelineError
            Path validation failures (non-existent, not directory, same path).
        """
        progress = progress_callback or _noop_progress
        rep = reporter or NoOpProgressReporter()

        # ── Path validation ──────────────────────────────────────────
        self._validate_paths(config)

        # ── SIGINT handling ──────────────────────────────────────────
        interrupted = False
        original_handler = signal.getsignal(signal.SIGINT)

        def _sigint_handler(signum, frame):  # noqa: ARG001
            nonlocal interrupted
            interrupted = True

        # Only install signal handler on main thread
        on_main_thread = threading.current_thread() is threading.main_thread()
        if on_main_thread:
            signal.signal(signal.SIGINT, _sigint_handler)

        # ── Estimate total time ──────────────────────────────────────
        old_file_count = _count_files(config.old_path)
        new_file_count = _count_files(config.new_path)
        progress(
            f"預估分析時間：約 2–5 分鐘"
            f"（舊版 {old_file_count} 個檔案 + 新版 {new_file_count} 個檔案）"
        )

        # ── Pipeline execution ───────────────────────────────────────
        pipeline_start = time.monotonic()
        steps: list[PipelineStep] = []
        old_analyze_result: AnalyzeResult | None = None
        new_analyze_result: AnalyzeResult | None = None
        diff_result: DiffResult | None = None
        scope_result: ScopeResult | None = None
        timeline_result: TimelineResult | None = None

        try:
            # ── Step 1: analyze_old ──────────────────────────────────
            if interrupted:
                steps.extend(self._skip_remaining(_STEP_DEFS, len(steps)))
                return self._build_result(
                    config, steps, None, None, None, None, None,
                    old_analyze_result, new_analyze_result,
                    pipeline_start, True,
                )

            step_num = 1
            progress(f"[步驟 {step_num}/{_TOTAL_STEPS}] 正在執行：analyze_old...")
            step, old_analyze_result = self._run_analyze_step(
                config.old_path, "analyze_old", config, reporter=rep,
            )
            steps.append(step)
            self._report_step_done(progress, step_num, step)

            if step.status == "failed":
                # analyze failure → terminate
                steps.extend(self._skip_remaining(_STEP_DEFS, len(steps)))
                return self._build_result(
                    config, steps, None, None, None, None, None,
                    old_analyze_result, new_analyze_result,
                    pipeline_start, interrupted,
                )

            # ── Step 2: analyze_new ──────────────────────────────────
            if interrupted:
                steps.extend(self._skip_remaining(_STEP_DEFS, len(steps)))
                return self._build_result(
                    config, steps,
                    old_analyze_result.snapshot if old_analyze_result else None,
                    None, None, None, None,
                    old_analyze_result, new_analyze_result,
                    pipeline_start, True,
                )

            step_num = 2
            progress(f"[步驟 {step_num}/{_TOTAL_STEPS}] 正在執行：analyze_new...")
            step, new_analyze_result = self._run_analyze_step(
                config.new_path, "analyze_new", config, reporter=rep,
            )
            steps.append(step)
            self._report_step_done(progress, step_num, step)

            if step.status == "failed":
                steps.extend(self._skip_remaining(_STEP_DEFS, len(steps)))
                return self._build_result(
                    config, steps,
                    old_analyze_result.snapshot if old_analyze_result else None,
                    None, None, None, None,
                    old_analyze_result, new_analyze_result,
                    pipeline_start, interrupted,
                )

            old_snapshot = old_analyze_result.snapshot
            new_snapshot = new_analyze_result.snapshot

            # ── Step 3: diff ─────────────────────────────────────────
            if interrupted:
                steps.extend(self._skip_remaining(_STEP_DEFS, len(steps)))
                return self._build_result(
                    config, steps, old_snapshot, new_snapshot,
                    None, None, None,
                    old_analyze_result, new_analyze_result,
                    pipeline_start, True,
                )

            step_num = 3
            progress(f"[步驟 {step_num}/{_TOTAL_STEPS}] 正在執行：diff...")
            step, diff_result = self._run_diff_step(old_snapshot, new_snapshot)
            steps.append(step)
            self._report_step_done(progress, step_num, step)

            # ── Step 4: scope_verify ─────────────────────────────────
            if interrupted:
                steps.extend(self._skip_remaining(_STEP_DEFS, len(steps)))
                return self._build_result(
                    config, steps, old_snapshot, new_snapshot,
                    diff_result, None, None,
                    old_analyze_result, new_analyze_result,
                    pipeline_start, True,
                )

            step_num = 4
            if config.scope_name is None:
                steps.append(PipelineStep(step_name="scope_verify", status="skipped"))
                progress(f"[步驟 {step_num}/{_TOTAL_STEPS}] ⊘ scope_verify（已跳過：未指定 scope）")
            else:
                progress(f"[步驟 {step_num}/{_TOTAL_STEPS}] 正在執行：scope_verify...")
                step, scope_result = self._run_scope_step(
                    config.scope_name, config.new_path, new_analyze_result.l1_output,
                )
                steps.append(step)
                self._report_step_done(progress, step_num, step)

            # ── Step 5: timeline ─────────────────────────────────────
            if interrupted:
                steps.extend(self._skip_remaining(_STEP_DEFS, len(steps)))
                return self._build_result(
                    config, steps, old_snapshot, new_snapshot,
                    diff_result, scope_result, None,
                    old_analyze_result, new_analyze_result,
                    pipeline_start, True,
                )

            step_num = 5
            if config.skip_timeline:
                steps.append(PipelineStep(step_name="timeline", status="skipped"))
                progress(f"[步驟 {step_num}/{_TOTAL_STEPS}] ⊘ timeline（已跳過）")
            else:
                progress(f"[步驟 {step_num}/{_TOTAL_STEPS}] 正在執行：timeline...")
                step, timeline_result = self._run_timeline_step(config.new_path)
                steps.append(step)
                self._report_step_done(progress, step_num, step)

            # ── Step 6: report (placeholder — actual rendering is external) ──
            if interrupted:
                steps.extend(self._skip_remaining(_STEP_DEFS, len(steps)))
                return self._build_result(
                    config, steps, old_snapshot, new_snapshot,
                    diff_result, scope_result, timeline_result,
                    old_analyze_result, new_analyze_result,
                    pipeline_start, True,
                )

            step_num = 6
            report_start = time.monotonic()
            report_started_at = _now_iso()
            # Report step is a marker — actual rendering happens in CLI/MCP layer
            steps.append(PipelineStep(
                step_name="report",
                status="completed",
                started_at=report_started_at,
                completed_at=_now_iso(),
                duration_ms=_elapsed_ms(report_start),
            ))
            progress(f"[步驟 {step_num}/{_TOTAL_STEPS}] ✓ report（耗時 0.0s）")

            result = self._build_result(
                config, steps, old_snapshot, new_snapshot,
                diff_result, scope_result, timeline_result,
                old_analyze_result, new_analyze_result,
                pipeline_start, interrupted,
            )

            # ── Summary ──────────────────────────────────────────────
            self._report_summary(progress, result)

            return result

        finally:
            # Restore original signal handler
            if on_main_thread:
                signal.signal(signal.SIGINT, original_handler)

    # ── Step implementations ─────────────────────────────────────────

    def _run_analyze_step(
        self,
        path: Path,
        step_name: str,
        config: PipelineConfig,
        *,
        reporter: ProgressReporter | None = None,
    ) -> tuple[PipelineStep, AnalyzeResult | None]:
        """Execute an analyze step with fingerprint caching.

        1. Compute current file fingerprint
        2. Check existing fingerprint (unless force_reanalyze)
        3. Fingerprint match → use existing snapshot
        4. Otherwise → run run_analyze_pipeline()
        5. Save new fingerprint file (named by snapshot.version_id)
        """
        started_at = _now_iso()
        start = time.monotonic()

        try:
            current_fp = compute_file_fingerprint(path)

            # Check for existing snapshot with matching fingerprint
            if not config.force_reanalyze:
                cached = self._try_cached_analyze(path, current_fp)
                if cached is not None:
                    duration = _elapsed_ms(start)
                    step = PipelineStep(
                        step_name=step_name,
                        status="completed",
                        started_at=started_at,
                        completed_at=_now_iso(),
                        duration_ms=duration,
                    )
                    return step, cached

            # Run full analysis
            rep = reporter or NoOpProgressReporter()
            result = run_analyze_pipeline(
                path,
                config.analyze_config,
                progress_callback=None,  # orchestrator handles progress
                reporter=rep,
            )

            # Save fingerprint
            self._save_fingerprint(path, result.snapshot.version_id, result.file_fingerprint)

            duration = _elapsed_ms(start)
            step = PipelineStep(
                step_name=step_name,
                status="completed",
                started_at=started_at,
                completed_at=_now_iso(),
                duration_ms=duration,
            )
            return step, result

        except Exception as exc:
            duration = _elapsed_ms(start)
            step = PipelineStep(
                step_name=step_name,
                status="failed",
                started_at=started_at,
                completed_at=_now_iso(),
                duration_ms=duration,
                error_message=str(exc),
            )
            return step, None

    def _run_diff_step(
        self,
        old_snapshot: VersionSnapshot,
        new_snapshot: VersionSnapshot,
    ) -> tuple[PipelineStep, DiffResult | None]:
        """Execute the diff step."""
        started_at = _now_iso()
        start = time.monotonic()

        try:
            engine = DiffEngine()
            result = engine.compute_l1_diff(old_snapshot, new_snapshot)

            duration = _elapsed_ms(start)
            step = PipelineStep(
                step_name="diff",
                status="completed",
                started_at=started_at,
                completed_at=_now_iso(),
                duration_ms=duration,
            )
            return step, result

        except Exception as exc:
            duration = _elapsed_ms(start)
            step = PipelineStep(
                step_name="diff",
                status="failed",
                started_at=started_at,
                completed_at=_now_iso(),
                duration_ms=duration,
                error_message=str(exc),
            )
            return step, None

    def _run_scope_step(
        self,
        scope_name: str,
        new_path: Path,
        new_l1_output: "L1Output",  # noqa: F821
    ) -> tuple[PipelineStep, ScopeResult | None]:
        """Execute the scope verify step.

        Uses ScopeVerifier.verify(scope_def, l1_output) — receives L1Output
        object (not dict), consistent with existing API.
        """
        started_at = _now_iso()
        start = time.monotonic()

        try:
            scope_path = resolve_scope_path(scope_name, new_path)
            scope_def = parse_scope_definition(scope_path)

            verifier = ScopeVerifier()
            result = verifier.verify(scope_def, new_l1_output)

            duration = _elapsed_ms(start)
            step = PipelineStep(
                step_name="scope_verify",
                status="completed",
                started_at=started_at,
                completed_at=_now_iso(),
                duration_ms=duration,
            )
            return step, result

        except Exception as exc:
            duration = _elapsed_ms(start)
            step = PipelineStep(
                step_name="scope_verify",
                status="failed",
                started_at=started_at,
                completed_at=_now_iso(),
                duration_ms=duration,
                error_message=str(exc),
            )
            return step, None

    def _run_timeline_step(
        self,
        new_path: Path,
    ) -> tuple[PipelineStep, TimelineResult | None]:
        """Execute the timeline step."""
        started_at = _now_iso()
        start = time.monotonic()

        try:
            store = SnapshotStore(new_path)
            snapshots = store.list_snapshots()

            engine = TimelineEngine()
            result = engine.analyze(snapshots)

            duration = _elapsed_ms(start)
            step = PipelineStep(
                step_name="timeline",
                status="completed",
                started_at=started_at,
                completed_at=_now_iso(),
                duration_ms=duration,
            )
            return step, result

        except Exception as exc:
            duration = _elapsed_ms(start)
            step = PipelineStep(
                step_name="timeline",
                status="failed",
                started_at=started_at,
                completed_at=_now_iso(),
                duration_ms=duration,
                error_message=str(exc),
            )
            return step, None

    # ── Fingerprint caching helpers ──────────────────────────────────

    def _try_cached_analyze(
        self,
        path: Path,
        current_fp: dict[str, tuple[int, float]],
    ) -> AnalyzeResult | None:
        """Try to find a cached AnalyzeResult via fingerprint matching.

        Loads the latest snapshot and its corresponding fingerprint file.
        If fingerprints match, reconstructs an AnalyzeResult from the snapshot.
        Returns None if no valid cache found.
        """
        store = SnapshotStore(path)
        latest = store.get_latest()
        if latest is None:
            return None

        # Load stored fingerprint
        fp_dir = path / ".the-door" / "fingerprints"
        fp_file = fp_dir / f"{latest.version_id}.json"
        if not fp_file.exists():
            return None

        try:
            stored_fp_raw = json.loads(fp_file.read_text(encoding="utf-8"))
            # Convert JSON lists back to tuples
            stored_fp: dict[str, tuple[int, float]] = {
                k: (v[0], v[1]) for k, v in stored_fp_raw.items()
            }
        except (json.JSONDecodeError, KeyError, IndexError, TypeError):
            return None

        if not validate_snapshot_fingerprint(stored_fp, current_fp):
            return None

        # Fingerprint matches — reconstruct AnalyzeResult from snapshot
        # We need to reconstruct L1Output from the snapshot data
        from the_door.models import (
            Feature,
            FeatureRelation,
            L1Output,
            ScanResult,
        )

        features = []
        for fid, fs in latest.l1_snapshot.items():
            # FeatureSummary doesn't carry `trigger` or `confidence_reason`
            # (the LLM-side fields), so cache rebuild fills them with empty
            # strings. `trigger_description` and `source_nodes` ARE persisted
            # (commits ba39192 and 8933100) — propagate them so the very
            # next snapshot write doesn't overwrite the on-disk values with
            # empties.
            features.append(Feature(
                feature_id=fid,
                label=fs.label,
                description=fs.description,
                trigger="",
                trigger_description=fs.trigger_description or "",
                confidence=fs.confidence,
                confidence_reason="",
                source_nodes=list(fs.source_nodes),
            ))

        feature_relations = []
        for rs in latest.feature_relations_snapshot:
            feature_relations.append(FeatureRelation(
                from_feature=rs.from_feature,
                to_feature=rs.to_feature,
                relation=rs.relation,
            ))

        l1_output = L1Output(
            features=features,
            feature_relations=feature_relations,
        )

        # Reconstruct scan_result from snapshot
        scan_result = ScanResult(
            entries=latest.vulnerabilities_snapshot,
            db_freshness=latest.vulnerability_db_freshness,
        )

        from the_door.models import AnalyzeResult as AR

        return AR(
            snapshot=latest,
            l1_output=l1_output,
            l1_output_data={},  # Not available from cache
            scan_result=scan_result,
            file_fingerprint=current_fp,
            total_batches=0,
            total_tokens=0,
        )

    def _save_fingerprint(
        self,
        path: Path,
        version_id: str,
        fingerprint: dict[str, tuple[int, float]],
    ) -> None:
        """Save fingerprint to `.the-door/fingerprints/<version_id>.json`."""
        fp_dir = path / ".the-door" / "fingerprints"
        fp_dir.mkdir(parents=True, exist_ok=True)
        fp_file = fp_dir / f"{version_id}.json"

        # Convert tuples to lists for JSON serialization
        serializable = {k: list(v) for k, v in fingerprint.items()}
        fp_file.write_text(
            json.dumps(serializable, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    # ── Path validation ──────────────────────────────────────────────

    def _validate_paths(self, config: PipelineConfig) -> None:
        """Validate old_path and new_path."""
        old = Path(config.old_path)
        new = Path(config.new_path)

        if not old.exists():
            raise PipelineError("validate_paths", f"舊版路徑不存在：{old}")
        if not old.is_dir():
            raise PipelineError("validate_paths", f"舊版路徑不是目錄：{old}")
        if not new.exists():
            raise PipelineError("validate_paths", f"新版路徑不存在：{new}")
        if not new.is_dir():
            raise PipelineError("validate_paths", f"新版路徑不是目錄：{new}")

        # Resolve to handle symlinks and relative paths
        if old.resolve() == new.resolve():
            raise PipelineError("validate_paths", "舊版路徑和新版路徑不可相同")

    # ── Progress helpers ─────────────────────────────────────────────

    def _report_step_done(
        self,
        progress: Callable[[str], None],
        step_num: int,
        step: PipelineStep,
    ) -> None:
        """Report step completion or failure."""
        duration_s = (step.duration_ms or 0) / 1000.0
        if step.status == "completed":
            progress(
                f"[步驟 {step_num}/{_TOTAL_STEPS}] ✓ {step.step_name}"
                f"（耗時 {duration_s:.1f}s）"
            )
        elif step.status == "failed":
            progress(
                f"[步驟 {step_num}/{_TOTAL_STEPS}] ✗ {step.step_name}"
                f" — {step.error_message}"
            )

    def _report_summary(
        self,
        progress: Callable[[str], None],
        result: PipelineResult,
    ) -> None:
        """Report pipeline completion summary."""
        total_s = result.total_duration_ms / 1000.0
        completed = sum(1 for s in result.steps if s.status == "completed")
        failed = sum(1 for s in result.steps if s.status == "failed")
        skipped = sum(1 for s in result.steps if s.status == "skipped")

        progress(
            f"\n管線完成：總耗時 {total_s:.1f}s"
            f"（成功 {completed}、失敗 {failed}、跳過 {skipped}）"
        )

    # ── Result builder ───────────────────────────────────────────────

    def _build_result(
        self,
        config: PipelineConfig,
        steps: list[PipelineStep],
        old_snapshot: VersionSnapshot | None,
        new_snapshot: VersionSnapshot | None,
        diff_result: DiffResult | None,
        scope_result: ScopeResult | None,
        timeline_result: TimelineResult | None,
        old_analyze_result: AnalyzeResult | None,
        new_analyze_result: AnalyzeResult | None,
        pipeline_start: float,
        interrupted: bool,
    ) -> PipelineResult:
        """Build the final PipelineResult."""
        return PipelineResult(
            config=config,
            steps=steps,
            old_snapshot=old_snapshot,
            new_snapshot=new_snapshot,
            diff_result=diff_result,
            scope_result=scope_result,
            timeline_result=timeline_result,
            scan_result_old=(
                old_analyze_result.scan_result if old_analyze_result else None
            ),
            scan_result_new=(
                new_analyze_result.scan_result if new_analyze_result else None
            ),
            total_duration_ms=_elapsed_ms(pipeline_start),
            interrupted=interrupted,
        )

    def _skip_remaining(
        self,
        step_defs: list[tuple[str, str]],
        completed_count: int,
    ) -> list[PipelineStep]:
        """Generate skipped steps for all remaining steps."""
        remaining = []
        for step_name, _ in step_defs[completed_count:]:
            remaining.append(PipelineStep(step_name=step_name, status="skipped"))
        return remaining
