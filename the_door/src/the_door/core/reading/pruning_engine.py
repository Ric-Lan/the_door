"""Pruning engine — track high-confidence nodes and decide what to skip."""
from __future__ import annotations

from dataclasses import dataclass, field

from the_door.models import Edge


@dataclass
class PruningDecision:
    """Record of a pruning decision."""

    node_id: str
    batch: int
    reason: str  # "high_confidence" | "downstream_dependency"
    reinstated: bool = False
    reinstated_at_batch: int | None = None


class PruningEngine:
    """Track high-confidence nodes and decide what to skip in subsequent batches.

    Requires edge information to determine downstream dependencies of pruned nodes.
    A downstream dependency is only pruned if ALL its incoming edges come from
    already-pruned nodes (i.e., it has no other pending references).
    """

    def __init__(self, edges: list[Edge]) -> None:
        self._edges = edges
        self._pruned: set[str] = set()
        self._decisions: list[PruningDecision] = []
        # Build adjacency: from_node -> [to_node]
        self._downstream: dict[str, list[str]] = {}
        # Build reverse adjacency: to_node -> [from_node]
        self._upstream: dict[str, list[str]] = {}
        for edge in edges:
            self._downstream.setdefault(edge.from_node, []).append(edge.to_node)
            self._upstream.setdefault(edge.to_node, []).append(edge.from_node)

    def record_confidence(self, node_id: str, confidence: str, batch: int) -> None:
        """Record a node's confidence from LLM output.

        If confidence is 'high', marks the node as pruned and also marks
        downstream dependencies for pruning (unless they have other pending
        references from non-pruned nodes).
        """
        if confidence != "high":
            return

        # Prune the node itself
        self._pruned.add(node_id)
        self._decisions.append(
            PruningDecision(node_id=node_id, batch=batch, reason="high_confidence")
        )

        # Check downstream dependencies
        self._prune_downstream(node_id, batch)

    def _prune_downstream(self, pruned_node: str, batch: int) -> None:
        """Recursively prune downstream nodes that have no other pending refs."""
        for downstream in self._downstream.get(pruned_node, []):
            if downstream in self._pruned:
                continue  # Already pruned

            # Check if all upstream sources are pruned
            upstream_sources = self._upstream.get(downstream, [])
            all_sources_pruned = all(src in self._pruned for src in upstream_sources)

            if all_sources_pruned:
                self._pruned.add(downstream)
                self._decisions.append(
                    PruningDecision(
                        node_id=downstream,
                        batch=batch,
                        reason="downstream_dependency",
                    )
                )
                # Recursively check further downstream
                self._prune_downstream(downstream, batch)

    def should_prune(self, node_id: str) -> bool:
        """Check if a node should be skipped in the current batch."""
        return node_id in self._pruned

    def get_pruned_nodes(self) -> set[str]:
        """Return set of node_ids currently pruned."""
        return set(self._pruned)

    def reinstate(self, node_id: str, batch: int) -> bool:
        """Re-include a previously pruned node.

        Returns True if the node was reinstated, False if it wasn't pruned.
        """
        if node_id not in self._pruned:
            return False

        self._pruned.discard(node_id)

        # Update the decision record
        for decision in self._decisions:
            if decision.node_id == node_id and not decision.reinstated:
                decision.reinstated = True
                decision.reinstated_at_batch = batch
                break

        return True

    def get_decisions(self) -> list[PruningDecision]:
        """Return all pruning decisions for narrative chain recording."""
        return list(self._decisions)
