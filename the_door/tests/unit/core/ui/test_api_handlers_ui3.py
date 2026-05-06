"""Unit tests for APIHandlers — Phase UI-3 new endpoints (6 handlers).

Tests cover:
- handle_get_l1
- handle_get_l2
- handle_post_l2_generate
- handle_get_layer_explanation
- handle_post_layer_explanation_generate
- handle_get_structure
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from the_door.core.ui.api_handlers import APIHandlers
from the_door.core.ui.job_store import JobStore
from the_door.models import (
    Anomaly,
    L2Module,
    L2Output,
    ModuleInteraction,
    VersionSnapshot,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_handlers(tmp_path: Path) -> APIHandlers:
    job_store = JobStore()
    return APIHandlers(project_root=tmp_path, job_store=job_store)


def _make_snapshot_with_l1(
    version_id: str = "v1",
    timestamp: str = "2024-01-01T00:00:00Z",
) -> VersionSnapshot:
    """Create a VersionSnapshot with l1_snapshot and feature_relations_snapshot."""
    from the_door.models import FeatureSummary, RelationSummary

    l1_snapshot = {
        "feat-1": FeatureSummary(
            feature_id="feat-1",
            label="Feature One",
            confidence="high",
            description="First feature",
            source_node_count=3,
        ),
        "feat-2": FeatureSummary(
            feature_id="feat-2",
            label="Feature Two",
            confidence="medium",
            description="Second feature",
            source_node_count=2,
        ),
    }
    feature_relations_snapshot = [
        RelationSummary(
            from_feature="feat-1",
            to_feature="feat-2",
            relation="calls",
        )
    ]
    return VersionSnapshot(
        version_id=version_id,
        timestamp=timestamp,
        trigger="manual",
        label=None,
        git_tags=[],
        l1_snapshot=l1_snapshot,
        feature_relations_snapshot=feature_relations_snapshot,
    )


def _make_l2_output() -> L2Output:
    return L2Output(
        modules=[
            L2Module(
                module_id="mod-1",
                label="Module One",
                confidence="high",
                source_nodes=["node-1", "node-2"],
            )
        ],
        module_interactions=[],
        anomalies=[],
    )


def _write_l2_output(tmp_path: Path, feature_id: str, l2_output: L2Output) -> None:
    """Write L2Output JSON to .the-door/l2-outputs/<feature_id>.json."""
    output_dir = tmp_path / ".the-door" / "l2-outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    data = {
        "modules": [
            {
                "module_id": m.module_id,
                "label": m.label,
                "confidence": m.confidence,
                "source_nodes": list(m.source_nodes),
            }
            for m in l2_output.modules
        ],
        "module_interactions": [],
        "anomalies": [],
    }
    (output_dir / f"{feature_id}.json").write_text(
        json.dumps(data), encoding="utf-8"
    )


def _write_structure_json(tmp_path: Path) -> None:
    """Write a minimal structure.json to .the-door/structure.json."""
    dot_dir = tmp_path / ".the-door"
    dot_dir.mkdir(parents=True, exist_ok=True)
    structure = {
        "nodes": [{"node_id": "n1", "name": "func_a", "type": "function", "file": "a.py"}],
        "edges": [],
        "topology": {},
    }
    (dot_dir / "structure.json").write_text(json.dumps(structure), encoding="utf-8")


def _write_layer_explanation(
    tmp_path: Path, feature_id: str, layer: str, explanation: str = "Some explanation"
) -> None:
    """Write a layer explanation cache file."""
    exp_dir = tmp_path / ".the-door" / "layer-explanations" / feature_id
    exp_dir.mkdir(parents=True, exist_ok=True)
    data = {
        "feature_id": feature_id,
        "layer": layer,
        "explanation": explanation,
        "generated_at": "2024-01-01T00:00:00Z",
    }
    (exp_dir / f"{layer}.json").write_text(json.dumps(data), encoding="utf-8")


# ---------------------------------------------------------------------------
# GET /api/l1
# ---------------------------------------------------------------------------


class TestGetL1:
    def test_get_l1_returns_view_model(self, tmp_path):
        """GET /api/l1 with a valid snapshot returns 200 + L1_Graph_ViewModel."""
        handlers = _make_handlers(tmp_path)
        snapshot = _make_snapshot_with_l1()

        with patch("the_door.core.ui.api_handlers.SnapshotStore") as mock_ss:
            mock_ss.return_value.get_latest.return_value = snapshot
            status, body = handlers.handle_get_l1()

        assert status == 200
        assert "nodes" in body
        assert "edges" in body
        assert "warnings" in body
        # Two features → two nodes
        assert len(body["nodes"]) == 2
        node_ids = {n["id"] for n in body["nodes"]}
        assert "feat-1" in node_ids
        assert "feat-2" in node_ids
        # One relation → one edge
        assert len(body["edges"]) == 1
        assert body["edges"][0]["source"] == "feat-1"
        assert body["edges"][0]["target"] == "feat-2"

    def test_get_l1_no_snapshot_returns_404(self, tmp_path):
        """GET /api/l1 with no snapshot returns 404 code:'no_l1_data'."""
        handlers = _make_handlers(tmp_path)

        with patch("the_door.core.ui.api_handlers.SnapshotStore") as mock_ss:
            mock_ss.return_value.get_latest.return_value = None
            status, body = handlers.handle_get_l1()

        assert status == 404
        assert body["error"]["code"] == "no_l1_data"


# ---------------------------------------------------------------------------
# GET /api/l2/<feature_id>
# ---------------------------------------------------------------------------


class TestGetL2:
    def test_get_l2_found_returns_view_model(self, tmp_path):
        """GET /api/l2/<feature_id> with existing L2 data returns 200 + L2_Graph_ViewModel."""
        handlers = _make_handlers(tmp_path)
        l2_output = _make_l2_output()
        _write_l2_output(tmp_path, "feat-1", l2_output)

        status, body = handlers.handle_get_l2("feat-1")

        assert status == 200
        assert "nodes" in body
        assert "edges" in body
        assert "anomalies" in body
        assert len(body["nodes"]) == 1
        assert body["nodes"][0]["id"] == "mod-1"

    def test_get_l2_not_found_returns_404(self, tmp_path):
        """GET /api/l2/<feature_id> with no L2 data returns 404 code:'l2_not_generated'."""
        handlers = _make_handlers(tmp_path)

        status, body = handlers.handle_get_l2("nonexistent-feature")

        assert status == 404
        assert body["error"]["code"] == "l2_not_generated"


# ---------------------------------------------------------------------------
# POST /api/l2/<feature_id>/generate
# ---------------------------------------------------------------------------


class TestPostL2Generate:
    def test_post_l2_generate_returns_202(self, tmp_path):
        """POST /api/l2/<feature_id>/generate with structure.json returns 202 + job_id."""
        handlers = _make_handlers(tmp_path)
        _write_structure_json(tmp_path)

        with patch("threading.Thread") as mock_thread:
            mock_thread.return_value = MagicMock()
            status, body = handlers.handle_post_l2_generate("feat-1")

        assert status == 202
        assert "job_id" in body
        assert isinstance(body["job_id"], str)

    def test_post_l2_generate_no_structure_returns_404(self, tmp_path):
        """POST /api/l2/<feature_id>/generate without structure.json returns 404."""
        handlers = _make_handlers(tmp_path)
        # No structure.json written

        status, body = handlers.handle_post_l2_generate("feat-1")

        assert status == 404
        assert body["error"]["code"] == "no_structure_data"

    def test_post_l2_generate_job_already_running_returns_409(self, tmp_path):
        """POST /api/l2/<feature_id>/generate with running job returns 409."""
        _write_structure_json(tmp_path)
        job_store = JobStore()
        job_store.try_create_job()  # simulate running job
        handlers = APIHandlers(project_root=tmp_path, job_store=job_store)

        status, body = handlers.handle_post_l2_generate("feat-1")

        assert status == 409
        assert body["error"]["code"] == "job_already_running"


# ---------------------------------------------------------------------------
# GET /api/layer-explanation/<feature_id>/<layer>
# ---------------------------------------------------------------------------


class TestGetLayerExplanation:
    def test_get_layer_explanation_found(self, tmp_path):
        """GET /api/layer-explanation/<fid>/<layer> with cached file returns 200."""
        handlers = _make_handlers(tmp_path)
        _write_layer_explanation(tmp_path, "feat-1", "l2", "This is the L2 explanation.")

        status, body = handlers.handle_get_layer_explanation("feat-1", "l2")

        assert status == 200
        assert body["feature_id"] == "feat-1"
        assert body["layer"] == "l2"
        assert body["explanation"] == "This is the L2 explanation."

    def test_get_layer_explanation_not_found_returns_404(self, tmp_path):
        """GET /api/layer-explanation/<fid>/<layer> with no cache returns 404."""
        handlers = _make_handlers(tmp_path)

        status, body = handlers.handle_get_layer_explanation("feat-1", "l2")

        assert status == 404
        assert body["error"]["code"] == "explanation_not_cached"

    def test_get_layer_explanation_invalid_layer_returns_400(self, tmp_path):
        """GET /api/layer-explanation/<fid>/<layer> with invalid layer returns 400."""
        handlers = _make_handlers(tmp_path)

        status, body = handlers.handle_get_layer_explanation("feat-1", "l99")

        assert status == 400
        assert body["error"]["code"] == "invalid_layer"


# ---------------------------------------------------------------------------
# POST /api/layer-explanation/<feature_id>/<layer>/generate
# ---------------------------------------------------------------------------


class TestPostLayerExplanationGenerate:
    def test_post_layer_explanation_generate_returns_202(self, tmp_path):
        """POST /api/layer-explanation/<fid>/<layer>/generate returns 202 + job_id."""
        handlers = _make_handlers(tmp_path)

        with patch("threading.Thread") as mock_thread:
            mock_thread.return_value = MagicMock()
            status, body = handlers.handle_post_layer_explanation_generate("feat-1", "l2")

        assert status == 202
        assert "job_id" in body
        assert isinstance(body["job_id"], str)

    def test_post_layer_explanation_generate_job_running_returns_409(self, tmp_path):
        """POST /api/layer-explanation/<fid>/<layer>/generate with running job returns 409."""
        job_store = JobStore()
        job_store.try_create_job()  # simulate running job
        handlers = APIHandlers(project_root=tmp_path, job_store=job_store)

        status, body = handlers.handle_post_layer_explanation_generate("feat-1", "l2")

        assert status == 409
        assert body["error"]["code"] == "job_already_running"


# ---------------------------------------------------------------------------
# GET /api/structure
# ---------------------------------------------------------------------------


class TestGetStructure:
    def test_get_structure_found(self, tmp_path):
        """GET /api/structure with existing structure.json returns 200 + content."""
        handlers = _make_handlers(tmp_path)
        _write_structure_json(tmp_path)

        status, body = handlers.handle_get_structure()

        assert status == 200
        assert "nodes" in body
        assert "edges" in body

    def test_get_structure_not_found_returns_404(self, tmp_path):
        """GET /api/structure without structure.json returns 404 code:'no_structure_data'."""
        handlers = _make_handlers(tmp_path)

        status, body = handlers.handle_get_structure()

        assert status == 404
        assert body["error"]["code"] == "no_structure_data"


# ---------------------------------------------------------------------------
# Background thread methods — _run_l2_generate_job and _run_layer_explanation_job
# ---------------------------------------------------------------------------


class TestRunL2GenerateJob:
    def test_run_l2_generate_job_config_error_fails_job(self, tmp_path):
        """_run_l2_generate_job calls fail_job when ConfigManager.load() raises ConfigError."""
        from the_door.core.llm.config_manager import ConfigError
        from the_door.core.ui.job_store import JobStore

        job_store = JobStore()
        job = job_store.try_create_job()
        handlers = APIHandlers(project_root=tmp_path, job_store=job_store)

        with patch("the_door.core.ui.api_handlers.ConfigManager") as mock_cm:
            mock_cm.load.side_effect = ConfigError("no config")
            handlers._run_l2_generate_job(job, "feat-1", {"nodes": [], "edges": []})

        updated_job = job_store.get_job(job.job_id)
        assert updated_job.status == "failed"
        assert "Config error" in updated_job.error_message

    def test_run_l2_generate_job_l2_generation_error_fails_job(self, tmp_path):
        """_run_l2_generate_job calls fail_job when L2Generator.generate() raises L2GenerationError."""
        from unittest.mock import AsyncMock
        from the_door.core.ui.job_store import JobStore
        from the_door.core.ui.l2_generator import L2GenerationError

        job_store = JobStore()
        job = job_store.try_create_job()
        handlers = APIHandlers(project_root=tmp_path, job_store=job_store)

        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(side_effect=L2GenerationError("LLM failed"))

        with patch("the_door.core.ui.api_handlers.ConfigManager") as mock_cm, \
             patch("the_door.core.ui.api_handlers.create_provider", return_value=mock_provider):
            mock_cm.load.return_value = MagicMock()
            handlers._run_l2_generate_job(job, "feat-1", {"nodes": [], "edges": []})

        updated_job = job_store.get_job(job.job_id)
        assert updated_job.status == "failed"

    def test_run_l2_generate_job_success_completes_job(self, tmp_path):
        """_run_l2_generate_job calls complete_job on success."""
        from unittest.mock import AsyncMock
        from the_door.core.ui.job_store import JobStore

        job_store = JobStore()
        job = job_store.try_create_job()
        handlers = APIHandlers(project_root=tmp_path, job_store=job_store)

        valid_l2_json = json.dumps({
            "modules": [{"module_id": "m1", "label": "M1", "confidence": "high", "source_nodes": []}],
            "module_interactions": [],
            "anomalies": [],
        })
        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(return_value=valid_l2_json)

        with patch("the_door.core.ui.api_handlers.ConfigManager") as mock_cm, \
             patch("the_door.core.ui.api_handlers.create_provider", return_value=mock_provider):
            mock_cm.load.return_value = MagicMock()
            handlers._run_l2_generate_job(job, "feat-1", {"nodes": [], "edges": []})

        updated_job = job_store.get_job(job.job_id)
        assert updated_job.status == "completed"


class TestRunLayerExplanationJob:
    def test_run_layer_explanation_job_config_error_fails_job(self, tmp_path):
        """_run_layer_explanation_job calls fail_job when ConfigManager.load() raises ConfigError."""
        from the_door.core.llm.config_manager import ConfigError
        from the_door.core.ui.job_store import JobStore

        job_store = JobStore()
        job = job_store.try_create_job()
        handlers = APIHandlers(project_root=tmp_path, job_store=job_store)

        with patch("the_door.core.ui.api_handlers.ConfigManager") as mock_cm:
            mock_cm.load.side_effect = ConfigError("no config")
            handlers._run_layer_explanation_job(job, "feat-1", "l2")

        updated_job = job_store.get_job(job.job_id)
        assert updated_job.status == "failed"
        assert "Config error" in updated_job.error_message

    def test_run_layer_explanation_job_success_persists_and_completes(self, tmp_path):
        """_run_layer_explanation_job persists explanation and calls complete_job on success."""
        from unittest.mock import AsyncMock
        from the_door.core.ui.job_store import JobStore

        job_store = JobStore()
        job = job_store.try_create_job()
        handlers = APIHandlers(project_root=tmp_path, job_store=job_store)

        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(return_value="This is the L2 explanation.")

        with patch("the_door.core.ui.api_handlers.ConfigManager") as mock_cm, \
             patch("the_door.core.ui.api_handlers.create_provider", return_value=mock_provider):
            mock_cm.load.return_value = MagicMock()
            handlers._run_layer_explanation_job(job, "feat-1", "l2")

        updated_job = job_store.get_job(job.job_id)
        assert updated_job.status == "completed"

        cache_path = tmp_path / ".the-door" / "layer-explanations" / "feat-1" / "l2.json"
        assert cache_path.exists()
        data = json.loads(cache_path.read_text(encoding="utf-8"))
        assert data["explanation"] == "This is the L2 explanation."
        assert data["feature_id"] == "feat-1"
        assert data["layer"] == "l2"

    def test_run_layer_explanation_job_exception_fails_job(self, tmp_path):
        """_run_layer_explanation_job calls fail_job when LLM raises any exception."""
        from unittest.mock import AsyncMock
        from the_door.core.ui.job_store import JobStore

        job_store = JobStore()
        job = job_store.try_create_job()
        handlers = APIHandlers(project_root=tmp_path, job_store=job_store)

        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(side_effect=RuntimeError("LLM timeout"))

        with patch("the_door.core.ui.api_handlers.ConfigManager") as mock_cm, \
             patch("the_door.core.ui.api_handlers.create_provider", return_value=mock_provider):
            mock_cm.load.return_value = MagicMock()
            handlers._run_layer_explanation_job(job, "feat-1", "l2")

        updated_job = job_store.get_job(job.job_id)
        assert updated_job.status == "failed"


# ---------------------------------------------------------------------------
# Additional coverage tests for exception / error paths
# ---------------------------------------------------------------------------


class TestAdditionalCoveragePaths:
    # ── handle_get_report_latest: report_read_error (lines 136-137) ──────

    def test_get_report_latest_read_error_returns_500(self, tmp_path):
        """handle_get_report_latest returns 500 when file read raises OSError."""
        from unittest.mock import patch, MagicMock
        handlers = _make_handlers(tmp_path)

        # Create a fake report path that exists but raises on read
        dot_dir = tmp_path / ".the-door"
        dot_dir.mkdir()
        report_file = dot_dir / "update-report-2024-01-01T00-00-00Z.json"
        report_file.write_text('{"generated_at": "2024-01-01T00:00:00Z"}', encoding="utf-8")

        with patch.object(report_file.__class__, "read_text", side_effect=OSError("disk error")):
            # patch the path object returned by _find_latest_report_path
            with patch.object(handlers, "_find_latest_report_path", return_value=report_file):
                status, body = handlers.handle_get_report_latest()

        assert status == 500
        assert body["error"]["code"] == "report_read_error"

    # ── handle_post_update: new_path invalid (line 170) ──────────────────

    def test_post_update_new_path_invalid_returns_400(self, tmp_path):
        """handle_post_update returns 400 when new_path does not exist."""
        handlers = _make_handlers(tmp_path)
        old_dir = tmp_path / "old"
        old_dir.mkdir()

        status, body = handlers.handle_post_update({
            "old_path": str(old_dir),
            "new_path": str(tmp_path / "nonexistent"),
        })

        assert status == 400
        assert body["error"]["code"] == "invalid_path"

    # ── handle_post_update: new_path outside project_root (lines 188-189) ─

    def test_post_update_new_path_outside_root_returns_400(self, tmp_path):
        """handle_post_update returns 400 when new_path is outside project_root.

        Uses a nested project_root so old_path is inside but new_path is outside.
        """
        # project_root is a subdirectory of tmp_path
        project_root = tmp_path / "project"
        project_root.mkdir()
        old_dir = project_root / "old"
        old_dir.mkdir()
        # new_dir is a sibling of project_root — outside project_root
        new_dir = tmp_path / "new"
        new_dir.mkdir()

        job_store = JobStore()
        handlers = APIHandlers(project_root=project_root, job_store=job_store)

        status, body = handlers.handle_post_update({
            "old_path": str(old_dir),
            "new_path": str(new_dir),
        })

        assert status == 400
        assert body["error"]["code"] == "invalid_path"

    # ── handle_get_l1: 500 exception path (lines 320-321) ────────────────

    def test_get_l1_exception_returns_500(self, tmp_path):
        """handle_get_l1 returns 500 when SnapshotStore raises an unexpected exception."""
        handlers = _make_handlers(tmp_path)

        with patch("the_door.core.ui.api_handlers.SnapshotStore") as mock_ss:
            mock_ss.return_value.get_latest.side_effect = RuntimeError("disk error")
            status, body = handlers.handle_get_l1()

        assert status == 500
        assert body["error"]["code"] == "l1_read_error"

    # ── handle_get_l2: 500 exception path (lines 343-344) ────────────────

    def test_get_l2_exception_returns_500(self, tmp_path):
        """handle_get_l2 returns 500 when L2Generator.load raises an unexpected exception."""
        handlers = _make_handlers(tmp_path)

        with patch("the_door.core.ui.api_handlers.L2Generator") as mock_gen:
            mock_gen.load.side_effect = RuntimeError("disk error")
            status, body = handlers.handle_get_l2("feat-1")

        assert status == 500
        assert body["error"]["code"] == "l2_read_error"

    # ── handle_post_l2_generate: structure.json read error (lines 368-369) ─

    def test_post_l2_generate_structure_read_error_returns_500(self, tmp_path):
        """handle_post_l2_generate returns 500 when structure.json cannot be parsed."""
        handlers = _make_handlers(tmp_path)
        dot_dir = tmp_path / ".the-door"
        dot_dir.mkdir()
        # Write invalid JSON to structure.json
        (dot_dir / "structure.json").write_bytes(b"\xff\xfe invalid")

        status, body = handlers.handle_post_l2_generate("feat-1")

        assert status == 500
        assert body["error"]["code"] == "structure_read_error"

    # ── handle_get_layer_explanation: read error (lines 426-427) ─────────

    def test_get_layer_explanation_read_error_returns_500(self, tmp_path):
        """handle_get_layer_explanation returns 500 when cache file cannot be parsed."""
        handlers = _make_handlers(tmp_path)
        exp_dir = tmp_path / ".the-door" / "layer-explanations" / "feat-1"
        exp_dir.mkdir(parents=True)
        # Write invalid JSON
        (exp_dir / "l2.json").write_bytes(b"\xff\xfe invalid")

        status, body = handlers.handle_get_layer_explanation("feat-1", "l2")

        assert status == 500
        assert body["error"]["code"] == "explanation_read_error"

    # ── handle_post_layer_explanation_generate: invalid layer (line 442) ──

    def test_post_layer_explanation_generate_invalid_layer_returns_400(self, tmp_path):
        """handle_post_layer_explanation_generate returns 400 for invalid layer."""
        handlers = _make_handlers(tmp_path)

        status, body = handlers.handle_post_layer_explanation_generate("feat-1", "l99")

        assert status == 400
        assert body["error"]["code"] == "invalid_layer"

    # ── handle_get_structure: read error (lines 482-483) ─────────────────

    def test_get_structure_read_error_returns_500(self, tmp_path):
        """handle_get_structure returns 500 when structure.json cannot be parsed."""
        handlers = _make_handlers(tmp_path)
        dot_dir = tmp_path / ".the-door"
        dot_dir.mkdir()
        # Write invalid JSON
        (dot_dir / "structure.json").write_bytes(b"\xff\xfe invalid")

        status, body = handlers.handle_get_structure()

        assert status == 500
        assert body["error"]["code"] == "structure_read_error"

    # ── _run_l2_generate_job: general Exception path (lines 536-537) ─────

    def test_run_l2_generate_job_general_exception_fails_job(self, tmp_path):
        """_run_l2_generate_job calls fail_job when an unexpected Exception occurs."""
        from unittest.mock import AsyncMock
        from the_door.core.ui.job_store import JobStore

        job_store = JobStore()
        job = job_store.try_create_job()
        handlers = APIHandlers(project_root=tmp_path, job_store=job_store)

        mock_provider = MagicMock()
        # Return valid JSON but cause StructureJSON construction to fail
        mock_provider.complete = AsyncMock(return_value='{"modules":[],"module_interactions":[],"anomalies":[]}')

        with patch("the_door.core.ui.api_handlers.ConfigManager") as mock_cm, \
             patch("the_door.core.ui.api_handlers.create_provider", return_value=mock_provider), \
             patch("the_door.core.ui.api_handlers.L2Generator") as mock_gen:
            mock_cm.load.return_value = MagicMock()
            mock_gen.return_value.generate = AsyncMock(side_effect=ValueError("unexpected"))
            handlers._run_l2_generate_job(job, "feat-1", {"nodes": [], "edges": []})

        updated_job = job_store.get_job(job.job_id)
        assert updated_job.status == "failed"
