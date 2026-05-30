"""ProgressReporter — file-level progress channel for analyze/update pipelines.

Decoupled from job_store / api_handlers: callers inject any `sink` callable
that consumes a progress dict. Production wiring routes sink to
`UpdateJob.update_progress`. Tests use list-append sinks.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Literal

ProgressDict = dict
Sink = Callable[[ProgressDict], None]


class ProgressReporter:
    """Tracks file-level analysis progress and pushes dicts to a sink."""

    def __init__(self, sink: Sink) -> None:
        self._sink = sink
        self._files_done = 0
        self._files_total = 0
        self._root: Literal["new", "old"] = "new"

    def set_total(self, total: int, *, root: Literal["new", "old"]) -> None:
        if root not in ("new", "old"):
            raise ValueError("root must be 'new' or 'old'")
        self._files_total = total
        self._files_done = 0
        self._root = root

    def report_file(self, path: str) -> None:
        if self._files_total > 0:
            self._files_done = min(self._files_done + 1, self._files_total)
        else:
            self._files_done += 1
        self._sink({
            "files_done": self._files_done,
            "files_total": self._files_total,
            "current_file": path,
            "current_root": self._root,
        })


class NoOpProgressReporter(ProgressReporter):
    """Default reporter when caller does not wire one (CLI / MCP path)."""

    def __init__(self) -> None:
        super().__init__(sink=lambda _d: None)
