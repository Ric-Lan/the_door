"""Unit tests for pruning_engine module.

Tests are written BEFORE implementation (TDD red phase).
"""
from __future__ import annotations

import pytest

from the_door.core.reading.pruning_engine import PruningEngine, PruningDecision
from the_door.models import Edge


class TestPruningEngineRecordConfidence:
    """Unit tests for PruningEngine.record_confidence()."""

    def test_high_confidence_node_is_pruned(self):
        """record_confidence('node_a', 'high', batch=1) → node_a in get_pruned_nodes()."""
        engine = PruningEngine(edges=[])
        engine.record_confidence("node_a", "high", batch=1)

        assert "node_a" in engine.get_pruned_nodes()

    def test_medium_confidence_not_pruned(self):
        """Medium confidence nodes are NOT pruned."""
        engine = PruningEngine(edges=[])
        engine.record_confidence("node_a", "medium", batch=1)

        assert "node_a" not in engine.get_pruned_nodes()

    def test_low_confidence_not_pruned(self):
        """Low confidence nodes are NOT pruned."""
        engine = PruningEngine(edges=[])
        engine.record_confidence("node_a", "low", batch=1)

        assert "node_a" not in engine.get_pruned_nodes()


class TestPruningEngineShouldPrune:
    """Unit tests for PruningEngine.should_prune()."""

    def test_should_prune_returns_true_for_pruned(self):
        """should_prune returns True for pruned nodes."""
        engine = PruningEngine(edges=[])
        engine.record_confidence("node_a", "high", batch=1)

        assert engine.should_prune("node_a") is True

    def test_should_prune_returns_false_for_non_pruned(self):
        """should_prune returns False for non-pruned nodes."""
        engine = PruningEngine(edges=[])
        engine.record_confidence("node_a", "medium", batch=1)

        assert engine.should_prune("node_a") is False

    def test_should_prune_returns_false_for_unknown(self):
        """should_prune returns False for nodes never recorded."""
        engine = PruningEngine(edges=[])

        assert engine.should_prune("unknown_node") is False


class TestPruningEngineDownstream:
    """Unit tests for downstream dependency pruning."""

    def test_downstream_of_high_confidence_also_pruned(self):
        """Downstream dependencies of high-confidence node also pruned (no other refs)."""
        edges = [
            Edge(from_node="node_a", to_node="node_b", type="calls"),
        ]
        engine = PruningEngine(edges=edges)
        engine.record_confidence("node_a", "high", batch=1)

        pruned = engine.get_pruned_nodes()
        assert "node_a" in pruned
        assert "node_b" in pruned

    def test_downstream_with_other_pending_refs_not_pruned(self):
        """Downstream dependency with other pending refs NOT pruned."""
        edges = [
            Edge(from_node="node_a", to_node="node_c", type="calls"),
            Edge(from_node="node_b", to_node="node_c", type="calls"),
        ]
        engine = PruningEngine(edges=edges)
        # Only prune node_a; node_b still references node_c
        engine.record_confidence("node_a", "high", batch=1)

        pruned = engine.get_pruned_nodes()
        assert "node_a" in pruned
        assert "node_c" not in pruned  # node_b still references it

    def test_all_nodes_high_confidence_all_pruned(self):
        """All nodes high-confidence → all pruned."""
        edges = [
            Edge(from_node="node_a", to_node="node_b", type="calls"),
        ]
        engine = PruningEngine(edges=edges)
        engine.record_confidence("node_a", "high", batch=1)
        engine.record_confidence("node_b", "high", batch=1)

        pruned = engine.get_pruned_nodes()
        assert "node_a" in pruned
        assert "node_b" in pruned


class TestPruningEngineReinstate:
    """Unit tests for PruningEngine.reinstate()."""

    def test_reinstate_removes_from_pruned_set(self):
        """reinstate('node_a', batch=3) → node_a removed from pruned set."""
        engine = PruningEngine(edges=[])
        engine.record_confidence("node_a", "high", batch=1)
        assert "node_a" in engine.get_pruned_nodes()

        result = engine.reinstate("node_a", batch=3)
        assert result is True
        assert "node_a" not in engine.get_pruned_nodes()

    def test_reinstate_non_pruned_node_returns_false(self):
        """Reinstating a non-pruned node returns False."""
        engine = PruningEngine(edges=[])

        result = engine.reinstate("node_a", batch=2)
        assert result is False


class TestPruningEngineDecisions:
    """Unit tests for PruningEngine.get_decisions()."""

    def test_no_high_confidence_empty_decisions(self):
        """No high-confidence nodes → get_pruned_nodes() returns empty set."""
        engine = PruningEngine(edges=[])
        engine.record_confidence("node_a", "medium", batch=1)
        engine.record_confidence("node_b", "low", batch=2)

        assert engine.get_pruned_nodes() == set()

    def test_get_decisions_returns_complete_list(self):
        """get_decisions() returns complete list of PruningDecision objects."""
        edges = [Edge(from_node="node_a", to_node="node_b", type="calls")]
        engine = PruningEngine(edges=edges)
        engine.record_confidence("node_a", "high", batch=1)

        decisions = engine.get_decisions()
        assert len(decisions) >= 1
        assert all(isinstance(d, PruningDecision) for d in decisions)

        # Find the decision for node_a
        node_a_decisions = [d for d in decisions if d.node_id == "node_a"]
        assert len(node_a_decisions) == 1
        assert node_a_decisions[0].batch == 1
        assert node_a_decisions[0].reason is not None
