"""AnalysisHandlers — POST /api/analyze, POST /api/update, GET /api/update/status/<job_id>."""
from __future__ import annotations

import json
import threading
from pathlib import Path

from the_door.core.pipeline.pipeline_orchestrator import PipelineOrchestrator
from the_door.core.pipeline.report_renderer import ReportRenderer
from the_door.core.ui.api.context import APIContext
from the_door.core.ui.job_store import UpdateJob
from the_door.models import PipelineConfig


def _make_analyze_progress_adapter(job):
    """Per-request closure that wraps run_analyze_pipeline messages into
    PipelineOrchestrator-compatible [步驟 N/6] format. See spec §5.1."""
    sent_skipped = False
    def adapter(msg: str) -> None:
        nonlocal sent_skipped
        if not sent_skipped:
            job.update_step("[步驟 1/6] ⊘ analyze_old （已跳過：首次分析無舊版）")
            job.update_step("[步驟 3/6] ⊘ diff （已跳過：首次分析無舊版）")
            job.update_step("[步驟 4/6] ⊘ scope_verify （已跳過：首次分析無 scope）")
            sent_skipped = True
        if msg.startswith("Extracting structure from"):
            job.update_step("[步驟 2/6] 正在執行：analyze_new...")
            return
        if msg.startswith("Snapshot saved:"):
            job.update_step("[步驟 2/6] ✓ analyze_new （耗時 0.0s）")
            job.update_step("[步驟 5/6] ✓ timeline （耗時 0.0s）")
            job.update_step("[步驟 6/6] ✓ report （耗時 0.0s）")
            return
    return adapter


class AnalysisHandlers:
    def __init__(self, ctx: APIContext) -> None:
        self._ctx = ctx

    # ------------------------------------------------------------------
    # POST /api/analyze
    # ------------------------------------------------------------------

    def analyze(self, ctx=None, *, body=None, **_) -> tuple[int, dict]:
        if body is None:
            body = {}
        extra_ignore = body.get("extra_ignore") or None
        snapshot_label = body.get("label") or None

        job = self._ctx.job_store.try_create_job()
        if job is None:
            return 409, self._make_error(
                code="job_already_running",
                message="A pipeline job is already running. Please wait for it to complete.",
                source="handle_post_analyze",
            )

        thread = threading.Thread(
            target=self._run_analyze_job,
            args=(job, extra_ignore, snapshot_label),
            daemon=True,
        )
        thread.start()

        return 202, {"job_id": job.job_id}

    def _run_analyze_job(
        self,
        job,
        extra_ignore: list[str] | None,
        snapshot_label: str | None,
    ) -> None:
        from the_door.core.pipeline.analyze_pipeline import run_analyze_pipeline
        from the_door.core.pipeline.progress_reporter import ProgressReporter
        from the_door.models import AnalyzeConfig

        config = AnalyzeConfig(
            skip_cost_confirm=True,
            extra_ignore=extra_ignore,
            snapshot_label=snapshot_label,
        )
        adapter = _make_analyze_progress_adapter(job)
        reporter = ProgressReporter(sink=job.update_progress)
        try:
            run_analyze_pipeline(
                self._ctx.project_root,
                config,
                progress_callback=adapter,
                reporter=reporter,
            )
            self._ctx.job_store.complete_job(job.job_id)
        except Exception as exc:
            self._ctx.job_store.fail_job(job.job_id, str(exc))

    # ------------------------------------------------------------------
    # POST /api/update
    # ------------------------------------------------------------------

    def update(self, ctx=None, *, body=None, **_) -> tuple[int, dict]:
        """Validate request, create job, start background pipeline thread."""
        if body is None:
            body = {}
        # 1. Validate required fields
        old_path_str = body.get("old_path")
        new_path_str = body.get("new_path")
        if old_path_str is None or new_path_str is None:
            return 400, self._make_error(
                code="missing_required_field",
                message="Both 'old_path' and 'new_path' are required.",
                source="handle_post_update",
            )

        old_path = Path(old_path_str)
        new_path = Path(new_path_str)

        # 2. Validate paths exist and are directories
        if not old_path.exists() or not old_path.is_dir():
            return 400, self._make_error(
                code="invalid_path",
                message=f"old_path does not exist or is not a directory: {old_path_str}",
                source="handle_post_update",
            )
        if not new_path.exists() or not new_path.is_dir():
            return 400, self._make_error(
                code="invalid_path",
                message=f"new_path does not exist or is not a directory: {new_path_str}",
                source="handle_post_update",
            )

        # 3. Validate paths are not the same
        if old_path.resolve() == new_path.resolve():
            return 400, self._make_error(
                code="same_path",
                message="old_path and new_path must be different directories.",
                source="handle_post_update",
            )

        # 4. Security: validate paths are under project_root
        project_root_resolved = self._ctx.project_root.resolve()
        try:
            old_path.resolve().relative_to(project_root_resolved)
        except ValueError:
            return 400, self._make_error(
                code="invalid_path",
                message=f"old_path is outside project root: {old_path_str}",
                source="handle_post_update",
            )
        try:
            new_path.resolve().relative_to(project_root_resolved)
        except ValueError:
            return 400, self._make_error(
                code="invalid_path",
                message=f"new_path is outside project root: {new_path_str}",
                source="handle_post_update",
            )

        # 5. Check for running job
        job = self._ctx.job_store.try_create_job()
        if job is None:
            return 409, self._make_error(
                code="job_already_running",
                message="A pipeline job is already running. Please wait for it to complete.",
                source="handle_post_update",
            )

        output_language = body.get("output_language") or "zh-Hant"

        # 6. Start background thread
        thread = threading.Thread(
            target=self._run_pipeline_job,
            args=(job, old_path, new_path, output_language),
            daemon=True,
        )
        thread.start()

        return 202, {"job_id": job.job_id}

    def _run_pipeline_job(
        self, job: UpdateJob, old_path: Path, new_path: Path, output_language: str = "zh-Hant"
    ) -> None:
        """Background thread: run pipeline, persist report, update job status."""
        try:
            from the_door.core.pipeline.progress_reporter import ProgressReporter
            config = PipelineConfig(old_path=old_path, new_path=new_path, output_language=output_language)
            reporter = ProgressReporter(sink=job.update_progress)
            result = PipelineOrchestrator().run(config, progress_callback=job.update_step, reporter=reporter)
            report = ReportRenderer().render_json(result)
            self._persist_report(report)
            self._ctx.job_store.complete_job(job.job_id)
        except Exception as exc:
            self._ctx.job_store.fail_job(job.job_id, str(exc))

    def _persist_report(self, report: dict) -> None:
        """Persist report to .the-door/update-report-<generated_at>.json."""
        generated_at = report.get("generated_at", "unknown")
        safe_ts = generated_at.replace(":", "-")
        filename = f"update-report-{safe_ts}.json"
        dot_dir = self._ctx.project_root / ".the-door"
        dot_dir.mkdir(parents=True, exist_ok=True)
        (dot_dir / filename).write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # ------------------------------------------------------------------
    # GET /api/update/status/<job_id>
    # ------------------------------------------------------------------

    def update_status(self, ctx=None, *, job_id=None, **_) -> tuple[int, dict]:
        """Return the current status of a pipeline job."""
        job = self._ctx.job_store.get_job(job_id)
        if job is None:
            return 404, self._make_error(
                code="job_not_found",
                message=f"No job found with id: {job_id}",
                source="handle_get_update_status",
            )

        response: dict = {
            "job_id": job.job_id,
            "status": job.status,
            "current_step": job.current_step,
            "steps": list(job.steps),
        }
        if job.status == "failed":
            response["error_message"] = job.error_message
        response["progress"] = job.progress

        return 200, response

    @staticmethod
    def _make_error(code: str, message: str, source: str) -> dict:
        return {"error": {"code": code, "message": message, "source": source}}
