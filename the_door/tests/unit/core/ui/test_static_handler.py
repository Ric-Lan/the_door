"""Tests for StaticHandler — static file serving with path traversal prevention."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def viewer_dir(tmp_path):
    """Create a temporary viewer directory with test files."""
    # Create test files
    (tmp_path / "index.html").write_text("<html>index</html>", encoding="utf-8")
    (tmp_path / "styles.css").write_text("body {}", encoding="utf-8")
    (tmp_path / "app.js").write_text("console.log('hi')", encoding="utf-8")
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "foo.json").write_text('{"key": "value"}', encoding="utf-8")
    return tmp_path


def test_serve_index_html(viewer_dir):
    from the_door.core.ui.static_handler import StaticHandler
    handler = StaticHandler(viewer_dir)
    status, content_type, body = handler.serve("/index.html")
    assert status == 200
    assert "text/html" in content_type
    assert b"index" in body


def test_serve_root_redirects_to_index(viewer_dir):
    from the_door.core.ui.static_handler import StaticHandler
    handler = StaticHandler(viewer_dir)
    status, content_type, body = handler.serve("/")
    assert status == 200
    assert b"index" in body


def test_serve_css_correct_content_type(viewer_dir):
    from the_door.core.ui.static_handler import StaticHandler
    handler = StaticHandler(viewer_dir)
    status, content_type, body = handler.serve("/styles.css")
    assert status == 200
    assert content_type == "text/css; charset=utf-8"


def test_serve_js_correct_content_type(viewer_dir):
    from the_door.core.ui.static_handler import StaticHandler
    handler = StaticHandler(viewer_dir)
    status, content_type, body = handler.serve("/app.js")
    assert status == 200
    assert content_type == "application/javascript; charset=utf-8"


def test_serve_json_correct_content_type(viewer_dir):
    from the_door.core.ui.static_handler import StaticHandler
    handler = StaticHandler(viewer_dir)
    status, content_type, body = handler.serve("/data/foo.json")
    assert status == 200
    assert content_type == "application/json; charset=utf-8"


def test_serve_missing_file_returns_404(viewer_dir):
    from the_door.core.ui.static_handler import StaticHandler
    handler = StaticHandler(viewer_dir)
    status, content_type, body = handler.serve("/nonexistent.txt")
    assert status == 404


def test_path_traversal_rejected(viewer_dir, tmp_path):
    from the_door.core.ui.static_handler import StaticHandler
    # Create a secret file outside viewer_dir
    secret = tmp_path.parent / "secret.txt"
    secret.write_text("secret", encoding="utf-8")
    handler = StaticHandler(viewer_dir)
    # resolve_path should return None for traversal attempts
    result = handler.resolve_path("/../secret.txt")
    assert result is None
    # serve should return 403
    status, _, _ = handler.serve("/../secret.txt")
    assert status == 403


def test_path_traversal_encoded_dots_rejected(viewer_dir):
    from the_door.core.ui.static_handler import StaticHandler
    handler = StaticHandler(viewer_dir)
    result = handler.resolve_path("/%2e%2e/secret.txt")
    assert result is None
    status, _, _ = handler.serve("/%2e%2e/secret.txt")
    assert status == 403


def test_serve_cytoscape_min_js_correct_content_type(viewer_dir):
    """Static_Handler serves viewer/lib/cytoscape.min.js with Content-Type: application/javascript.

    Validates Task 11.6 / Req 13 AC4.
    """
    from the_door.core.ui.static_handler import StaticHandler

    # Create lib/ subdirectory with a stub cytoscape.min.js
    lib_dir = viewer_dir / "lib"
    lib_dir.mkdir()
    (lib_dir / "cytoscape.min.js").write_bytes(b"/* cytoscape stub */")

    handler = StaticHandler(viewer_dir)
    status, content_type, body = handler.serve("/lib/cytoscape.min.js")

    assert status == 200, f"Expected 200, got {status}"
    assert content_type == "application/javascript; charset=utf-8", (
        f"Expected 'application/javascript; charset=utf-8', got '{content_type}'"
    )
    assert b"cytoscape" in body
