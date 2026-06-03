# Error Codes

Auto-generated from `the_door.core.ui.api.error_codes.ERROR_CODES`. Do not edit by hand — run `python -m the_door.core.ui.api._gen_docs` to regenerate.

Total codes: 35

| Code | HTTP | Source File | Description |
| --- | --- | --- | --- |
| `comment_too_long` | 400 | `core/ui/api/handlers/annotation.py` | Comment exceeds the maximum allowed length. |
| `diff_error` | 500 | `core/ui/api/handlers/diff.py` | Failed to compute diff. |
| `doubt_read_error` | 500 | `core/ui/api/handlers/diff.py` | Failed to read doubt/explanation data. |
| `empty_comment` | 400 | `core/ui/api/handlers/annotation.py` | Comment text must not be empty. |
| `empty_name` | 400 | `core/ui/api/handlers/annotation.py` | Name must not be empty. |
| `explanation_not_cached` | 404 | `core/ui/api/handlers/graph.py` | No cached diff explanation is available for the requested version. |
| `explanation_read_error` | 500 | `core/ui/api/handlers/diff.py` | Failed to read diff explanation. |
| `invalid_layer` | 400 | `core/ui/api/handlers/graph.py` | Invalid analysis layer requested. |
| `invalid_mode` | 400 | `core/ui/api/handlers/annotation.py` | Invalid mode requested. |
| `invalid_path` | 400 | `core/ui/api/handlers/analysis.py` | The provided path is invalid. |
| `job_already_running` | 409 | `core/ui/api/handlers/analysis.py` | A pipeline job is already running. Please wait for it to complete. |
| `job_not_found` | 404 | `core/ui/api/handlers/analysis.py` | Job not found. |
| `l1_read_error` | 500 | `core/ui/api/handlers/graph.py` | Failed to read L1 analysis data. |
| `l2_not_generated` | 404 | `core/ui/api/handlers/graph.py` | L2 analysis has not been generated yet. |
| `l2_read_error` | 500 | `core/ui/api/handlers/graph.py` | Failed to read L2 analysis data. |
| `llm_error` | 500 | `core/ui/api/handlers/graph.py` | LLM generation failed. |
| `missing_params` | 400 | `core/ui/api/router.py` | Required query or body parameters are missing. |
| `missing_required_field` | 400 | `core/ui/api/handlers/analysis.py` | A required request field is missing. |
| `name_too_long` | 400 | `core/ui/api/handlers/annotation.py` | Name exceeds the maximum allowed length. |
| `no_l1_data` | 404 | `core/ui/api/handlers/graph.py` | No L1 analysis data is available for this project yet. |
| `no_report_found` | 404 | `core/ui/api/handlers/catalog.py` | No report found for the requested version. |
| `no_structure_data` | 404 | `core/ui/api/handlers/graph.py` | Structure data not found. Run 'the-door extract' first. |
| `project_read_error` | 500 | `core/ui/api/handlers/project.py` | Failed to read project data. |
| `provider_not_configured` | 503 | `core/ui/api/handlers/diff.py` | LLM provider is not configured. |
| `report_parse_error` | 500 | `core/ui/api/handlers/catalog.py` | Failed to parse the report data. |
| `report_read_error` | 500 | `core/ui/api/handlers/catalog.py` | Failed to read the report file. |
| `router.handler_error` | 500 | `core/ui/api/router.py` | An unhandled error occurred in the route handler. |
| `router.invalid_json` | 400 | `core/ui/api/router.py` | Request body is not valid JSON. |
| `router.method_not_allowed` | 405 | `core/ui/api/router.py` | HTTP method not allowed for this route. |
| `router.no_route` | 404 | `core/ui/api/router.py` | No route matched the requested path. |
| `same_path` | 400 | `core/ui/api/handlers/analysis.py` | old_path and new_path must be different directories. |
| `snapshot_not_found` | 404 | `core/ui/api/handlers/diff.py` | Snapshot not found. |
| `snapshot_read_error` | 500 | `core/ui/api/handlers/catalog.py` | Failed to read snapshot data. |
| `structure_read_error` | 500 | `core/ui/api/handlers/graph.py` | Failed to read structure data. |
| `timeline_error` | 500 | `core/ui/api/handlers/catalog.py` | Failed to build timeline. |
