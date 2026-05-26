"""UIServer — local HTTP server for The Door frontend viewer.

Uses Python standard library ThreadingHTTPServer.
Binds exclusively to 127.0.0.1 (loopback) for security.

Request routing:
- /api/* → APIHandlers
- everything else → StaticHandler

All API responses include Access-Control-Allow-Origin: * header.
"""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from the_door.core.ui.api_handlers import APIHandlers
from the_door.core.ui.job_store import JobStore
from the_door.core.ui.static_handler import StaticHandler


class UIServer:
    """Local HTTP server for the frontend viewer.

    Binds to 127.0.0.1 only. Uses ThreadingHTTPServer to handle
    concurrent requests (static assets + API polling).
    """

    def __init__(
        self,
        project_root: Path,
        viewer_dir: Path,
        port: int = 8765,
    ) -> None:
        self._project_root = project_root
        self._viewer_dir = viewer_dir
        self._port = port
        self._httpd: ThreadingHTTPServer | None = None

        # Shared state passed to request handler via closure
        self._job_store = JobStore()
        self._api_handlers = APIHandlers(project_root=project_root, job_store=self._job_store)
        self._static_handler = StaticHandler(viewer_dir=viewer_dir)

    def start(self) -> None:
        """Start the server and block until shutdown() is called.

        Raises OSError (errno.EADDRINUSE) if port is already in use.
        """
        api_handlers = self._api_handlers
        static_handler = self._static_handler

        class _RequestHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                _handle_get(self, api_handlers, static_handler)

            def do_POST(self):
                _handle_post(self, api_handlers)

            def log_message(self, format, *args):  # noqa: A002
                pass  # Suppress server log output to avoid polluting CLI

        self._httpd = ThreadingHTTPServer(("127.0.0.1", self._port), _RequestHandler)
        self._httpd.serve_forever()

    def shutdown(self) -> None:
        """Gracefully shut down the server."""
        if self._httpd is not None:
            self._httpd.shutdown()

    @property
    def url(self) -> str:
        """Return the server URL."""
        return f"http://127.0.0.1:{self._port}"


# ---------------------------------------------------------------------------
# Request handling functions (module-level for clarity)
# ---------------------------------------------------------------------------

# API endpoints and their allowed methods
_API_ROUTES: dict[str, str] = {
    "/api/project": "GET",
    "/api/snapshots": "GET",
    "/api/report/latest": "GET",
    "/api/update": "POST",
    "/api/analyze": "POST",
    "/api/doubts": "GET",
    "/api/timeline": "GET",
    "/api/l1": "GET",
    "/api/diff": "GET",
    "/api/status": "GET",
    "/api/structure": "GET",
    "/api/notes": "GET",
}


def _handle_get(
    handler: BaseHTTPRequestHandler,
    api_handlers: APIHandlers,
    static_handler: StaticHandler,
) -> None:
    """Route GET requests."""
    parsed_url = urlparse(handler.path)
    path = parsed_url.path
    query_params = parse_qs(parsed_url.query)

    if path.startswith("/api/"):
        # Check method is allowed for static routes
        allowed = _API_ROUTES.get(path)
        # Determine if path matches a known dynamic GET pattern
        parts = path.split("/")  # e.g. ['', 'api', 'l2', '<feature_id>']
        is_dynamic_get = (
            path.startswith("/api/update/status/")
            or (len(parts) == 4 and parts[1] == "api" and parts[2] == "l2")
            or (len(parts) == 5 and parts[1] == "api" and parts[2] == "layer-explanation")
            or (len(parts) == 4 and parts[1] == "api" and parts[2] == "diff-explanations")
        )
        if allowed is None and not is_dynamic_get:
            _send_api_error(handler, 404, "not_found", f"Unknown endpoint: {path}", path)
            return
        if allowed == "POST":
            _send_api_error(handler, 405, "method_not_allowed", "Method not allowed", path)
            return

        # Route to appropriate handler
        if path == "/api/project":
            status, body = api_handlers.handle_get_project()
        elif path == "/api/snapshots":
            status, body = api_handlers.handle_get_snapshots()
        elif path == "/api/report/latest":
            status, body = api_handlers.handle_get_report_latest()
        elif path == "/api/doubts":
            status, body = api_handlers.handle_get_doubts()
        elif path == "/api/timeline":
            status, body = api_handlers.handle_get_timeline()
        elif path == "/api/l1":
            version_id = query_params.get("version_id", [None])[0]
            status, body = api_handlers.handle_get_l1(version_id=version_id)
        elif path == "/api/diff":
            baseline_id = query_params.get("baseline", [None])[0]
            current_id = query_params.get("current", [None])[0]
            if not baseline_id or not current_id:
                _send_api_error(handler, 400, "missing_params", "baseline and current query params required", path)
                return
            status, body = api_handlers.handle_diff_versions(baseline_id, current_id)
        elif path == "/api/status":
            status, body = api_handlers.handle_get_status()
        elif path == "/api/structure":
            status, body = api_handlers.handle_get_structure()
        elif path == "/api/notes":
            mode = query_params.get("mode", [None])[0]
            feature_id = query_params.get("feature_id", [None])[0]
            version_a = query_params.get("version_a", [None])[0]
            version_b = query_params.get("version_b", [None])[0]
            status, body = api_handlers.handle_get_notes(mode, feature_id, version_a, version_b)
        elif path.startswith("/api/update/status/"):
            job_id = path[len("/api/update/status/"):]
            status, body = api_handlers.handle_get_update_status(job_id)
        elif len(parts) == 4 and parts[1] == "api" and parts[2] == "l2":
            # /api/l2/<feature_id>
            feature_id = parts[3]
            status, body = api_handlers.handle_get_l2(feature_id)
        elif len(parts) == 5 and parts[1] == "api" and parts[2] == "layer-explanation":
            # /api/layer-explanation/<feature_id>/<layer>
            feature_id = parts[3]
            layer = parts[4]
            status, body = api_handlers.handle_get_layer_explanation(feature_id, layer)
        elif len(parts) == 4 and parts[1] == "api" and parts[2] == "diff-explanations":
            # GET /api/diff-explanations/<feature_id>
            feature_id = parts[3]
            baseline_version_id = query_params.get("baseline_version_id", [None])[0]
            current_version_id = query_params.get("current_version_id", [None])[0]
            output_language = query_params.get("output_language", [None])[0]
            status, body = api_handlers.handle_get_diff_explanation(
                feature_id, baseline_version_id, current_version_id, output_language
            )
        else:
            _send_api_error(handler, 404, "not_found", f"Unknown endpoint: {path}", path)
            return

        _send_json(handler, status, body)
    else:
        # Static file serving
        status, content_type, body_bytes = static_handler.serve(path)
        handler.send_response(status)
        handler.send_header("Content-Type", content_type)
        handler.send_header("Content-Length", str(len(body_bytes)))
        handler.end_headers()
        handler.wfile.write(body_bytes)


def _handle_post(
    handler: BaseHTTPRequestHandler,
    api_handlers: APIHandlers,
) -> None:
    """Route POST requests."""
    path = handler.path.split("?")[0]

    if not path.startswith("/api/"):
        _send_api_error(handler, 404, "not_found", f"Unknown endpoint: {path}", path)
        return

    # /api/notes supports both GET and POST
    if path == "/api/notes":
        content_length = int(handler.headers.get("Content-Length", 0))
        raw_body = handler.rfile.read(content_length) if content_length > 0 else b""
        try:
            body = json.loads(raw_body) if raw_body else {}
        except json.JSONDecodeError:
            _send_api_error(handler, 400, "invalid_json", "Request body is not valid JSON", path)
            return
        status, response_body = api_handlers.handle_post_notes(body)
        _send_json(handler, status, response_body)
        return

    # Check method is allowed for static routes
    allowed = _API_ROUTES.get(path)
    if allowed == "GET":
        _send_api_error(handler, 405, "method_not_allowed", "Method not allowed", path)
        return

    if path == "/api/analyze":
        content_length = int(handler.headers.get("Content-Length", 0))
        raw_body = handler.rfile.read(content_length) if content_length > 0 else b""
        try:
            body = json.loads(raw_body) if raw_body else {}
        except json.JSONDecodeError:
            _send_api_error(handler, 400, "invalid_json", "Request body is not valid JSON", path)
            return
        status, response_body = api_handlers.handle_post_analyze(body)
        _send_json(handler, status, response_body)
        return

    if path == "/api/update":
        # Parse JSON body
        content_length = int(handler.headers.get("Content-Length", 0))
        raw_body = handler.rfile.read(content_length) if content_length > 0 else b""
        try:
            body = json.loads(raw_body) if raw_body else {}
        except json.JSONDecodeError:
            _send_api_error(handler, 400, "invalid_json", "Request body is not valid JSON", path)
            return

        status, response_body = api_handlers.handle_post_update(body)
        _send_json(handler, status, response_body)
    else:
        # Check dynamic POST routes
        parts = path.split("/")  # e.g. ['', 'api', 'l2', '<feature_id>', 'generate']
        if (
            len(parts) == 5
            and parts[1] == "api"
            and parts[2] == "l2"
            and parts[4] == "generate"
        ):
            # /api/l2/<feature_id>/generate
            feature_id = parts[3]
            status, response_body = api_handlers.handle_post_l2_generate(feature_id)
            _send_json(handler, status, response_body)
        elif (
            len(parts) == 6
            and parts[1] == "api"
            and parts[2] == "layer-explanation"
            and parts[5] == "generate"
        ):
            # /api/layer-explanation/<feature_id>/<layer>/generate
            feature_id = parts[3]
            layer = parts[4]
            status, response_body = api_handlers.handle_post_layer_explanation_generate(
                feature_id, layer
            )
            _send_json(handler, status, response_body)
        elif (
            len(parts) == 5
            and parts[1] == "api"
            and parts[2] == "diff-explanations"
            and parts[4] == "generate"
        ):
            # POST /api/diff-explanations/<feature_id>/generate
            feature_id = parts[3]
            content_length = int(handler.headers.get("Content-Length", 0))
            raw_body = handler.rfile.read(content_length) if content_length > 0 else b""
            try:
                post_body = json.loads(raw_body) if raw_body else {}
            except json.JSONDecodeError:
                _send_api_error(handler, 400, "invalid_json", "Request body is not valid JSON", path)
                return
            status, response_body = api_handlers.handle_post_diff_explanation_generate(
                feature_id, post_body
            )
            _send_json(handler, status, response_body)
        else:
            _send_api_error(handler, 405, "method_not_allowed", "Method not allowed", path)


def _send_json(handler: BaseHTTPRequestHandler, status: int, body: dict) -> None:
    """Send a JSON response with CORS header."""
    encoded = json.dumps(body, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(encoded)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.end_headers()
    handler.wfile.write(encoded)


def _send_api_error(
    handler: BaseHTTPRequestHandler,
    status: int,
    code: str,
    message: str,
    source: str,
) -> None:
    """Send a standard API_Error_Response."""
    _send_json(handler, status, {"error": {"code": code, "message": message, "source": source}})
