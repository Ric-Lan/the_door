"""Property-based tests for topology analysis.

Tests are written BEFORE implementation (TDD red phase).
Uses Hypothesis to verify universal correctness properties.
"""
import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from the_door.core.topology.topology_analyzer import TopologyAnalyzer
from the_door.core.topology.entry_point_detector import EntryPointDetector
from the_door.core.topology.batch_assigner import BatchAssigner
from the_door.models import ASTNode, Edge, TopologyEntry


# === Strategies ===

KNOWN_ENTRY_DECORATORS = {"@app.route", "@Controller", "@Get", "@Post", "@Cron", "@EventSubscriber"}
ENTRY_DIRECTORIES = {"routes/", "handlers/", "controllers/", "views/", "endpoints/"}


def make_node(node_id: str, decorators: list[str] = None, file: str = "src/main.py") -> ASTNode:
    """Create a minimal ASTNode for testing."""
    return ASTNode(
        node_id=node_id,
        type="function",
        name=node_id.split("::")[-1] if "::" in node_id else node_id,
        file=file,
        language="python",
        decorators=decorators or [],
    )


@st.composite
def graph_strategy(draw):
    """Generate a random directed graph of nodes and edges."""
    num_nodes = draw(st.integers(min_value=2, max_value=20))
    node_ids = [f"file.py::func_{i}" for i in range(num_nodes)]
    nodes = [make_node(nid) for nid in node_ids]

    # Generate random edges (no self-loops)
    max_edges = min(num_nodes * 2, 30)
    num_edges = draw(st.integers(min_value=0, max_value=max_edges))
    edges = []
    for _ in range(num_edges):
        from_idx = draw(st.integers(min_value=0, max_value=num_nodes - 1))
        to_idx = draw(st.integers(min_value=0, max_value=num_nodes - 1))
        if from_idx != to_idx:
            edges.append(Edge(
                from_node=node_ids[from_idx],
                to_node=node_ids[to_idx],
                type="calls"
            ))

    return nodes, edges


# === Property 5: Degree computation correctness ===

class TestProperty5DegreeComputation:
    """Feature: the-door-phase-1-min, Property 5: Degree computation correctness"""

    @settings(max_examples=100)
    @given(data=graph_strategy())
    def test_degrees_match_edge_counts(self, data):
        """For any graph, in_degree equals incoming edge count and out_degree equals outgoing edge count.

        **Validates: Requirements 2.1**
        """
        nodes, edges = data

        # Act
        analyzer = TopologyAnalyzer()
        result = analyzer.analyze(nodes, edges)

        # Assert
        node_ids = {n.node_id for n in nodes}
        for entry in result.entries:
            assert entry.node_id in node_ids

            expected_in = sum(1 for e in edges if e.to_node == entry.node_id)
            expected_out = sum(1 for e in edges if e.from_node == entry.node_id)

            assert entry.in_degree == expected_in, (
                f"Node {entry.node_id}: expected in_degree={expected_in}, got {entry.in_degree}"
            )
            assert entry.out_degree == expected_out, (
                f"Node {entry.node_id}: expected out_degree={expected_out}, got {entry.out_degree}"
            )


# === Property 6: Entry point detection correctness ===

class TestProperty6EntryPointDetection:
    """Feature: the-door-phase-1-min, Property 6: Entry point detection correctness"""

    @settings(max_examples=100)
    @given(
        has_entry_decorator=st.booleans(),
        in_degree=st.integers(min_value=0, max_value=10),
        out_degree=st.integers(min_value=0, max_value=10),
        is_in_entry_dir=st.booleans(),
    )
    def test_entry_point_iff_decorator_or_path_rule(
        self, has_entry_decorator, in_degree, out_degree, is_in_entry_dir
    ):
        """Entry point detection returns true iff decorator match OR (in_degree=0 AND out_degree>0 AND entry dir).

        **Validates: Requirements 2.2**
        """
        # Arrange
        decorators = ["@app.route(\"/test\")"] if has_entry_decorator else []
        file_path = "routes/handler.py" if is_in_entry_dir else "utils/helper.py"
        node = make_node("test::func", decorators=decorators, file=file_path)

        # Act
        detector = EntryPointDetector()
        result = detector.is_entry_point(node, in_degree, out_degree)

        # Assert
        expected = has_entry_decorator or (in_degree == 0 and out_degree > 0 and is_in_entry_dir)
        assert result == expected, (
            f"Expected is_entry_point={expected} for decorator={has_entry_decorator}, "
            f"in_degree={in_degree}, out_degree={out_degree}, entry_dir={is_in_entry_dir}"
        )


# === Property 7: Batch assignment correctness ===

class TestProperty7BatchAssignment:
    """Feature: the-door-phase-1-min, Property 7: Batch assignment correctness"""

    @settings(max_examples=100)
    @given(data=graph_strategy())
    def test_entry_points_batch_1_and_ordering(self, data):
        """Entry points get batch 1; higher in_degree non-entry nodes get lower/equal batch numbers.

        **Validates: Requirements 2.3, 2.4, 2.5, 2.6, 18.5**
        """
        nodes, edges = data

        # Act
        analyzer = TopologyAnalyzer()
        result = analyzer.analyze(nodes, edges)

        # Identify entry points
        entry_entries = [e for e in result.entries if e.is_entry_point]
        non_entry_entries = [e for e in result.entries if not e.is_entry_point]

        # Assert — all entry points have batch_assignment == 1
        for entry in entry_entries:
            assert entry.batch_assignment == 1, (
                f"Entry point {entry.node_id} should have batch=1, got {entry.batch_assignment}"
            )

        # Assert — higher in_degree non-entry nodes have batch <= lower in_degree nodes
        for a in non_entry_entries:
            for b in non_entry_entries:
                if a.in_degree > b.in_degree:
                    assert a.batch_assignment <= b.batch_assignment, (
                        f"Node {a.node_id} (in_degree={a.in_degree}) should have batch <= "
                        f"node {b.node_id} (in_degree={b.in_degree})"
                    )

        # Assert — entry points have lower topology_rank than non-entry nodes
        if entry_entries and non_entry_entries:
            max_entry_rank = max(e.topology_rank for e in entry_entries)
            min_non_entry_rank = min(e.topology_rank for e in non_entry_entries)
            assert max_entry_rank < min_non_entry_rank, (
                "Entry points should have lower topology_rank than non-entry nodes"
            )
