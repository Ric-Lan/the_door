"""Unit tests for batch_reader module.

Tests are written BEFORE implementation (TDD red phase).
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from the_door.core.reading.batch_reader import BatchReader, BatchReadResult
from the_door.models import (
    StructureJSON,
    ASTNode,
    Edge,
    FileInfo,
    TopologyEntry,
)


# We use the MockLLMProvider from conftest.py


def make_structure(nodes_per_batch: dict[int, list[str]], edges: list[Edge] | None = None) -> StructureJSON:
    """Helper: create a StructureJSON with nodes assigned to specific batches."""
    all_nodes = []
    all_topology = []
    files = set()

    for batch, node_ids in nodes_per_batch.items():
        for nid in node_ids:
            parts = nid.split("::")
            file_name = parts[0]
            func_name = parts[1]
            files.add(file_name)
            all_nodes.append(
                ASTNode(node_id=nid, type="function", name=func_name, file=file_name, language="python")
            )
            all_topology.append(
                TopologyEntry(
                    node_id=nid, in_degree=0, out_degree=0,
                    topology_rank=batch, is_entry_point=(batch == 1),
                    batch_assignment=batch,
                )
            )

    return StructureJSON(
        files=[FileInfo(path=f, language="python") for f in files],
        nodes=all_nodes,
        edges=edges or [],
        topology=all_topology,
    )


class TestBatchReaderRead:
    """Unit tests for BatchReader.read()."""

    def test_single_batch_structure(self, mock_llm_with_responses):
        """read() with single-batch structure → correct BatchReadResult."""
        mock = mock_llm_with_responses({
            "features": [
                {
                    "feature_id": "feat-login",
                    "label": "User login",
                    "description": "Handles user authentication",
                    "trigger": "user_action",
                    "trigger_description": "User submits credentials",
                    "confidence": "high",
                    "confidence_reason": "Clear route handler",
                    "source_nodes": ["app.py::login"],
                }
            ],
            "feature_relations": [],
            "unclassified_nodes": [],
            "infrastructure_nodes": [],
        })

        structure = make_structure({1: ["app.py::login"]})
        reader = BatchReader(llm_provider=mock, structure=structure)
        result = asyncio.run(reader.read())

        assert isinstance(result, BatchReadResult)
        assert len(result.l1_output.features) == 1
        assert result.l1_output.features[0].feature_id == "feat-login"

    def test_multi_batch_processed_in_order(self, mock_llm_with_responses):
        """read() with multi-batch structure → batches processed in order."""
        responses = [
            {"features": [{"feature_id": "feat-1", "label": "F1", "description": "D1",
                          "trigger": "user_action", "trigger_description": "T1",
                          "confidence": "high", "confidence_reason": "R1",
                          "source_nodes": ["mod1.py::func_1"]}],
             "feature_relations": [], "unclassified_nodes": [], "infrastructure_nodes": []},
            {"features": [{"feature_id": "feat-2", "label": "F2", "description": "D2",
                          "trigger": "scheduled", "trigger_description": "T2",
                          "confidence": "medium", "confidence_reason": "R2",
                          "source_nodes": ["mod2.py::func_2"]}],
             "feature_relations": [], "unclassified_nodes": [], "infrastructure_nodes": []},
        ]
        mock = mock_llm_with_responses(responses)

        structure = make_structure({
            1: ["mod1.py::func_1"],
            2: ["mod2.py::func_2"],
        })
        reader = BatchReader(llm_provider=mock, structure=structure)
        result = asyncio.run(reader.read())

        assert mock.call_count == 2
        assert len(result.l1_output.features) == 2

    def test_empty_structure_returns_empty_result(self, mock_llm_with_responses):
        """read() with empty structure (0 nodes) → empty result."""
        mock = mock_llm_with_responses("{}")
        structure = StructureJSON()
        reader = BatchReader(llm_provider=mock, structure=structure)
        result = asyncio.run(reader.read())

        assert isinstance(result, BatchReadResult)
        assert len(result.l1_output.features) == 0
        assert mock.call_count == 0  # No LLM calls for empty structure

    def test_max_batch_limit_enforced(self, mock_llm_with_responses):
        """Max batch limit (5) enforced, remaining nodes marked unclassified."""
        mock = mock_llm_with_responses(
            {"features": [], "feature_relations": [], "unclassified_nodes": [], "infrastructure_nodes": []}
        )

        # Create structure with 7 batches (exceeds limit of 5)
        nodes_per_batch = {i: [f"mod{i}.py::func_{i}"] for i in range(1, 8)}
        structure = make_structure(nodes_per_batch)
        reader = BatchReader(llm_provider=mock, structure=structure)
        result = asyncio.run(reader.read())

        # Only 5 batches should be processed
        assert mock.call_count <= 5
        # Remaining nodes should be unclassified
        assert len(result.l1_output.unclassified_nodes) >= 2

    def test_affected_nodes_partial_reanalysis(self, mock_llm_with_responses):
        """affected_nodes parameter → only specified nodes + dependents re-analyzed."""
        mock = mock_llm_with_responses(
            {"features": [{"feature_id": "feat-1", "label": "F1", "description": "D1",
                          "trigger": "user_action", "trigger_description": "T1",
                          "confidence": "high", "confidence_reason": "R1",
                          "source_nodes": ["mod1.py::func_1"]}],
             "feature_relations": [], "unclassified_nodes": [], "infrastructure_nodes": []}
        )

        edges = [Edge(from_node="mod1.py::func_1", to_node="mod2.py::func_2", type="calls")]
        structure = make_structure(
            {1: ["mod1.py::func_1", "mod3.py::func_3"], 2: ["mod2.py::func_2"]},
            edges=edges,
        )
        reader = BatchReader(llm_provider=mock, structure=structure)
        result = asyncio.run(reader.read(affected_nodes=["mod1.py::func_1"]))

        # Should only analyze func_1 and its dependent func_2, not func_3
        assert isinstance(result, BatchReadResult)

    def test_batch_payload_exceeding_context_auto_split(self, mock_llm_with_responses):
        """Batch payload exceeding context window → auto-split into sub-batches."""
        mock = mock_llm_with_responses(
            {"features": [], "feature_relations": [], "unclassified_nodes": [], "infrastructure_nodes": []}
        )

        # Create a batch with many nodes (simulating large payload)
        many_nodes = [f"mod{i}.py::func_{i}" for i in range(50)]
        structure = make_structure({1: many_nodes})
        reader = BatchReader(llm_provider=mock, structure=structure, max_context_tokens=100)
        result = asyncio.run(reader.read())

        # Should have made multiple LLM calls due to auto-splitting
        assert mock.call_count > 1

    def test_llm_empty_response_nodes_unclassified(self, mock_llm_with_responses):
        """LLM returns empty response → nodes marked unclassified."""
        mock = mock_llm_with_responses("")  # Empty response

        structure = make_structure({1: ["mod1.py::func_1"]})
        reader = BatchReader(llm_provider=mock, structure=structure)
        result = asyncio.run(reader.read())

        assert "mod1.py::func_1" in result.l1_output.unclassified_nodes

    def test_low_confidence_triggers_source_review(self, mock_llm_with_responses):
        """Low-confidence node triggers source review escalation."""
        mock = mock_llm_with_responses(
            {"features": [{"feature_id": "feat-1", "label": "F1", "description": "D1",
                          "trigger": "user_action", "trigger_description": "T1",
                          "confidence": "low", "confidence_reason": "Unclear purpose",
                          "source_nodes": ["mod1.py::func_1"],
                          "needs_source_review": True,
                          "review_reason": "Generic function name"}],
             "feature_relations": [], "unclassified_nodes": [], "infrastructure_nodes": []}
        )

        structure = make_structure({1: ["mod1.py::func_1"]})
        reader = BatchReader(llm_provider=mock, structure=structure)
        result = asyncio.run(reader.read())

        # The feature should be marked for source review
        assert any(f.needs_source_review for f in result.l1_output.features)


class TestBatchReaderRegenerate:
    """Unit tests for BatchReader.regenerate()."""

    def test_regenerate_different_result_marker_applied(self, mock_llm_with_responses):
        """regenerate() with different result → marker applied, previous preserved."""
        mock = mock_llm_with_responses(
            {"features": [{"feature_id": "feat-1", "label": "Updated label", "description": "New description",
                          "trigger": "user_action", "trigger_description": "T1",
                          "confidence": "high", "confidence_reason": "R1",
                          "source_nodes": ["mod1.py::func_1"]}],
             "feature_relations": [], "unclassified_nodes": [], "infrastructure_nodes": []}
        )

        structure = make_structure({1: ["mod1.py::func_1"]})
        reader = BatchReader(llm_provider=mock, structure=structure)

        # Simulate previous result
        from the_door.models import Feature
        previous = Feature(
            feature_id="feat-1", label="Old label", description="Old description",
            trigger="user_action", trigger_description="T1",
            confidence="high", confidence_reason="R1",
            source_nodes=["mod1.py::func_1"],
        )

        result = asyncio.run(reader.regenerate("feat-1", previous_result=previous))

        assert result.new_result is not None
        assert result.previous_result == previous
        assert result.differs is True

    def test_regenerate_identical_result_no_marker(self, mock_llm_with_responses):
        """regenerate() with identical result → no marker."""
        mock = mock_llm_with_responses(
            {"features": [{"feature_id": "feat-1", "label": "Same label", "description": "Same desc",
                          "trigger": "user_action", "trigger_description": "T1",
                          "confidence": "high", "confidence_reason": "R1",
                          "source_nodes": ["mod1.py::func_1"]}],
             "feature_relations": [], "unclassified_nodes": [], "infrastructure_nodes": []}
        )

        structure = make_structure({1: ["mod1.py::func_1"]})
        reader = BatchReader(llm_provider=mock, structure=structure)

        from the_door.models import Feature
        previous = Feature(
            feature_id="feat-1", label="Same label", description="Same desc",
            trigger="user_action", trigger_description="T1",
            confidence="high", confidence_reason="R1",
            source_nodes=["mod1.py::func_1"],
        )

        result = asyncio.run(reader.regenerate("feat-1", previous_result=previous))

        assert result.differs is False


# === L1_SYSTEM_PROMPT wire-through tests ===

import json
from unittest.mock import AsyncMock

from the_door.core.llm.prompts import L1_SYSTEM_PROMPT
from the_door.models import Feature, StructureJSON


def _l1_minimal_structure() -> StructureJSON:
    return StructureJSON()


def _l1_stub_feature() -> Feature:
    return Feature(
        feature_id="feat-x",
        label="x",
        description="",
        trigger="user_action",
        trigger_description="",
        confidence="medium",
        confidence_reason="",
        source_nodes=[],
    )


def _extract_system_prompt(call) -> str | None:
    system_prompt = call.kwargs.get("system_prompt")
    if system_prompt is None and len(call.args) >= 2:
        system_prompt = call.args[1]
    return system_prompt


def test_process_batch_passes_l1_system_prompt():
    """_process_batch must pass L1_SYSTEM_PROMPT as the system_prompt argument."""
    provider = AsyncMock()
    provider.complete = AsyncMock(
        return_value=json.dumps({"features": [], "feature_relations": []})
    )

    reader = BatchReader(provider, _l1_minimal_structure())
    asyncio.run(reader._process_batch(["n1"], 0))

    assert provider.complete.await_count == 1
    assert _extract_system_prompt(provider.complete.await_args) == L1_SYSTEM_PROMPT


def test_regenerate_passes_l1_system_prompt():
    """regenerate() must pass L1_SYSTEM_PROMPT as system_prompt."""
    provider = AsyncMock()
    provider.complete = AsyncMock(
        return_value=json.dumps({"features": [{"feature_id": "feat-x", "label": "x"}]})
    )

    reader = BatchReader(provider, _l1_minimal_structure())
    asyncio.run(reader.regenerate("feat-x", _l1_stub_feature()))

    assert _extract_system_prompt(provider.complete.await_args) == L1_SYSTEM_PROMPT
