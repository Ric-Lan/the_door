"""Central error-code registry for core/ui/api.

Every business error code used anywhere in the UI API layer is registered here.
All descriptions MUST be ASCII English.
`build_error` produces a uniform (status, body) tuple for handler responses.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ErrCode:
    http: int
    file: str   # src-relative path marker (identifies owning module)
    desc: str   # English ASCII description


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

ERROR_CODES: dict[str, ErrCode] = {
    # --- router generic codes -----------------------------------------------
    "router.no_route": ErrCode(
        http=404,
        file="core/ui/api/router.py",
        desc="No route matched the requested path.",
    ),
    "router.method_not_allowed": ErrCode(
        http=405,
        file="core/ui/api/router.py",
        desc="HTTP method not allowed for this route.",
    ),
    "router.invalid_json": ErrCode(
        http=400,
        file="core/ui/api/router.py",
        desc="Request body is not valid JSON.",
    ),
    "router.handler_error": ErrCode(
        http=500,
        file="core/ui/api/router.py",
        desc="An unhandled error occurred in the route handler.",
    ),

    # --- generic server-level codes (legacy server.py) ----------------------
    "not_found": ErrCode(
        http=404,
        file="core/ui/api/router.py",
        desc="Unknown endpoint.",
    ),
    "method_not_allowed": ErrCode(
        http=405,
        file="core/ui/api/router.py",
        desc="HTTP method not allowed.",
    ),
    "invalid_json": ErrCode(
        http=400,
        file="core/ui/api/router.py",
        desc="Request body is not valid JSON.",
    ),
    "missing_params": ErrCode(
        http=400,
        file="core/ui/api/router.py",
        desc="Required query or body parameters are missing.",
    ),

    # --- snapshot / version domain ------------------------------------------
    "project_read_error": ErrCode(
        http=500,
        file="core/ui/api/handlers/snapshot.py",
        desc="Failed to read project data.",
    ),
    "snapshot_read_error": ErrCode(
        http=500,
        file="core/ui/api/handlers/snapshot.py",
        desc="Failed to read snapshot data.",
    ),
    "snapshot_not_found": ErrCode(
        http=404,
        file="core/ui/api/handlers/snapshot.py",
        desc="Snapshot not found.",
    ),
    "no_report_found": ErrCode(
        http=404,
        file="core/ui/api/handlers/snapshot.py",
        desc="No report found for the requested version.",
    ),
    "report_parse_error": ErrCode(
        http=500,
        file="core/ui/api/handlers/snapshot.py",
        desc="Failed to parse the report data.",
    ),
    "report_read_error": ErrCode(
        http=500,
        file="core/ui/api/handlers/snapshot.py",
        desc="Failed to read the report file.",
    ),

    # --- job / async-job domain ---------------------------------------------
    "job_not_found": ErrCode(
        http=404,
        file="core/ui/api/handlers/jobs.py",
        desc="Job not found.",
    ),

    # --- diff domain --------------------------------------------------------
    "diff_error": ErrCode(
        http=500,
        file="core/ui/api/handlers/diff.py",
        desc="Failed to compute diff.",
    ),
    "doubt_read_error": ErrCode(
        http=500,
        file="core/ui/api/handlers/diff.py",
        desc="Failed to read doubt/explanation data.",
    ),

    # --- structure / graph domain -------------------------------------------
    "structure_read_error": ErrCode(
        http=500,
        file="core/ui/api/handlers/graph.py",
        desc="Failed to read structure data.",
    ),

    # --- diff-explanation domain --------------------------------------------
    "explanation_read_error": ErrCode(
        http=500,
        file="core/ui/api/handlers/diff.py",
        desc="Failed to read diff explanation.",
    ),

    # --- timeline domain ----------------------------------------------------
    "timeline_error": ErrCode(
        http=500,
        file="core/ui/api/handlers/snapshot.py",
        desc="Failed to build timeline.",
    ),

    # --- LLM / generation domain --------------------------------------------
    "llm_error": ErrCode(
        http=500,
        file="core/ui/api/handlers/graph.py",
        desc="LLM generation failed.",
    ),
}


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------

def build_error(
    code: str,
    *,
    source: str,
    message: Optional[str] = None,
    source_file: Optional[str] = None,
) -> tuple[int, dict]:
    """Return ``(http_status, body_dict)`` for the given error code.

    ``source_file`` defaults to the registry entry's ``file`` marker when not
    supplied explicitly.  ``message`` defaults to the registry ``desc``.
    """
    ec = ERROR_CODES[code]
    return ec.http, {
        "error": {
            "code": code,
            "message": message if message is not None else ec.desc,
            "source": source,
            "source_file": source_file if source_file is not None else ec.file,
        }
    }
