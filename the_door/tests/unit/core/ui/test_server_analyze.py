"""Tests for /api/analyze route registration."""
from __future__ import annotations
import json
import socket
import threading
import time
from http.client import HTTPConnection
from pathlib import Path
from unittest.mock import patch
import pytest


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def running_server(tmp_path):
    viewer_dir = tmp_path / "viewer"
    viewer_dir.mkdir()
    (viewer_dir / "index.html").write_text("<html></html>", encoding="utf-8")

    from the_door.core.ui.server import UIServer
    port = _find_free_port()
    server = UIServer(project_root=tmp_path, viewer_dir=viewer_dir, port=port)
    thread = threading.Thread(target=server.start, daemon=True)
    thread.start()
    for _ in range(20):
        try:
            conn = HTTPConnection("127.0.0.1", port, timeout=1)
            conn.request("GET", "/api/status")
            conn.getresponse().read()
            conn.close()
            break
        except Exception:
            time.sleep(0.05)
    yield port
    server.shutdown()


def test_post_api_analyze_returns_202(running_server):
    port = running_server
    with patch("the_door.core.ui.api.handlers.analysis.AnalysisHandlers._run_analyze_job"):
        conn = HTTPConnection("127.0.0.1", port)
        body = json.dumps({}).encode()
        conn.request("POST", "/api/analyze", body=body,
                     headers={"Content-Type": "application/json", "Content-Length": str(len(body))})
        resp = conn.getresponse()
        data = json.loads(resp.read())
        conn.close()
    assert resp.status == 202
    assert "job_id" in data


def test_get_api_analyze_returns_405(running_server):
    port = running_server
    conn = HTTPConnection("127.0.0.1", port)
    conn.request("GET", "/api/analyze")
    resp = conn.getresponse()
    resp.read()
    conn.close()
    assert resp.status == 405
