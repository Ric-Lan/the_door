"""UIServer — local HTTP server for The Door frontend viewer.

Uses Python standard library ThreadingHTTPServer.
Binds exclusively to 127.0.0.1 (loopback) for security.

Request routing:
- /api/* → Router (6 domain handlers)
- everything else → StaticHandler

All API responses include Access-Control-Allow-Origin: * header.
"""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from the_door.core.ui.api import APIContext, Router, build_routes
from the_door.core.ui.api.handlers.annotation import AnnotationHandlers
from the_door.core.ui.api.handlers.catalog import CatalogHandlers
from the_door.core.ui.api.handlers.diff import DiffHandlers
from the_door.core.ui.api.handlers.graph import GraphHandlers
from the_door.core.ui.api.handlers.group import GroupHandlers
from the_door.core.ui.api.handlers.integration import IntegrationHandlers
from the_door.core.ui.api.handlers.project import ProjectHandlers
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
        self._switch_lock = threading.Lock()
        ctx = APIContext(
            lambda: self._project_root,
            self._switch_project,
        )
        routes = build_routes(
            ProjectHandlers(ctx),
            CatalogHandlers(ctx),
            GraphHandlers(ctx),
            DiffHandlers(ctx),
            AnnotationHandlers(ctx),
            GroupHandlers(ctx),
            IntegrationHandlers(ctx),
        )
        self._router = Router(ctx, routes)
        self._static_handler = StaticHandler(viewer_dir=viewer_dir)

    def start(self) -> None:
        """Start the server and block until shutdown() is called.

        Raises OSError (errno.EADDRINUSE) if port is already in use.
        """
        router = self._router
        static_handler = self._static_handler

        class _RequestHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                _handle_get(self, router, static_handler)

            def do_POST(self):
                _handle_post(self, router)

            def log_message(self, format, *args):  # noqa: A002
                pass  # Suppress server log output to avoid polluting CLI

        self._httpd = ThreadingHTTPServer(("127.0.0.1", self._port), _RequestHandler)
        self._httpd.serve_forever()

    def shutdown(self) -> None:
        """Gracefully shut down the server."""
        if self._httpd is not None:
            self._httpd.shutdown()

    def _switch_project(self, new_path: Path, force: bool) -> dict:
        """Switch the server to a new project root.

        Args:
            new_path: The new project root path.
            force: If True, cancel any running job and switch. If False,
                   return conflict if a job is running.

        Returns:
            A dict with "status" key:
            - "switched": Successfully switched to new_path
            - "conflict": A job is running and force=False
        """
        # T5-A: analysis jobs retired (zero API-key) → no running-job conflict to
        # arbitrate; project switch is unconditional. `force` kept for API stability.
        with self._switch_lock:
            self._project_root = new_path
            return {"status": "switched", "path": str(new_path)}

    @property
    def url(self) -> str:
        """Return the server URL."""
        return f"http://127.0.0.1:{self._port}"


# ---------------------------------------------------------------------------
# Request handling functions (module-level for clarity)
# ---------------------------------------------------------------------------

# Router-generic error codes are remapped to the legacy bare codes that the
# HTTP surface has always exposed (the router's own unit tests pin the
# "router.*" forms; the HTTP contract pins the bare forms).
_ROUTER_ERROR_ALIASES: dict[str, str] = {
    "router.no_route": "not_found",
    "router.method_not_allowed": "method_not_allowed",
    "router.invalid_json": "invalid_json",
}


def _alias_router_error(body: dict) -> dict:
    """Remap router-generic error codes back to the legacy HTTP error codes."""
    err = body.get("error") if isinstance(body, dict) else None
    if isinstance(err, dict):
        alias = _ROUTER_ERROR_ALIASES.get(err.get("code"))
        if alias is not None:
            err["code"] = alias
    return body


def _handle_get(
    handler: BaseHTTPRequestHandler,
    router: Router,
    static_handler: StaticHandler,
) -> None:
    """Route GET requests."""
    parsed = urlparse(handler.path)
    path = parsed.path

    if path.startswith("/api/"):
        query = {k: v[0] for k, v in parse_qs(parsed.query).items()}
        status, body = router.dispatch("GET", path, raw_body=b"", query=query)
        _send_json(handler, status, _alias_router_error(body))
        return
    # Static file serving
    status, content_type, body_bytes = static_handler.serve(path)
    handler.send_response(status)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(body_bytes)))
    handler.end_headers()
    handler.wfile.write(body_bytes)


def _handle_post(
    handler: BaseHTTPRequestHandler,
    router: Router,
) -> None:
    """Route POST requests."""
    parsed = urlparse(handler.path)
    path = parsed.path

    if not path.startswith("/api/"):
        _send_api_error(handler, 404, "not_found", f"Unknown endpoint: {path}", path)
        return

    length = int(handler.headers.get("Content-Length", 0))
    raw = handler.rfile.read(length) if length > 0 else b""
    query = {k: v[0] for k, v in parse_qs(parsed.query).items()}
    status, body = router.dispatch("POST", path, raw_body=raw, query=query)
    _send_json(handler, status, _alias_router_error(body))


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
