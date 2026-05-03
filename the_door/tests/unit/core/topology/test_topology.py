"""Unit tests for topology analysis modules (TDD red phase).

Tests are written BEFORE implementation — all should fail until modules are implemented.
Covers: GraphBuilder (10.1), EntryPointDetector (10.2), BatchAssigner (10.3),
        TopologyAnalyzer (10.4).
"""
import time

import pytest

from the_door.core.topology.topology_analyzer import TopologyAnalyzer
from the_door.core.topology.graph_builder import GraphBuilder
from the_door.core.topology.entry_point_detector import (
    EntryPointDetector,
    KNOWN_ENTRY_DECORATORS,
    ENTRY_DIRECTORIES,
)
from the_door.core.topology.batch_assigner import BatchAssigner
from the_door.models import ASTNode, Edge, TopologyEntry, TopologyResult


def make_node(node_id, decorators=None, file="src/main.py"):
    """Helper to create ASTNode instances for testing."""
    return ASTNode(
        node_id=node_id,
        type="function",
        name=node_id.split("::")[-1] if "::" in node_id else node_id,
        file=file,
        language="python",
        decorators=decorators or [],
    )


# === GraphBuilder tests (Task 10.1) ===


class TestGraphBuilder:
    """Unit tests for graph_builder module."""

    def test_builds_digraph_from_edges(self):
        nodes = [make_node("a::f1"), make_node("a::f2"), make_node("a::f3")]
        edges = [
            Edge(from_node="a::f1", to_node="a::f2", type="calls"),
            Edge(from_node="a::f2", to_node="a::f3", type="calls"),
        ]

        builder = GraphBuilder()
        graph = builder.build(nodes, edges)

        assert graph.number_of_nodes() == 3
        assert graph.number_of_edges() == 2

    def test_empty_edges_returns_graph_with_nodes(self):
        nodes = [make_node("a::f1")]
        edges = []

        builder = GraphBuilder()
        graph = builder.build(nodes, edges)

        assert graph.number_of_nodes() == 1
        assert graph.number_of_edges() == 0

    def test_handles_circular_dependencies(self):
        nodes = [make_node("a::f1"), make_node("a::f2")]
        edges = [
            Edge(from_node="a::f1", to_node="a::f2", type="calls"),
            Edge(from_node="a::f2", to_node="a::f1", type="calls"),
        ]

        builder = GraphBuilder()
        graph = builder.build(nodes, edges)

        assert graph.number_of_edges() == 2


# === EntryPointDetector tests (Task 10.2) ===


class TestEntryPointDetector:
    """Unit tests for entry_point_detector module."""

    def test_app_route_decorator_is_entry_point(self):
        node = make_node("app::handler", decorators=['@app.route("/test")'])
        detector = EntryPointDetector()
        assert detector.is_entry_point(node, in_degree=0, out_degree=1) is True

    def test_controller_decorator_is_entry_point(self):
        node = make_node("ctrl::action", decorators=["@Controller"])
        detector = EntryPointDetector()
        assert detector.is_entry_point(node, in_degree=0, out_degree=1) is True

    def test_zero_in_degree_in_routes_dir_is_entry_point(self):
        node = make_node("routes/api::handler", file="routes/api.py")
        detector = EntryPointDetector()
        assert detector.is_entry_point(node, in_degree=0, out_degree=1) is True

    def test_nonzero_in_degree_no_decorator_not_entry_point(self):
        node = make_node("utils::helper")
        detector = EntryPointDetector()
        assert detector.is_entry_point(node, in_degree=3, out_degree=2) is False

    def test_zero_in_degree_zero_out_degree_not_entry_point(self):
        node = make_node("orphan::func")
        detector = EntryPointDetector()
        assert detector.is_entry_point(node, in_degree=0, out_degree=0) is False

    def test_known_entry_decorators_constant_exists(self):
        assert isinstance(KNOWN_ENTRY_DECORATORS, (set, list, tuple, frozenset))
        assert len(KNOWN_ENTRY_DECORATORS) > 0

    def test_entry_directories_constant_exists(self):
        assert isinstance(ENTRY_DIRECTORIES, (set, list, tuple, frozenset))
        assert len(ENTRY_DIRECTORIES) > 0

    def test_get_decorator_is_entry_point(self):
        node = make_node("api::get_users", decorators=["@Get"])
        detector = EntryPointDetector()
        assert detector.is_entry_point(node, in_degree=0, out_degree=1) is True

    def test_post_decorator_is_entry_point(self):
        node = make_node("api::create_user", decorators=["@Post"])
        detector = EntryPointDetector()
        assert detector.is_entry_point(node, in_degree=0, out_degree=1) is True

    def test_handlers_dir_with_zero_in_degree_is_entry_point(self):
        node = make_node("handlers/event::on_event", file="handlers/event.py")
        detector = EntryPointDetector()
        assert detector.is_entry_point(node, in_degree=0, out_degree=1) is True

    def test_click_command_decorator_is_entry_point(self):
        node = make_node("cli::my_cmd", decorators=["@click.command"])
        detector = EntryPointDetector()
        assert detector.is_entry_point(node, in_degree=0, out_degree=1) is True

    def test_click_group_decorator_is_entry_point(self):
        node = make_node("cli::my_group", decorators=['@click.group()'])
        detector = EntryPointDetector()
        assert detector.is_entry_point(node, in_degree=0, out_degree=1) is True

    def test_typer_command_decorator_is_entry_point(self):
        node = make_node("cli::my_cmd", decorators=["@typer.command()"])
        detector = EntryPointDetector()
        assert detector.is_entry_point(node, in_degree=0, out_degree=1) is True

    def test_main_function_with_out_degree_is_entry_point(self):
        node = make_node("app::main", file="src/app.py")
        detector = EntryPointDetector()
        assert detector.is_entry_point(node, in_degree=0, out_degree=3) is True

    def test_main_function_zero_out_degree_not_entry_point(self):
        node = make_node("app::main", file="src/app.py")
        detector = EntryPointDetector()
        assert detector.is_entry_point(node, in_degree=0, out_degree=0) is False

    def test_dunder_main_file_is_entry_point(self):
        node = make_node("__main__.py::run", file="__main__.py")
        detector = EntryPointDetector()
        assert detector.is_entry_point(node, in_degree=0, out_degree=2) is True

    def test_cli_directory_with_zero_in_degree_is_entry_point(self):
        node = make_node("cli/cmd::handler", file="cli/cmd.py")
        detector = EntryPointDetector()
        assert detector.is_entry_point(node, in_degree=0, out_degree=1) is True

    def test_commands_directory_with_zero_in_degree_is_entry_point(self):
        node = make_node("commands/deploy::run", file="commands/deploy.py")
        detector = EntryPointDetector()
        assert detector.is_entry_point(node, in_degree=0, out_degree=1) is True


# === BatchAssigner tests (Task 10.3) ===


class TestBatchAssigner:
    """Unit tests for batch_assigner module."""

    def test_entry_points_get_batch_1(self):
        nodes = [make_node("a::f1"), make_node("a::f2"), make_node("a::f3")]
        in_degrees = {"a::f1": 0, "a::f2": 5, "a::f3": 2}
        entry_points = {"a::f1"}

        assigner = BatchAssigner()
        batches = assigner.assign_batches(nodes, in_degrees, entry_points)

        assert batches["a::f1"] == 1

    def test_non_entry_sorted_by_descending_in_degree(self):
        nodes = [make_node("a::f1"), make_node("a::f2"), make_node("a::f3")]
        in_degrees = {"a::f1": 0, "a::f2": 10, "a::f3": 2}
        entry_points = {"a::f1"}

        assigner = BatchAssigner()
        batches = assigner.assign_batches(nodes, in_degrees, entry_points)

        # f2 (in_degree=10) should be in same or earlier batch than f3 (in_degree=2)
        assert batches["a::f2"] <= batches["a::f3"]

    def test_max_batches_respected(self):
        nodes = [make_node(f"a::f{i}") for i in range(20)]
        in_degrees = {f"a::f{i}": i for i in range(20)}
        entry_points = {"a::f0"}

        assigner = BatchAssigner()
        batches = assigner.assign_batches(
            nodes, in_degrees, entry_points, max_batches=5
        )

        assert max(batches.values()) <= 5

    def test_empty_nodes_returns_empty(self):
        assigner = BatchAssigner()
        batches = assigner.assign_batches([], {}, set())
        assert batches == {}

    def test_all_entry_points_get_batch_1(self):
        nodes = [make_node("a::f1"), make_node("a::f2"), make_node("a::f3")]
        in_degrees = {"a::f1": 0, "a::f2": 0, "a::f3": 5}
        entry_points = {"a::f1", "a::f2"}

        assigner = BatchAssigner()
        batches = assigner.assign_batches(nodes, in_degrees, entry_points)

        assert batches["a::f1"] == 1
        assert batches["a::f2"] == 1


# === TopologyAnalyzer orchestrator tests (Task 10.4) ===


class TestTopologyAnalyzer:
    """Unit tests for topology_analyzer orchestrator."""

    def test_full_analysis_produces_topology(self):
        nodes = [make_node("a::f1", decorators=['@app.route("/")'])]
        nodes.append(make_node("a::f2"))
        edges = [Edge(from_node="a::f1", to_node="a::f2", type="calls")]

        analyzer = TopologyAnalyzer()
        result = analyzer.analyze(nodes, edges)

        assert isinstance(result, TopologyResult)
        assert len(result.entries) == 2
        entry = next(e for e in result.entries if e.node_id == "a::f1")
        assert entry.is_entry_point is True
        assert entry.batch_assignment == 1

    def test_performance_1000_nodes_under_1_second(self):
        nodes = [make_node(f"file.py::func_{i}") for i in range(1000)]
        edges = [
            Edge(
                from_node=f"file.py::func_{i}",
                to_node=f"file.py::func_{(i + 1) % 1000}",
                type="calls",
            )
            for i in range(999)
        ]

        analyzer = TopologyAnalyzer()
        start = time.time()
        result = analyzer.analyze(nodes, edges)
        elapsed = time.time() - start

        assert elapsed < 1.0, f"Topology analysis took {elapsed:.2f}s, must be < 1s"
        assert len(result.entries) == 1000

    def test_star_graph_pattern(self):
        hub = make_node("hub::center")
        leaves = [make_node(f"leaf::n{i}") for i in range(5)]
        nodes = [hub] + leaves
        edges = [
            Edge(from_node=f"leaf::n{i}", to_node="hub::center", type="calls")
            for i in range(5)
        ]

        analyzer = TopologyAnalyzer()
        result = analyzer.analyze(nodes, edges)

        hub_entry = next(e for e in result.entries if e.node_id == "hub::center")
        assert hub_entry.in_degree == 5
        assert hub_entry.out_degree == 0

    def test_chain_graph_pattern(self):
        nodes = [make_node(f"chain::n{i}") for i in range(5)]
        edges = [
            Edge(from_node=f"chain::n{i}", to_node=f"chain::n{i + 1}", type="calls")
            for i in range(4)
        ]

        analyzer = TopologyAnalyzer()
        result = analyzer.analyze(nodes, edges)

        # First node has in_degree=0, last has out_degree=0
        first = next(e for e in result.entries if e.node_id == "chain::n0")
        last = next(e for e in result.entries if e.node_id == "chain::n4")
        assert first.in_degree == 0
        assert first.out_degree == 1
        assert last.in_degree == 1
        assert last.out_degree == 0

    def test_isolated_nodes(self):
        nodes = [make_node("a::f1"), make_node("a::f2")]
        edges = []

        analyzer = TopologyAnalyzer()
        result = analyzer.analyze(nodes, edges)

        for entry in result.entries:
            assert entry.in_degree == 0
            assert entry.out_degree == 0

    def test_topology_entries_have_all_fields(self):
        nodes = [make_node("a::f1")]
        edges = []

        analyzer = TopologyAnalyzer()
        result = analyzer.analyze(nodes, edges)

        entry = result.entries[0]
        assert isinstance(entry, TopologyEntry)
        assert hasattr(entry, "node_id")
        assert hasattr(entry, "in_degree")
        assert hasattr(entry, "out_degree")
        assert hasattr(entry, "topology_rank")
        assert hasattr(entry, "is_entry_point")
        assert hasattr(entry, "batch_assignment")
