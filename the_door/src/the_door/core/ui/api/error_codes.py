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

    "missing_params": ErrCode(
        http=400,
        file="core/ui/api/router.py",
        desc="Required query or body parameters are missing.",
    ),

    # --- snapshot / version domain ------------------------------------------
    "project_read_error": ErrCode(
        http=500,
        file="core/ui/api/handlers/project.py",
        desc="Failed to read project data.",
    ),
    "snapshot_read_error": ErrCode(
        http=500,
        file="core/ui/api/handlers/catalog.py",
        desc="Failed to read snapshot data.",
    ),
    "snapshot_not_found": ErrCode(
        http=404,
        file="core/ui/api/handlers/diff.py",
        desc="Snapshot not found.",
    ),
    "no_report_found": ErrCode(
        http=404,
        file="core/ui/api/handlers/catalog.py",
        desc="No report found for the requested version.",
    ),
    "report_parse_error": ErrCode(
        http=500,
        file="core/ui/api/handlers/catalog.py",
        desc="Failed to parse the report data.",
    ),
    "report_read_error": ErrCode(
        http=500,
        file="core/ui/api/handlers/catalog.py",
        desc="Failed to read the report file.",
    ),

    # --- job / async-job domain ---------------------------------------------
    "job_not_found": ErrCode(
        http=404,
        file="core/ui/api/handlers/analysis.py",
        desc="Job not found.",
    ),
    "job_already_running": ErrCode(
        http=409,
        file="core/ui/api/handlers/analysis.py",
        desc="A pipeline job is already running. Please wait for it to complete.",
    ),

    # --- analysis input validation ------------------------------------------
    "missing_required_field": ErrCode(
        http=400,
        file="core/ui/api/handlers/analysis.py",
        desc="A required request field is missing.",
    ),
    "invalid_path": ErrCode(
        http=400,
        file="core/ui/api/handlers/analysis.py",
        desc="The provided path is invalid.",
    ),
    "same_path": ErrCode(
        http=400,
        file="core/ui/api/handlers/analysis.py",
        desc="old_path and new_path must be different directories.",
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
    "provider_not_configured": ErrCode(
        http=503,
        file="core/ui/api/handlers/diff.py",
        desc="LLM provider is not configured.",
    ),

    # --- structure / graph domain -------------------------------------------
    "structure_read_error": ErrCode(
        http=500,
        file="core/ui/api/handlers/graph.py",
        desc="Failed to read structure data.",
    ),
    "no_structure_data": ErrCode(
        http=404,
        file="core/ui/api/handlers/graph.py",
        desc="Structure data not found. Run 'the-door extract' first.",
    ),
    "invalid_layer": ErrCode(
        http=400,
        file="core/ui/api/handlers/graph.py",
        desc="Invalid analysis layer requested.",
    ),
    "no_l1_data": ErrCode(
        http=404,
        file="core/ui/api/handlers/graph.py",
        desc="No L1 analysis data is available for this project yet.",
    ),
    "l1_read_error": ErrCode(
        http=500,
        file="core/ui/api/handlers/graph.py",
        desc="Failed to read L1 analysis data.",
    ),
    "l2_read_error": ErrCode(
        http=500,
        file="core/ui/api/handlers/graph.py",
        desc="Failed to read L2 analysis data.",
    ),
    "l2_not_generated": ErrCode(
        http=404,
        file="core/ui/api/handlers/graph.py",
        desc="L2 analysis has not been generated yet.",
    ),

    # --- diff-explanation domain --------------------------------------------
    "explanation_read_error": ErrCode(
        http=500,
        file="core/ui/api/handlers/diff.py",
        desc="Failed to read diff explanation.",
    ),
    "explanation_not_cached": ErrCode(
        http=404,
        file="core/ui/api/handlers/graph.py",
        desc="No cached diff explanation is available for the requested version.",
    ),

    # --- timeline domain ----------------------------------------------------
    "timeline_error": ErrCode(
        http=500,
        file="core/ui/api/handlers/catalog.py",
        desc="Failed to build timeline.",
    ),

    # --- LLM / generation domain --------------------------------------------
    "llm_error": ErrCode(
        http=500,
        file="core/ui/api/handlers/graph.py",
        desc="LLM generation failed.",
    ),

    # --- annotation domain --------------------------------------------------
    "empty_name": ErrCode(
        http=400,
        file="core/ui/api/handlers/annotation.py",
        desc="Name must not be empty.",
    ),
    "name_too_long": ErrCode(
        http=400,
        file="core/ui/api/handlers/annotation.py",
        desc="Name exceeds the maximum allowed length.",
    ),
    "empty_comment": ErrCode(
        http=400,
        file="core/ui/api/handlers/annotation.py",
        desc="Comment text must not be empty.",
    ),
    "comment_too_long": ErrCode(
        http=400,
        file="core/ui/api/handlers/annotation.py",
        desc="Comment exceeds the maximum allowed length.",
    ),
    "invalid_mode": ErrCode(
        http=400,
        file="core/ui/api/handlers/annotation.py",
        desc="Invalid mode requested.",
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
    if code not in ERROR_CODES:
        raise ValueError(f"unregistered error code: {code!r}")
    ec = ERROR_CODES[code]
    return ec.http, {
        "error": {
            "code": code,
            "message": message if message is not None else ec.desc,
            "source": source,
            "source_file": source_file if source_file is not None else ec.file,
        }
    }
