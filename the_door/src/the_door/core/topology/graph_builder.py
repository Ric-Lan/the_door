"""Graph builder — constructs a networkx DiGraph from AST edges."""
from __future__ import annotations

import networkx as nx

from the_door.models import ASTNode, Edge


class GraphBuilder:
    """Build a networkx directed graph from AST nodes and edges."""

    def build(self, nodes: list[ASTNode], edges: list[Edge]) -> nx.MultiDiGraph:
        """Build a MultiDiGraph with all nodes and edges.

        All nodes are added even if they have no edges (isolated nodes).
        Uses MultiDiGraph to correctly count parallel/duplicate edges.
        """
        graph = nx.MultiDiGraph()

        # Add all nodes
        for node in nodes:
            graph.add_node(node.node_id)

        # Add edges (including duplicates)
        for edge in edges:
            if edge.from_node in graph and edge.to_node in graph:
                graph.add_edge(edge.from_node, edge.to_node, type=edge.type)

        return graph
