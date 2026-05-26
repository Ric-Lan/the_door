"""UpdateJob and JobStore — in-memory pipeline job state management.

UpdateJob tracks the execution state of a single pipeline run.
JobStore enforces at-most-one concurrent job constraint.

All state mutations are protected by threading.Lock for thread safety.
"""
from __future__ import annotations

import re
import threading
import uuid
from dataclasses import dataclass, field
from typing import Optional


# Regex to extract step_name from PipelineOrchestrator progress messages.
# Format: "[步驟 N/M] <symbol> <step_name>..." or "[步驟 N/M] 正在執行：<step_name>..."
# We match on Unicode symbols (✓ ✗ ⊘) and the running pattern.
_RE_COMPLETED = re.compile(r"\[步驟 \d+/\d+\] ✓ (\S+)")
_RE_FAILED = re.compile(r"\[步驟 \d+/\d+\] ✗ (\S+)")
_RE_SKIPPED = re.compile(r"\[步驟 \d+/\d+\] ⊘ (\S+)")
_RE_RUNNING = re.compile(r"\[步驟 \d+/\d+\] 正在執行：(\S+?)\.{0,3}$")

# Duration extraction: "（耗時 X.Xs）"
_RE_DURATION = re.compile(r"耗時 ([\d.]+)s")


def _parse_duration_ms(msg: str) -> int | None:
    """Extract duration in milliseconds from a progress message."""
    m = _RE_DURATION.search(msg)
    if m:
        try:
            return int(float(m.group(1)) * 1000)
        except ValueError:
            return None
    return None


@dataclass
class UpdateJob:
    """In-memory state for a single pipeline execution.

    Non-frozen: status transitions happen during execution.
    Thread-safe: all mutations use self._lock.
    """

    job_id: str
    status: str = "running"          # "running" | "completed" | "failed"
    current_step: Optional[str] = None
    steps: list = field(default_factory=list)
    error_message: Optional[str] = None
    _lock: threading.Lock = field(
        default_factory=threading.Lock,
        repr=False,
        compare=False,
    )

    def update_step(self, progress_msg: str) -> None:
        """Parse a PipelineOrchestrator progress message and update state.

        Parsing is based on Unicode symbols (not Chinese keywords) to avoid
        Windows cp950 encoding issues:
        - ✓  → step completed
        - ✗  → step failed
        - ⊘  → step skipped
        - 正在執行 → step running (update current_step)
        """
        with self._lock:
            m = _RE_COMPLETED.search(progress_msg)
            if m:
                self.steps.append({
                    "step_name": m.group(1),
                    "status": "completed",
                    "duration_ms": _parse_duration_ms(progress_msg),
                    "error_message": None,
                })
                self.current_step = None
                return

            m = _RE_FAILED.search(progress_msg)
            if m:
                # Extract error message after " — "
                parts = progress_msg.split(" — ", 1)
                err = parts[1].strip() if len(parts) > 1 else None
                self.steps.append({
                    "step_name": m.group(1),
                    "status": "failed",
                    "duration_ms": None,
                    "error_message": err,
                })
                self.current_step = None
                return

            m = _RE_SKIPPED.search(progress_msg)
            if m:
                self.steps.append({
                    "step_name": m.group(1),
                    "status": "skipped",
                    "duration_ms": None,
                    "error_message": None,
                })
                self.current_step = None
                return

            m = _RE_RUNNING.search(progress_msg)
            if m:
                self.current_step = m.group(1)


class JobStore:
    """In-memory store for UpdateJob instances.

    Enforces at-most-one concurrent running job.
    All operations are protected by a threading.Lock.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._current_job: UpdateJob | None = None
        self._completed_jobs: dict[str, UpdateJob] = {}

    def try_create_job(self) -> UpdateJob | None:
        """Create a new UpdateJob if no job is currently running.

        Returns None if a running job already exists (caller should return 409).
        """
        with self._lock:
            if self._current_job is not None:
                return None
            job = UpdateJob(job_id=str(uuid.uuid4()))
            self._current_job = job
            return job

    def get_job(self, job_id: str) -> UpdateJob | None:
        """Retrieve a job by ID (running or completed). Returns None if not found."""
        with self._lock:
            if self._current_job is not None and self._current_job.job_id == job_id:
                return self._current_job
            return self._completed_jobs.get(job_id)

    def complete_job(self, job_id: str) -> None:
        """Mark the current job as completed and move it to completed_jobs."""
        with self._lock:
            if self._current_job is not None and self._current_job.job_id == job_id:
                self._current_job.status = "completed"
                self._current_job.current_step = None
                self._completed_jobs[job_id] = self._current_job
                self._current_job = None

    def fail_job(self, job_id: str, error_message: str) -> None:
        """Mark the current job as failed and move it to completed_jobs."""
        with self._lock:
            if self._current_job is not None and self._current_job.job_id == job_id:
                self._current_job.status = "failed"
                self._current_job.error_message = error_message
                self._current_job.current_step = None
                self._completed_jobs[job_id] = self._current_job
                self._current_job = None

    @property
    def has_running_job(self) -> bool:
        """True if a job is currently running."""
        with self._lock:
            return self._current_job is not None

    def get_running_job_id(self) -> str | None:
        """Return the job_id of the currently running job, or None."""
        with self._lock:
            return self._current_job.job_id if self._current_job is not None else None
