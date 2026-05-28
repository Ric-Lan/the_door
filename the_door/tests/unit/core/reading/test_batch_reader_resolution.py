"""Tests for Task 06 — BatchReader detail mode payload includes edge.resolution.

BatchReader API (verified against src batch_reader.py:50-57):
- Constructor: BatchReader(llm_provider, structure: StructureJSON, *,
                          max_context_tokens=None, context_mode="detail")
- Method:      _build_payload(node_ids: list[str], batch_num: int) → dict

Note: first positional arg is `llm_provider` (not `provider`); `structure` is the
second positional. We test _build_payload directly because it's the smallest seam
containing the edge serialization logic. The llm_provider is mocked because
BatchReader's constructor wires up PruningEngine + provider but neither is
exercised by _build_payload.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from the_door.core.reading.batch_reader import BatchReader
from the_door.models import ASTNode, Edge, StructureJSON


def _node(node_id, name="x", file="f.py"):
    return ASTNode(
        node_id=node_id,
        name=name,
        file=file,
        language="python",
        type="function",
    )


def _make_reader(nodes, edges, context_mode="detail"):
    structure = StructureJSON(files=[], nodes=nodes, edges=edges, topology=[])
    provider = MagicMock()
    provider.estimate_tokens.return_value = 100
    # Real signature: BatchReader(llm_provider, structure, *, max_context_tokens=None, context_mode="detail")
    return BatchReader(llm_provider=provider, structure=structure, context_mode=context_mode)


class TestBatchReaderResolution:
    """Detail mode payload must include edges with resolution so LLM can read it."""

    def test_detail_payload_includes_edges_key(self):
        nodes = [_node("a.py::foo", "foo"), _node("a.py::bar", "bar")]
        edges = [Edge(from_node="a.py::foo", to_node="a.py::bar", type="calls", resolution="scope_rule")]
        reader = _make_reader(nodes, edges)
        payload = reader._build_payload(["a.py::foo", "a.py::bar"], batch_num=1)
        assert "edges" in payload, f"detail payload must contain 'edges' key, got: {list(payload.keys())}"

    def test_detail_payload_edge_has_resolution_field(self):
        nodes = [_node("a.py::foo"), _node("a.py::bar")]
        edges = [Edge(from_node="a.py::foo", to_node="a.py::bar", type="calls", resolution="scope_rule")]
        reader = _make_reader(nodes, edges)
        payload = reader._build_payload(["a.py::foo", "a.py::bar"], batch_num=1)
        payload_str = json.dumps(payload, ensure_ascii=False)
        assert "scope_rule" in payload_str

    def test_detail_payload_filters_edges_to_batch_node_ids(self):
        """Edges referencing nodes outside the current batch must be excluded
        to keep payload size bounded (per spec §3 non-goal: don't blow up payloads)."""
        nodes = [_node("a.py::foo"), _node("a.py::bar"), _node("c.py::out")]
        edges = [
            Edge(from_node="a.py::foo", to_node="a.py::bar", type="calls", resolution="scope_rule"),
            Edge(from_node="a.py::foo", to_node="c.py::out", type="calls", resolution="name_match"),
        ]
        reader = _make_reader(nodes, edges)
        payload = reader._build_payload(["a.py::foo", "a.py::bar"], batch_num=1)
        # Only the within-batch edge should be present
        edge_dicts = payload.get("edges", [])
        targets = {e["to"] for e in edge_dicts}
        assert "a.py::bar" in targets
        assert "c.py::out" not in targets, "out-of-batch edge must be filtered"

    def test_detail_payload_serializes_all_resolution_types(self):
        nodes = [_node("a.py::foo"), _node("a.py::bar")]
        edges_full = [
            Edge(from_node="a.py::foo", to_node="a.py::bar", type="calls", resolution="scope_rule"),
            Edge(from_node="a.py::bar", to_node="a.py::foo", type="calls", resolution="name_match"),
        ]
        reader = _make_reader(nodes, edges_full)
        payload = reader._build_payload(["a.py::foo", "a.py::bar"], batch_num=1)
        payload_str = json.dumps(payload, ensure_ascii=False)
        assert "scope_rule" in payload_str
        assert "name_match" in payload_str

    def test_minimal_mode_payload_unchanged_no_edges(self):
        """minimal mode is intentionally edge-less; spec §4.5 教學只對 detail mode."""
        nodes = [_node("a.py::foo")]
        edges = [Edge(from_node="a.py::foo", to_node="a.py::foo", type="calls", resolution="scope_rule")]
        reader = _make_reader(nodes, edges, context_mode="minimal")
        payload = reader._build_payload(["a.py::foo"], batch_num=1)
        assert "edges" not in payload
        assert payload["context_mode"] == "minimal"
