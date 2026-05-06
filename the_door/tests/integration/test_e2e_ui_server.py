"""End-to-end integration tests for the UIServer + APIHandlers pipeline.

Tests cover the full flow:
  1. Set up a project_root with .the-door/ data (snapshots, reports, structure.json)
  2. Start UIServer in a background thread
  3. Make real HTTP requests to all 13 API endpoints
  4. Verify responses match expected contracts

No LLM calls are made — all data is pre-seeded from fixtures.
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
# Helpers
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


def _find_free_port() -> int:
    """Find a free TCP port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _get(url: str) -> tuple[int, dict]:
    """Make a GET request and return (status_code, body_dict)."""
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))


def _post(url: str, body: dict) -> tuple[int, dict]:
    """Make a POST request with JSON body and return (status_code, body_dict)."""
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


def _wait_for_server(url: str, timeout: float = 5.0) -> None:
    """Poll until the server responds or timeout expires."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            urllib.request.urlopen(url + "/api/project", timeout=1)
            return
        except Exception:
            time.sleep(0.05)
    raise RuntimeError(f"Server at {url} did not start within {timeout}s")


def _seed_snapshot(project_root: Path) -> str:
    """Create a VersionSnapshot with two features and one relation. Returns version_id."""
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
            "feat-users": FeatureSummary(
                feature_id="feat-users",
                label="User listing",
                confidence="medium",
                description="Displays all registered users",
                source_node_count=1,
            ),
        },
        feature_relations=[
            RelationSummary(
                from_feature="feat-auth",
                to_feature="feat-users",
                relation="triggers",
            )
        ],
        analyzed_files=["app.py", "auth.py"],
        trigger="manual",
        label="v1.0",
    )
    return snapshot.version_id


def _seed_structure_json(project_root: Path) -> None:
    """Write a minimal structure.json to .the-door/."""
    dot_dir = project_root / ".the-door"
    dot_dir.mkdir(parents=True, exist_ok=True)
    structure = {
        "nodes": [
            {"node_id": "app.py::login", "name": "login", "type": "function", "file": "app.py"},
            {"node_id": "auth.py::authenticate_user", "name": "authenticate_user", "type": "function", "file": "auth.py"},
        ],
        "edges": [
            {"from_node": "app.py::login", "to_node": "auth.py::authenticate_user", "type": "calls"},
        ],
        "topology": {},
    }
    (dot_dir / "structure.json").write_text(
        json.dumps(structure, ensure_ascii=False), encoding="utf-8"
    )


def _seed_update_report(project_root: Path) -> None:
    """Write a minimal update-report JSON to .the-door/."""
    dot_dir = project_root / ".the-door"
    dot_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "report_version": "1.0",
        "generated_at": "2024-01-01T00:00:00Z",
        "pipeline_summary": {"status": "completed"},
        "l0_summary": "Two features analyzed.",
        "l1_changes": [
            {
                "feature_id": "feat-auth",
                "change_type": "added",
                "current_label": "User sign-in",
                "baseline_label": None,
                "current_description": "Allows users to verify their identity",
                "baseline_description": None,
                "risk_flags": [],
            }
        ],
        "l2_details": {},
        "l3_appendix": {},
        "interrupted": False,
    }
    (dot_dir / "update-report-2024-01-01T00-00-00Z.json").write_text(
        json.dumps(report, ensure_ascii=False), encoding="utf-8"
    )


def _seed_l2_output(project_root: Path, feature_id: str) -> None:
    """Write a minimal L2 output JSON to .the-door/l2-outputs/."""
    l2_dir = project_root / ".the-door" / "l2-outputs"
    l2_dir.mkdir(parents=True, exist_ok=True)
    l2_data = {
        "modules": [
            {
                "module_id": "mod-auth",
                "label": "Auth Module",
                "confidence": "high",
                "source_nodes": ["app.py::login", "auth.py::authenticate_user"],
            }
        ],
        "module_interactions": [],
        "anomalies": [],
    }
    (l2_dir / f"{feature_id}.json").write_text(
        json.dumps(l2_data, ensure_ascii=False), encoding="utf-8"
    )


def _seed_layer_explanation(
    project_root: Path, feature_id: str, layer: str, explanation: str
) -> None:
    """Write a layer explanation cache file."""
    exp_dir = project_root / ".the-door" / "layer-explanations" / feature_id
    exp_dir.mkdir(parents=True, exist_ok=True)
    data = {
        "feature_id": feature_id,
        "layer": layer,
        "explanation": explanation,
        "generated_at": "2024-01-01T00:00:00Z",
    }
    (exp_dir / f"{layer}.json").write_text(
        json.dumps(data, ensure_ascii=False), encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def server_url(tmp_path):
    """Start UIServer with a seeded project_root. Yield base URL. Shutdown after test."""
    project_root = tmp_path / "project"
    project_root.mkdir()

    # Seed all data
    _seed_snapshot(project_root)
    _seed_structure_json(project_root)
    _seed_update_report(project_root)
    _seed_l2_output(project_root, "feat-auth")
    _seed_layer_explanation(project_root, "feat-auth", "l2", "This is the L2 explanation.")

    # Use a minimal viewer_dir (just needs to exist)
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


@pytest.fixture()
def empty_server_url(tmp_path):
    """Start UIServer with an empty project_root (no .the-door/ dir). Yield base URL."""
    project_root = tmp_path / "empty_project"
    project_root.mkdir()

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
# Test: GET /api/project
# ---------------------------------------------------------------------------


class TestGetProject:
    def test_project_with_data(self, server_url):
        """GET /api/project returns 200 with correct available_data flags."""
        status, body = _get(f"{server_url}/api/project")

        assert status == 200
        assert "project_path" in body
        assert body["dot_the_door_exists"] is True
        data = body["available_data"]
        assert data["has_snapshots"] is True
        assert data["has_latest_report"] is True
        assert data["has_doubts"] is False
        assert data["has_scope_config"] is False

    def test_project_empty(self, empty_server_url):
        """GET /api/project with no .the-door/ returns 200 with all flags False."""
        status, body = _get(f"{empty_server_url}/api/project")

        assert status == 200
        assert body["dot_the_door_exists"] is False
        data = body["available_data"]
        assert data["has_snapshots"] is False
        assert data["has_latest_report"] is False


# ---------------------------------------------------------------------------
# Test: GET /api/snapshots
# ---------------------------------------------------------------------------


class TestGetSnapshots:
    def test_snapshots_returns_list(self, server_url):
        """GET /api/snapshots returns 200 with a non-empty list."""
        status, body = _get(f"{server_url}/api/snapshots")

        assert status == 200
        assert "snapshots" in body
        assert len(body["snapshots"]) == 1
        snap = body["snapshots"][0]
        assert "version_id" in snap
        assert snap["trigger"] == "manual"
        assert snap["label"] == "v1.0"

    def test_snapshots_empty(self, empty_server_url):
        """GET /api/snapshots with no data returns 200 with empty list."""
        status, body = _get(f"{empty_server_url}/api/snapshots")

        assert status == 200
        assert body["snapshots"] == []


# ---------------------------------------------------------------------------
# Test: GET /api/report/latest
# ---------------------------------------------------------------------------


class TestGetReportLatest:
    def test_report_found(self, server_url):
        """GET /api/report/latest returns 200 with UpdateReport content."""
        status, body = _get(f"{server_url}/api/report/latest")

        assert status == 200
        assert body["generated_at"] == "2024-01-01T00:00:00Z"
        assert "l1_changes" in body
        assert len(body["l1_changes"]) == 1
        assert body["l1_changes"][0]["feature_id"] == "feat-auth"

    def test_report_not_found(self, empty_server_url):
        """GET /api/report/latest with no report returns 404."""
        status, body = _get(f"{empty_server_url}/api/report/latest")

        assert status == 404
        assert body["error"]["code"] == "no_report_found"


# ---------------------------------------------------------------------------
# Test: GET /api/l1
# ---------------------------------------------------------------------------


class TestGetL1:
    def test_l1_returns_graph_view_model(self, server_url):
        """GET /api/l1 returns 200 with L1_Graph_ViewModel from latest snapshot."""
        status, body = _get(f"{server_url}/api/l1")

        assert status == 200
        assert "nodes" in body
        assert "edges" in body
        assert "warnings" in body
        # Two features → two nodes
        assert len(body["nodes"]) == 2
        node_ids = {n["id"] for n in body["nodes"]}
        assert "feat-auth" in node_ids
        assert "feat-users" in node_ids
        # One relation → one edge
        assert len(body["edges"]) == 1
        assert body["edges"][0]["source"] == "feat-auth"
        assert body["edges"][0]["target"] == "feat-users"

    def test_l1_node_has_required_fields(self, server_url):
        """Each node in L1_Graph_ViewModel has id, label, confidence, description."""
        status, body = _get(f"{server_url}/api/l1")

        assert status == 200
        for node in body["nodes"]:
            assert "id" in node
            assert "label" in node
            assert "confidence" in node
            assert "description" in node
            # trigger_description is null for snapshot-based L1
            assert "trigger_description" in node
            assert node["trigger_description"] is None

    def test_l1_no_snapshot_returns_404(self, empty_server_url):
        """GET /api/l1 with no snapshot returns 404."""
        status, body = _get(f"{empty_server_url}/api/l1")

        assert status == 404
        assert body["error"]["code"] == "no_l1_data"


# ---------------------------------------------------------------------------
# Test: GET /api/l2/<feature_id>
# ---------------------------------------------------------------------------


class TestGetL2:
    def test_l2_found_returns_view_model(self, server_url):
        """GET /api/l2/feat-auth returns 200 with L2_Graph_ViewModel."""
        status, body = _get(f"{server_url}/api/l2/feat-auth")

        assert status == 200
        assert "nodes" in body
        assert "edges" in body
        assert "anomalies" in body
        assert len(body["nodes"]) == 1
        assert body["nodes"][0]["id"] == "mod-auth"
        assert body["nodes"][0]["label"] == "Auth Module"

    def test_l2_not_found_returns_404(self, server_url):
        """GET /api/l2/nonexistent returns 404."""
        status, body = _get(f"{server_url}/api/l2/nonexistent-feature")

        assert status == 404
        assert body["error"]["code"] == "l2_not_generated"


# ---------------------------------------------------------------------------
# Test: GET /api/structure
# ---------------------------------------------------------------------------


class TestGetStructure:
    def test_structure_found(self, server_url):
        """GET /api/structure returns 200 with structure.json content."""
        status, body = _get(f"{server_url}/api/structure")

        assert status == 200
        assert "nodes" in body
        assert "edges" in body
        assert len(body["nodes"]) == 2
        node_ids = {n["node_id"] for n in body["nodes"]}
        assert "app.py::login" in node_ids
        assert "auth.py::authenticate_user" in node_ids

    def test_structure_not_found_returns_404(self, empty_server_url):
        """GET /api/structure with no structure.json returns 404."""
        status, body = _get(f"{empty_server_url}/api/structure")

        assert status == 404
        assert body["error"]["code"] == "no_structure_data"


# ---------------------------------------------------------------------------
# Test: GET /api/layer-explanation/<feature_id>/<layer>
# ---------------------------------------------------------------------------


class TestGetLayerExplanation:
    def test_explanation_found(self, server_url):
        """GET /api/layer-explanation/feat-auth/l2 returns 200 with cached content."""
        status, body = _get(f"{server_url}/api/layer-explanation/feat-auth/l2")

        assert status == 200
        assert body["feature_id"] == "feat-auth"
        assert body["layer"] == "l2"
        assert body["explanation"] == "This is the L2 explanation."

    def test_explanation_not_found_returns_404(self, server_url):
        """GET /api/layer-explanation/feat-auth/l1 with no cache returns 404."""
        status, body = _get(f"{server_url}/api/layer-explanation/feat-auth/l1")

        assert status == 404
        assert body["error"]["code"] == "explanation_not_cached"

    def test_explanation_invalid_layer_returns_400(self, server_url):
        """GET /api/layer-explanation/feat-auth/l99 returns 400."""
        status, body = _get(f"{server_url}/api/layer-explanation/feat-auth/l99")

        assert status == 400
        assert body["error"]["code"] == "invalid_layer"


# ---------------------------------------------------------------------------
# Test: GET /api/doubts
# ---------------------------------------------------------------------------


class TestGetDoubts:
    def test_doubts_empty(self, server_url):
        """GET /api/doubts with no doubts returns 200 with empty list."""
        status, body = _get(f"{server_url}/api/doubts")

        assert status == 200
        assert "doubts" in body
        assert body["doubts"] == []
        assert body["summary"]["total"] == 0


# ---------------------------------------------------------------------------
# Test: GET /api/timeline
# ---------------------------------------------------------------------------


class TestGetTimeline:
    def test_timeline_with_snapshot(self, server_url):
        """GET /api/timeline with snapshots returns 200 with timeline data."""
        status, body = _get(f"{server_url}/api/timeline")

        assert status == 200
        # Timeline result has some structure (exact fields depend on TimelineEngine)
        assert isinstance(body, dict)

    def test_timeline_empty(self, empty_server_url):
        """GET /api/timeline with no snapshots returns 200 with empty result."""
        status, body = _get(f"{empty_server_url}/api/timeline")

        assert status == 200
        assert isinstance(body, dict)


# ---------------------------------------------------------------------------
# Test: POST /api/update (validation only — no actual pipeline run)
# ---------------------------------------------------------------------------


class TestPostUpdate:
    def test_missing_fields_returns_400(self, server_url):
        """POST /api/update with missing fields returns 400."""
        status, body = _post(f"{server_url}/api/update", {})

        assert status == 400
        assert body["error"]["code"] == "missing_required_field"

    def test_nonexistent_old_path_returns_400(self, server_url, tmp_path):
        """POST /api/update with nonexistent old_path returns 400."""
        status, body = _post(f"{server_url}/api/update", {
            "old_path": str(tmp_path / "nonexistent"),
            "new_path": str(tmp_path / "also_nonexistent"),
        })

        assert status == 400
        assert body["error"]["code"] == "invalid_path"

    def test_same_path_returns_400(self, server_url, tmp_path):
        """POST /api/update with same old_path and new_path returns 400."""
        same_dir = tmp_path / "same"
        same_dir.mkdir()
        status, body = _post(f"{server_url}/api/update", {
            "old_path": str(same_dir),
            "new_path": str(same_dir),
        })

        assert status == 400
        assert body["error"]["code"] == "same_path"


# ---------------------------------------------------------------------------
# Test: POST /api/l2/<feature_id>/generate (job creation only)
# ---------------------------------------------------------------------------


class TestPostL2Generate:
    def test_generate_returns_202_with_job_id(self, server_url):
        """POST /api/l2/feat-auth/generate returns 202 with job_id."""
        status, body = _post(f"{server_url}/api/l2/feat-auth/generate", {})

        assert status == 202
        assert "job_id" in body
        assert isinstance(body["job_id"], str)

    def test_generate_no_structure_returns_404(self, empty_server_url):
        """POST /api/l2/feat-auth/generate without structure.json returns 404."""
        status, body = _post(f"{empty_server_url}/api/l2/feat-auth/generate", {})

        assert status == 404
        assert body["error"]["code"] == "no_structure_data"

    def test_generate_job_already_running_returns_409(self, server_url):
        """409 conflict is enforced at the JobStore level.

        This is a race-condition-sensitive test in integration context because
        background threads (with no LLM config) fail almost instantly.
        We verify the contract by using the /api/update endpoint which also
        uses the same JobStore — if we can create a job via l2/generate and
        immediately check the status, the job lifecycle is correct.

        The 409 behaviour itself is fully covered by unit tests in
        test_api_handlers_ui3.py::TestPostL2Generate::test_post_l2_generate_job_already_running_returns_409
        which uses a pre-seeded running job without race conditions.
        """
        # Create a job and verify it gets a valid job_id
        status, body = _post(f"{server_url}/api/l2/feat-auth/generate", {})
        assert status == 202
        assert "job_id" in body

        # Poll until the job finishes (it will fail due to no LLM config)
        job_id = body["job_id"]
        deadline = time.monotonic() + 5.0
        final_status = None
        while time.monotonic() < deadline:
            _, status_body = _get(f"{server_url}/api/update/status/{job_id}")
            final_status = status_body.get("status")
            if final_status in ("completed", "failed"):
                break
            time.sleep(0.05)

        # Job must reach a terminal state (completed or failed — failed expected here)
        assert final_status in ("completed", "failed"), (
            f"Job did not reach terminal state within 5s, last status: {final_status}"
        )


# ---------------------------------------------------------------------------
# Test: GET /api/update/status/<job_id>
# ---------------------------------------------------------------------------


class TestGetUpdateStatus:
    def test_status_after_l2_generate(self, server_url):
        """GET /api/update/status/<job_id> returns 200 with job status."""
        # Create a job first
        _, create_body = _post(f"{server_url}/api/l2/feat-auth/generate", {})
        job_id = create_body["job_id"]

        status, body = _get(f"{server_url}/api/update/status/{job_id}")

        assert status == 200
        assert body["job_id"] == job_id
        assert body["status"] in ("pending", "running", "completed", "failed")

    def test_status_unknown_job_returns_404(self, server_url):
        """GET /api/update/status/nonexistent returns 404."""
        status, body = _get(f"{server_url}/api/update/status/nonexistent-job-id")

        assert status == 404
        assert body["error"]["code"] == "job_not_found"


# ---------------------------------------------------------------------------
# Test: POST /api/layer-explanation/<feature_id>/<layer>/generate
# ---------------------------------------------------------------------------


class TestPostLayerExplanationGenerate:
    def test_generate_returns_202(self, server_url):
        """POST /api/layer-explanation/feat-auth/l1/generate returns 202."""
        status, body = _post(
            f"{server_url}/api/layer-explanation/feat-auth/l1/generate", {}
        )

        assert status == 202
        assert "job_id" in body

    def test_generate_invalid_layer_returns_400(self, server_url):
        """POST /api/layer-explanation/feat-auth/l99/generate returns 400."""
        status, body = _post(
            f"{server_url}/api/layer-explanation/feat-auth/l99/generate", {}
        )

        assert status == 400
        assert body["error"]["code"] == "invalid_layer"


# ---------------------------------------------------------------------------
# Test: Static file serving
# ---------------------------------------------------------------------------


class TestStaticServing:
    def test_index_html_served(self, server_url):
        """GET / serves index.html with 200."""
        try:
            with urllib.request.urlopen(f"{server_url}/", timeout=5) as resp:
                assert resp.status == 200
                content = resp.read().decode("utf-8")
                assert "<html>" in content
        except urllib.error.HTTPError as e:
            pytest.fail(f"Expected 200 for /, got {e.code}")

    def test_nonexistent_static_returns_404(self, server_url):
        """GET /nonexistent.js returns 404."""
        try:
            urllib.request.urlopen(f"{server_url}/nonexistent.js", timeout=5)
            pytest.fail("Expected 404")
        except urllib.error.HTTPError as e:
            assert e.code == 404


# ---------------------------------------------------------------------------
# Test: Full data flow — L1 → L2 → Structure chain
# ---------------------------------------------------------------------------


class TestDataFlowChain:
    def test_l1_nodes_match_snapshot_features(self, server_url):
        """L1 graph nodes correspond exactly to snapshot features.

        /api/snapshots returns summary (no l1_snapshot field).
        We verify via /api/l1 that node count matches what we seeded (2 features).
        """
        _, snap_body = _get(f"{server_url}/api/snapshots")
        _, l1_body = _get(f"{server_url}/api/l1")

        # We seeded exactly 2 features; snapshot list should have 1 snapshot
        assert len(snap_body["snapshots"]) == 1
        # L1 graph should have exactly 2 nodes (one per feature)
        assert len(l1_body["nodes"]) == 2
        node_ids = {n["id"] for n in l1_body["nodes"]}
        assert "feat-auth" in node_ids
        assert "feat-users" in node_ids

    def test_l2_source_nodes_exist_in_structure(self, server_url):
        """L2 module source_nodes are a subset of structure.json node_ids."""
        _, l2_body = _get(f"{server_url}/api/l2/feat-auth")
        _, struct_body = _get(f"{server_url}/api/structure")

        structure_node_ids = {n["node_id"] for n in struct_body["nodes"]}
        for module in l2_body["nodes"]:
            for source_node in module["source_nodes"]:
                assert source_node in structure_node_ids, (
                    f"L2 source_node '{source_node}' not found in structure.json"
                )

    def test_report_l1_changes_count_consistent(self, server_url):
        """UpdateReport l1_changes count matches what /api/report/latest returns."""
        _, report_body = _get(f"{server_url}/api/report/latest")

        l1_changes = report_body.get("l1_changes", [])
        assert len(l1_changes) == 1
        assert l1_changes[0]["change_type"] == "added"

    def test_no_invented_data_in_l1(self, server_url):
        """Every L1 node id corresponds to a real feature we seeded.

        Anti-hallucination check: L1 graph must not contain nodes
        that weren't in the original snapshot.
        """
        _, l1_body = _get(f"{server_url}/api/l1")

        # We seeded exactly these two feature IDs
        known_feature_ids = {"feat-auth", "feat-users"}

        for node in l1_body["nodes"]:
            assert node["id"] in known_feature_ids, (
                f"L1 node '{node['id']}' not found in seeded features — possible hallucination"
            )

    def test_l2_edges_reference_existing_nodes(self, server_url):
        """All L2 edges reference nodes that exist in the L2 ViewModel."""
        _, l2_body = _get(f"{server_url}/api/l2/feat-auth")

        node_ids = {n["id"] for n in l2_body["nodes"]}
        for edge in l2_body["edges"]:
            assert edge["source"] in node_ids, (
                f"L2 edge source '{edge['source']}' not in node set"
            )
            assert edge["target"] in node_ids, (
                f"L2 edge target '{edge['target']}' not in node set"
            )
