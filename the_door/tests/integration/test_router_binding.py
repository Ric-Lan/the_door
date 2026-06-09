"""Router binding safety net — pins current HTTP path→response shape for 8 endpoints
not covered by test_e2e_ui_server.py.

These tests run against the CURRENT server and MUST be GREEN immediately.
They are a baseline, not TDD.  Do NOT change the server to fix a red test here;
fix the assertion instead so it matches the actual response.

Endpoints covered:
  POST /api/analyze
  POST /api/set-project
  GET  /api/status
  GET  /api/diff
  GET  /api/diff-explanations/<fid>
  POST /api/diff-explanations/<fid>/generate
  GET  /api/notes
  POST /api/notes
"""
from __future__ import annotations

import json
import socket
import threading
import time
import urllib.request
import urllib.error
from pathlib import Path

import pytest

from the_door.core.diff.snapshot_store import SnapshotStore
from the_door.core.ui.server import UIServer
from the_door.models import FeatureSummary, RelationSummary


# ---------------------------------------------------------------------------
# Helpers — reused verbatim from test_e2e_ui_server.py
# ---------------------------------------------------------------------------


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _get(url: str) -> tuple[int, dict]:
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))


def _post(url: str, body: dict) -> tuple[int, dict]:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))


def _post_raw(url: str, raw_bytes: bytes) -> tuple[int, dict]:
    """POST raw bytes (e.g. invalid JSON) and return (status, body_dict)."""
    req = urllib.request.Request(
        url,
        data=raw_bytes,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))


def _wait_for_server(url: str, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            urllib.request.urlopen(url + "/api/project", timeout=1)
            return
        except Exception:
            time.sleep(0.05)
    raise RuntimeError(f"Server at {url} did not start within {timeout}s")


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------


def _seed_snapshot(project_root: Path) -> str:
    store = SnapshotStore(project_root)
    snapshot = store.create_snapshot(
        l1_snapshot={
            "feat-auth": FeatureSummary(
                feature_id="feat-auth",
                label="User sign-in",
                confidence="high",
                description="Allows users to verify their identity",
                source_node_count=3,
            ),
        },
        feature_relations=[],
        analyzed_files=["app.py"],
        trigger="manual",
        label="v1.0",
    )
    return snapshot.version_id


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def server_url(tmp_path):
    """Start UIServer with a seeded project_root. Yield base URL. Shutdown after."""
    project_root = tmp_path / "project"
    project_root.mkdir()
    _seed_snapshot(project_root)

    viewer_dir = tmp_path / "viewer"
    viewer_dir.mkdir()
    (viewer_dir / "index.html").write_text("<html></html>", encoding="utf-8")

    port = _find_free_port()
    server = UIServer(project_root=project_root, viewer_dir=viewer_dir, port=port)
    thread = threading.Thread(target=server.start, daemon=True)
    thread.start()

    base_url = f"http://127.0.0.1:{port}"
    _wait_for_server(base_url)
    yield base_url
    server.shutdown()



# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestGetStatus:
    """GET /api/status"""

    def test_returns_200_with_state_key(self, server_url):
        status, body = _get(f"{server_url}/api/status")
        assert status == 200
        assert "state" in body

    def test_returns_200_with_next_actions_key(self, server_url):
        status, body = _get(f"{server_url}/api/status")
        assert status == 200
        assert "next_actions" in body


class TestGetDiff:
    """GET /api/diff"""

    def test_missing_params_returns_400(self, server_url):
        # No query params → missing_params error
        status, body = _get(f"{server_url}/api/diff")
        assert status == 400
        assert body["error"]["code"] == "missing_params"

    def test_missing_current_param_returns_400(self, server_url):
        status, body = _get(f"{server_url}/api/diff?baseline=v1.0")
        assert status == 400
        assert body["error"]["code"] == "missing_params"


# TestPostAnalyze removed in T5-A: POST /api/analyze (key-bound analysis job) retired.


class TestPostSetProject:
    """POST /api/set-project"""

    def test_invalid_json_returns_400(self, server_url):
        status, body = _post_raw(f"{server_url}/api/set-project", b"{bad json")
        assert status == 400
        assert body["error"]["code"] == "invalid_json"

    def test_missing_path_returns_400(self, server_url):
        status, body = _post(f"{server_url}/api/set-project", {})
        assert status == 400
        # Server returns {"status": "error", "message": ...} (not the standard error envelope)
        # TODO(api-handlers-split): non-standard envelope — normalize during refactor
        assert body["status"] == "error"

    def test_nonexistent_path_returns_400(self, server_url):
        status, body = _post(
            f"{server_url}/api/set-project",
            {"path": "/no/such/directory/ever"},
        )
        assert status == 400
        assert body["status"] == "error"

    def test_valid_path_returns_200_switched(self, server_url, tmp_path):
        # tmp_path itself exists and is readable
        new_dir = tmp_path / "other_project"
        new_dir.mkdir()
        status, body = _post(
            f"{server_url}/api/set-project",
            {"path": str(new_dir)},
        )
        assert status == 200
        assert body["status"] == "switched"


class TestGetDiffExplanations:
    """GET /api/diff-explanations/<fid>"""

    def test_missing_query_params_returns_400(self, server_url):
        status, body = _get(f"{server_url}/api/diff-explanations/feat-auth")
        assert status == 400
        assert body["error"]["code"] == "missing_params"

    def test_all_params_present_returns_200_with_explanation_key(self, server_url):
        url = (
            f"{server_url}/api/diff-explanations/feat-auth"
            "?baseline_version_id=vid-a&current_version_id=vid-b&output_language=zh-Hant"
        )
        status, body = _get(url)
        assert status == 200
        assert "explanation" in body


class TestPostDiffExplanationsGenerateRetired:
    """POST /api/diff-explanations/<fid>/generate was retired in T5-V (丙案 D1).

    The generation endpoint no longer exists; the path must not match any route.
    The GET read/display path remains (see TestGetDiffExplanations).
    """

    def test_generate_route_removed_returns_404(self, server_url):
        # Route removed → the path matches no route; server returns 404 not_found.
        status, body = _post(
            f"{server_url}/api/diff-explanations/feat-auth/generate",
            {
                "baseline_version_id": "vid-a",
                "current_version_id": "vid-b",
                "output_language": "zh-Hant",
            },
        )
        assert status == 404
        assert body["error"]["code"] == "not_found"


class TestGetNotes:
    """GET /api/notes"""

    def test_missing_mode_and_feature_id_returns_400(self, server_url):
        status, body = _get(f"{server_url}/api/notes")
        assert status == 400
        assert body["error"]["code"] == "missing_params"

    def test_invalid_mode_returns_400(self, server_url):
        status, body = _get(
            f"{server_url}/api/notes?mode=bogus&feature_id=feat-auth"
        )
        assert status == 400
        assert body["error"]["code"] == "invalid_mode"

    def test_current_mode_missing_version_b_returns_400(self, server_url):
        status, body = _get(
            f"{server_url}/api/notes?mode=current&feature_id=feat-auth"
        )
        assert status == 400
        assert body["error"]["code"] == "missing_params"

    def test_current_mode_with_version_b_returns_200_notes_list(self, server_url):
        status, body = _get(
            f"{server_url}/api/notes"
            "?mode=current&feature_id=feat-auth&version_b=v1.0"
        )
        assert status == 200
        assert "notes" in body
        assert isinstance(body["notes"], list)


class TestPostNotes:
    """POST /api/notes"""

    def test_missing_mode_and_feature_id_returns_400(self, server_url):
        status, body = _post(f"{server_url}/api/notes", {})
        assert status == 400
        assert body["error"]["code"] == "missing_params"

    def test_invalid_json_returns_400(self, server_url):
        status, body = _post_raw(f"{server_url}/api/notes", b"{bad")
        assert status == 400
        assert body["error"]["code"] == "invalid_json"

    def test_valid_note_roundtrip(self, server_url):
        # POST a note then GET it back
        post_status, post_body = _post(
            f"{server_url}/api/notes",
            {
                "mode": "current",
                "feature_id": "feat-auth",
                "version_b": "v1.0",
                "name_input": "Reviewer",
                "comment": "Looks good to me.",
            },
        )
        assert post_status in (200, 201)
        # Response shape: {"note": {...}} with the persisted note object
        assert "note" in post_body

        # GET back the note
        get_status, get_body = _get(
            f"{server_url}/api/notes"
            "?mode=current&feature_id=feat-auth&version_b=v1.0"
        )
        assert get_status == 200
        assert "notes" in get_body
        notes = get_body["notes"]
        assert any(n.get("comment") == "Looks good to me." for n in notes)
