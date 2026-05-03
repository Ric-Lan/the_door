"""Topology analyzer — orchestrates graph building, entry point detection, and batch assignment."""
from __future__ import annotations

from the_door.models import ASTNode, Edge, TopologyEntry, TopologyResult
from the_door.core.topology.graph_builder import GraphBuilder
from the_door.core.topology.entry_point_detector import EntryPointDetector
from the_door.core.topology.batch_assigner import BatchAssigner


class TopologyAnalyzer:
    """Orchestrate topology analysis: graph -> degrees -> entry points -> batches -> ranks."""

    def __init__(self) -> None:
        self._graph_builder = GraphBuilder()
        self._entry_detector = EntryPointDetector()
        self._batch_assigner = BatchAssigner()

    def analyze(self, nodes: list[ASTNode], edges: list[Edge]) -> TopologyResult:
        """Compute full topology analysis for all nodes.

        Must complete in < 1 second for up to 1000 nodes.
        """
        if not nodes:
            return TopologyResult(entries=[])

        # Step 1: Build graph
        graph = self._graph_builder.build(nodes, edges)

        # Step 2: Compute degrees
        in_degrees: dict[str, int] = {}
        out_degrees: dict[str, int] = {}
        for node in nodes:
            in_degrees[node.node_id] = graph.in_degree(node.node_id)
            out_degrees[node.node_id] = graph.out_degree(node.node_id)

        # Step 3: Detect entry points
        entry_points: set[str] = set()
        for node in nodes:
            if self._entry_detector.is_entry_point(
                node, in_degrees[node.node_id], out_degrees[node.node_id]
            ):
                entry_points.add(node.node_id)

        # Step 4: Assign batches
        batches = self._batch_assigner.assign_batches(nodes, in_degrees, entry_points)

        # Step 5: Compute topology ranks
        # Entry points first (sorted by out_degree descending), then non-entry (sorted by in_degree descending)
        entry_nodes = [n for n in nodes if n.node_id in entry_points]
        non_entry_nodes = [n for n in nodes if n.node_id not in entry_points]

        entry_nodes.sort(key=lambda n: out_degrees[n.node_id], reverse=True)
        non_entry_nodes.sort(key=lambda n: in_degrees[n.node_id], reverse=True)

        ranked_nodes = entry_nodes + non_entry_nodes
        rank_map = {n.node_id: i + 1 for i, n in enumerate(ranked_nodes)}

        # Step 6: Build topology entries
        entries = []
        for node in nodes:
            entries.append(TopologyEntry(
                node_id=node.node_id,
                in_degree=in_degrees[node.node_id],
                out_degree=out_degrees[node.node_id],
                topology_rank=rank_map[node.node_id],
                is_entry_point=node.node_id in entry_points,
                batch_assignment=batches[node.node_id],
            ))

        return TopologyResult(entries=entries)
