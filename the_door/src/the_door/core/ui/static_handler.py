"""StaticHandler — serve static frontend files with path traversal prevention.

Design:
- resolve_path() returns None ONLY for path traversal (outside viewer_dir) → 403
- If path is valid but file doesn't exist → serve() returns 404
- If path is valid and file exists → serve() returns 200 with correct Content-Type
"""
from __future__ import annotations

from pathlib import Path
from urllib.parse import unquote


class StaticHandler:
    """Serve static files from viewer_dir with path traversal prevention."""

    CONTENT_TYPES: dict[str, str] = {
        ".html": "text/html; charset=utf-8",
        ".css":  "text/css; charset=utf-8",
        ".js":   "application/javascript; charset=utf-8",
        ".json": "application/json; charset=utf-8",
    }

    def __init__(self, viewer_dir: Path) -> None:
        self._viewer_dir = viewer_dir.resolve()

    def resolve_path(self, request_path: str) -> Path | None:
        """Resolve request path to an absolute file path.

        Returns:
            Path: The resolved absolute path (may or may not exist — caller checks)
            None: Path traversal detected (resolves outside viewer_dir) → 403

        Special cases:
        - '/' or '/index.html' → viewer_dir/index.html
        - URL-encoded paths are decoded before resolution
        """
        # Decode URL encoding (e.g., %2e%2e → ..)
        decoded = unquote(request_path)

        # Normalize: strip query string and fragment
        path_part = decoded.split("?")[0].split("#")[0]

        # Handle root
        if path_part in ("/", ""):
            path_part = "/index.html"

        # Strip leading slash and resolve relative to viewer_dir
        relative = path_part.lstrip("/")
        candidate = (self._viewer_dir / relative).resolve()

        # Security check: must be within viewer_dir
        try:
            candidate.relative_to(self._viewer_dir)
        except ValueError:
            return None  # Path traversal → 403

        return candidate

    def get_content_type(self, path: Path) -> str:
        """Return Content-Type for the given file path."""
        return self.CONTENT_TYPES.get(path.suffix.lower(), "application/octet-stream")

    def serve(self, request_path: str) -> tuple[int, str, bytes]:
        """Serve a static file.

        Returns:
            (200, content_type, body): File found and served
            (404, "text/plain", b"Not Found"): File not found (path valid but missing)
            (403, "text/plain", b"Forbidden"): Path traversal attempt
        """
        resolved = self.resolve_path(request_path)

        if resolved is None:
            return 403, "text/plain; charset=utf-8", b"Forbidden"

        if not resolved.exists() or not resolved.is_file():
            return 404, "text/plain; charset=utf-8", b"Not Found"

        content_type = self.get_content_type(resolved)
        body = resolved.read_bytes()
        return 200, content_type, body
