"""APIContext — immutable lazy dependency holder for UI API handlers.

Rather than passing individual dependencies (project_root, job_store, …) into
every handler, handlers receive a single ``APIContext`` instance.  All values
are resolved lazily through callables so that the context object can be built
once at server start-up and still reflect live state (e.g. the current project
root can change when the user switches projects).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


@dataclass(frozen=True)
class APIContext:
    """Immutable bag of callables that resolve live dependencies on demand."""

    _project_root_fn: Callable[[], Path]
    _switch_project_fn: Callable[[str, bool], Any]

    @property
    def project_root(self) -> Path:
        """Current project root — re-evaluated on every access."""
        return self._project_root_fn()

    def switch_project(self, path: str, force: bool) -> Any:
        """Delegate to the switch-project callable."""
        return self._switch_project_fn(path, force)
