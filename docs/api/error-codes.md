# Error Codes

Auto-generated from `the_door.core.ui.api.error_codes.ERROR_CODES`. Do not edit by hand — run `python -m the_door.core.ui.api._gen_docs` to regenerate.

Total codes: 18

| Code | HTTP | Source File | Description |
| --- | --- | --- | --- |
| `diff_error` | 500 | `core/ui/api/handlers/diff.py` | Failed to compute diff. |
| `doubt_read_error` | 500 | `core/ui/api/handlers/diff.py` | Failed to read doubt/explanation data. |
| `explanation_read_error` | 500 | `core/ui/api/handlers/diff.py` | Failed to read diff explanation. |
| `job_not_found` | 404 | `core/ui/api/handlers/analysis.py` | Job not found. |
| `llm_error` | 500 | `core/ui/api/handlers/graph.py` | LLM generation failed. |
| `missing_params` | 400 | `core/ui/api/router.py` | Required query or body parameters are missing. |
| `no_report_found` | 404 | `core/ui/api/handlers/catalog.py` | No report found for the requested version. |
| `project_read_error` | 500 | `core/ui/api/handlers/project.py` | Failed to read project data. |
| `report_parse_error` | 500 | `core/ui/api/handlers/catalog.py` | Failed to parse the report data. |
| `report_read_error` | 500 | `core/ui/api/handlers/catalog.py` | Failed to read the report file. |
| `router.handler_error` | 500 | `core/ui/api/router.py` | An unhandled error occurred in the route handler. |
| `router.invalid_json` | 400 | `core/ui/api/router.py` | Request body is not valid JSON. |
| `router.method_not_allowed` | 405 | `core/ui/api/router.py` | HTTP method not allowed for this route. |
| `router.no_route` | 404 | `core/ui/api/router.py` | No route matched the requested path. |
| `snapshot_not_found` | 404 | `core/ui/api/handlers/diff.py` | Snapshot not found. |
| `snapshot_read_error` | 500 | `core/ui/api/handlers/catalog.py` | Failed to read snapshot data. |
| `structure_read_error` | 500 | `core/ui/api/handlers/graph.py` | Failed to read structure data. |
| `timeline_error` | 500 | `core/ui/api/handlers/catalog.py` | Failed to build timeline. |
