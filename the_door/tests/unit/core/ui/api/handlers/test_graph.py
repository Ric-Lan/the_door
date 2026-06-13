"""Unit tests for GraphHandlers."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from the_door.core.ui.api.context import APIContext
from the_door.core.ui.api.handlers.graph import GraphHandlers


def _ctx(tmp_path: Path) -> APIContext:
    return APIContext(lambda: tmp_path, lambda p, f: {})


class TestGetL1:
    def test_no_snapshot_returns_404(self, tmp_path):
        h = GraphHandlers(_ctx(tmp_path))
        with patch("the_door.core.ui.api.handlers.graph.SnapshotStore") as mock_ss:
            mock_ss.return_value.get_latest.return_value = None
            status, body = h.get_l1()
        assert status == 404
        assert body["error"]["code"] == "no_l1_data"

    def test_with_snapshot_returns_200(self, tmp_path):
        h = GraphHandlers(_ctx(tmp_path))
        snap = MagicMock()
        snap.l1_snapshot = {}
        snap.feature_relations_snapshot = []
        with (
            patch("the_door.core.ui.api.handlers.graph.SnapshotStore") as mock_ss,
            patch("the_door.core.ui.api.handlers.graph.build_l1_graph_view_model_from_snapshot", return_value={"nodes": []}),
        ):
            mock_ss.return_value.get_latest.return_value = snap
            status, body = h.get_l1()
        assert status == 200

    def test_response_includes_project_summary(self, tmp_path):
        h = GraphHandlers(_ctx(tmp_path))
        snap = MagicMock()
        snap.l1_snapshot = {}
        snap.feature_relations_snapshot = []
        snap.project_summary = "這個專案做登入。"
        with (
            patch("the_door.core.ui.api.handlers.graph.SnapshotStore") as mock_ss,
            patch("the_door.core.ui.api.handlers.graph.build_l1_graph_view_model_from_snapshot", return_value={"nodes": []}),
        ):
            mock_ss.return_value.get_latest.return_value = snap
            status, body = h.get_l1()
        assert status == 200
        assert body["project_summary"] == "這個專案做登入。"

    def test_response_project_summary_none_when_absent(self, tmp_path):
        h = GraphHandlers(_ctx(tmp_path))
        snap = MagicMock()
        snap.l1_snapshot = {}
        snap.feature_relations_snapshot = []
        snap.project_summary = None
        with (
            patch("the_door.core.ui.api.handlers.graph.SnapshotStore") as mock_ss,
            patch("the_door.core.ui.api.handlers.graph.build_l1_graph_view_model_from_snapshot", return_value={"nodes": []}),
        ):
            mock_ss.return_value.get_latest.return_value = snap
            status, body = h.get_l1()
        assert body["project_summary"] is None


class TestGetL2:
    def test_not_generated_returns_404(self, tmp_path):
        h = GraphHandlers(_ctx(tmp_path))
        with patch("the_door.core.ui.api.handlers.graph.L2Generator") as mock_lg:
            mock_lg.load.return_value = None
            status, body = h.get_l2(feature_id="feat-x")
        assert status == 404
        assert body["error"]["code"] == "l2_not_generated"

    def test_cached_returns_200(self, tmp_path):
        h = GraphHandlers(_ctx(tmp_path))
        l2_output = MagicMock()
        with (
            patch("the_door.core.ui.api.handlers.graph.L2Generator") as mock_lg,
            patch("the_door.core.ui.api.handlers.graph.build_l2_graph_view_model", return_value={"ok": True}),
        ):
            mock_lg.load.return_value = l2_output
            status, body = h.get_l2(feature_id="feat-x")
        assert status == 200


class TestGetStructure:
    def test_no_structure_returns_404(self, tmp_path):
        h = GraphHandlers(_ctx(tmp_path))
        status, body = h.get_structure()
        assert status == 404

    def test_valid_structure_returns_200(self, tmp_path):
        dot = tmp_path / ".the-door"; dot.mkdir()
        data = {"nodes": [], "edges": []}
        (dot / "structure.json").write_text(json.dumps(data), encoding="utf-8")
        h = GraphHandlers(_ctx(tmp_path))
        status, body = h.get_structure()
        assert status == 200
        assert "nodes" in body


class TestGetLayerExplanation:
    def test_invalid_layer_returns_400(self, tmp_path):
        h = GraphHandlers(_ctx(tmp_path))
        status, body = h.get_layer_explanation(feature_id="feat-x", layer="l99")
        assert status == 400
        assert body["error"]["code"] == "invalid_layer"

    def test_not_cached_returns_404(self, tmp_path):
        h = GraphHandlers(_ctx(tmp_path))
        status, body = h.get_layer_explanation(feature_id="feat-x", layer="l1")
        assert status == 404

    def test_cached_returns_200(self, tmp_path):
        cache_dir = tmp_path / ".the-door" / "layer-explanations" / "feat-x"
        cache_dir.mkdir(parents=True)
        (cache_dir / "l1.json").write_text('{"explanation": "hi"}', encoding="utf-8")
        h = GraphHandlers(_ctx(tmp_path))
        status, body = h.get_layer_explanation(feature_id="feat-x", layer="l1")
        assert status == 200


class TestGraphErrorBranches:
    def test_get_l1_exception_returns_500(self, tmp_path):
        h = GraphHandlers(_ctx(tmp_path))
        with patch("the_door.core.ui.api.handlers.graph.SnapshotStore", side_effect=RuntimeError("x")):
            status, body = h.get_l1()
        assert status == 500
        assert body["error"]["code"] == "l1_read_error"

    def test_get_l2_exception_returns_500(self, tmp_path):
        h = GraphHandlers(_ctx(tmp_path))
        with patch("the_door.core.ui.api.handlers.graph.L2Generator") as mock_lg:
            mock_lg.load.side_effect = RuntimeError("x")
            status, body = h.get_l2(feature_id="feat-x")
        assert status == 500
        assert body["error"]["code"] == "l2_read_error"

    def test_get_structure_bad_json_returns_500(self, tmp_path):
        dot = tmp_path / ".the-door"; dot.mkdir()
        (dot / "structure.json").write_text("not json", encoding="utf-8")
        h = GraphHandlers(_ctx(tmp_path))
        status, body = h.get_structure()
        assert status == 500
        assert body["error"]["code"] == "structure_read_error"

    def test_get_layer_explanation_bad_json_returns_500(self, tmp_path):
        cache_dir = tmp_path / ".the-door" / "layer-explanations" / "feat-x"
        cache_dir.mkdir(parents=True)
        (cache_dir / "l1.json").write_text("not json", encoding="utf-8")
        h = GraphHandlers(_ctx(tmp_path))
        status, body = h.get_layer_explanation(feature_id="feat-x", layer="l1")
        assert status == 500
        assert body["error"]["code"] == "explanation_read_error"
