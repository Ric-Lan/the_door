"""Tests for UIServer and _RequestHandler routing."""
from __future__ import annotations

import json
import socket
import threading
import time
from http.client import HTTPConnection
from pathlib import Path

import pytest


def _find_free_port() -> int:
    """Find an available TCP port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def viewer_dir(tmp_path):
    """Create a minimal viewer directory."""
    (tmp_path / "index.html").write_text("<html>viewer</html>", encoding="utf-8")
    return tmp_path


@pytest.fixture
def running_server(tmp_path, viewer_dir):
    """Start a UIServer on a free port, yield (server, port), then shut down."""
    from the_door.core.ui.server import UIServer
    port = _find_free_port()
    server = UIServer(project_root=tmp_path, viewer_dir=viewer_dir, port=port)
    thread = threading.Thread(target=server.start, daemon=True)
    thread.start()
    # Wait for server to be ready
    for _ in range(20):
        try:
            conn = HTTPConnection("127.0.0.1", port, timeout=1)
            conn.request("GET", "/api/project")
            conn.getresponse()
            conn.close()
            break
        except Exception:
            time.sleep(0.05)
    yield server, port
    server.shutdown()


def test_method_not_allowed_on_get_endpoint(running_server):
    """POST to a GET-only endpoint should return 405."""
    server, port = running_server
    conn = HTTPConnection("127.0.0.1", port, timeout=5)
    conn.request("POST", "/api/project", body=b"{}", headers={"Content-Type": "application/json"})
    resp = conn.getresponse()
    assert resp.status == 405
    body = json.loads(resp.read())
    assert body["error"]["code"] == "method_not_allowed"
    conn.close()


def test_invalid_json_body_returns_400(running_server):
    """POST /api/update with non-JSON body should return 400 invalid_json."""
    server, port = running_server
    conn = HTTPConnection("127.0.0.1", port, timeout=5)
    conn.request("POST", "/api/update", body=b"NOT JSON", headers={"Content-Type": "application/json"})
    resp = conn.getresponse()
    assert resp.status == 400
    body = json.loads(resp.read())
    assert body["error"]["code"] == "invalid_json"
    conn.close()


def test_cors_header_present(running_server):
    """All API responses should include Access-Control-Allow-Origin: *."""
    server, port = running_server
    conn = HTTPConnection("127.0.0.1", port, timeout=5)
    conn.request("GET", "/api/project")
    resp = conn.getresponse()
    resp.read()
    assert resp.getheader("Access-Control-Allow-Origin") == "*"


class TestNotesRouting:
    def test_get_notes_returns_200_with_valid_params(self, running_server):
        server, port = running_server
        conn = HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request(
            "GET",
            "/api/notes?mode=diff&feature_id=feat-x&version_a=v1&version_b=v2",
        )
        resp = conn.getresponse()
        assert resp.status == 200
        body = json.loads(resp.read())
        assert "notes" in body
        conn.close()

    def test_get_notes_missing_params_returns_400(self, running_server):
        server, port = running_server
        conn = HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", "/api/notes?feature_id=feat-x")
        resp = conn.getresponse()
        assert resp.status == 400
        conn.close()

    def test_post_notes_returns_201(self, running_server):
        server, port = running_server
        payload = json.dumps({
            "mode": "diff",
            "feature_id": "feat-x",
            "version_a": "v1",
            "version_b": "v2",
            "name_input": "Ric",
            "comment": "test note",
        }).encode()
        conn = HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request(
            "POST", "/api/notes",
            body=payload,
            headers={"Content-Type": "application/json"},
        )
        resp = conn.getresponse()
        assert resp.status == 201
        body = json.loads(resp.read())
        assert "note" in body
        conn.close()

    def test_post_notes_empty_name_returns_400(self, running_server):
        server, port = running_server
        payload = json.dumps({
            "mode": "diff", "feature_id": "feat-x",
            "version_a": "v1", "version_b": "v2",
            "name_input": "", "comment": "msg",
        }).encode()
        conn = HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("POST", "/api/notes", body=payload,
                     headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        assert resp.status == 400
        conn.close()


class TestDiffExplanationRouting:
    def test_get_diff_explanation_returns_200(self, running_server):
        server, port = running_server
        conn = HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request(
            "GET",
            "/api/diff-explanations/feat-x"
            "?baseline_version_id=v1&current_version_id=v2&output_language=zh-Hant",
        )
        resp = conn.getresponse()
        assert resp.status == 200
        body = json.loads(resp.read())
        assert "explanation" in body
        conn.close()

    def test_get_diff_explanation_missing_params_returns_400(self, running_server):
        server, port = running_server
        conn = HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", "/api/diff-explanations/feat-x?baseline_version_id=v1")
        resp = conn.getresponse()
        assert resp.status == 400
        conn.close()

    def test_get_diff_explanation_unknown_path_returns_404(self, running_server):
        server, port = running_server
        conn = HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", "/api/diff-explanations/")
        resp = conn.getresponse()
        # No feature_id segment — should 400 or 404
        assert resp.status in (400, 404)
        conn.close()
