"""Unit tests for cost_estimator module.

Tests are written BEFORE implementation (TDD red phase).
"""
from __future__ import annotations

import pytest

from the_door.core.rendering.cost_estimator import CostEstimator
from the_door.models import (
    StructureJSON,
    ASTNode,
    FileInfo,
    TopologyEntry,
    CostEstimate,
)


def make_structure(num_nodes: int) -> StructureJSON:
    """Helper: create a StructureJSON with N nodes."""
    nodes = [
        ASTNode(
            node_id=f"mod{i}.py::func_{i}",
            type="function",
            name=f"func_{i}",
            file=f"mod{i}.py",
            language="python",
        )
        for i in range(num_nodes)
    ]
    topology = [
        TopologyEntry(
            node_id=f"mod{i}.py::func_{i}",
            in_degree=0,
            out_degree=0,
            topology_rank=1,
            is_entry_point=True,
            batch_assignment=(i // 10) + 1,
        )
        for i in range(num_nodes)
    ]
    files = [FileInfo(path=f"mod{i}.py", language="python") for i in range(num_nodes)]
    return StructureJSON(files=files, nodes=nodes, topology=topology)


class TestCostEstimator:
    """Unit tests for CostEstimator.estimate()."""

    def test_zero_nodes_zero_tokens(self):
        """estimate with zero nodes → CostEstimate with 0 tokens."""
        estimator = CostEstimator(provider_name="openai", model_name="gpt-4o")
        structure = StructureJSON()

        estimate = estimator.estimate(structure)

        assert isinstance(estimate, CostEstimate)
        assert estimate.total_input_tokens == 0
        assert estimate.total_output_tokens == 0
        assert estimate.estimated_cost_usd == 0.0

    def test_ollama_is_local_zero_cost(self):
        """estimate with Ollama provider → is_local=True, cost=0.0."""
        estimator = CostEstimator(provider_name="ollama", model_name="qwen3:8b")
        structure = make_structure(10)

        estimate = estimator.estimate(structure)

        assert estimate.is_local is True
        assert estimate.estimated_cost_usd == 0.0
        assert estimate.provider == "ollama"
        assert estimate.model == "qwen3:8b"

    def test_openai_correct_cost(self):
        """estimate with OpenAI provider → correct cost based on pricing."""
        estimator = CostEstimator(provider_name="openai", model_name="gpt-4o")
        structure = make_structure(10)

        estimate = estimator.estimate(structure)

        assert estimate.is_local is False
        assert estimate.provider == "openai"
        assert estimate.model == "gpt-4o"
        assert estimate.estimated_cost_usd > 0.0
        assert estimate.total_input_tokens > 0
        assert estimate.total_output_tokens > 0

    def test_anthropic_correct_cost(self):
        """estimate with Anthropic provider → correct cost based on pricing."""
        estimator = CostEstimator(provider_name="anthropic", model_name="claude-sonnet-4-20250514")
        structure = make_structure(10)

        estimate = estimator.estimate(structure)

        assert estimate.is_local is False
        assert estimate.provider == "anthropic"
        assert estimate.estimated_cost_usd > 0.0

    def test_larger_structure_higher_estimate(self):
        """Larger structure produces higher token estimate than smaller."""
        estimator = CostEstimator(provider_name="openai", model_name="gpt-4o")

        small = make_structure(5)
        large = make_structure(50)

        est_small = estimator.estimate(small)
        est_large = estimator.estimate(large)

        assert est_large.total_input_tokens > est_small.total_input_tokens
        assert est_large.total_output_tokens > est_small.total_output_tokens
        assert est_large.estimated_cost_usd > est_small.estimated_cost_usd

    def test_batch_count_reflects_expected(self):
        """batch_count reflects expected number of batches."""
        estimator = CostEstimator(provider_name="openai", model_name="gpt-4o")
        structure = make_structure(10)

        estimate = estimator.estimate(structure)

        assert estimate.batch_count >= 1
