"""Batch assigner — assigns reading batch numbers to nodes based on topology."""
from __future__ import annotations

import math

from the_door.models import ASTNode


class BatchAssigner:
    """Assign batch numbers for topology-guided LLM reading."""

    def assign_batches(
        self,
        nodes: list[ASTNode],
        in_degrees: dict[str, int],
        entry_points: set[str],
        max_batches: int = 5,
    ) -> dict[str, int]:
        """Assign batch numbers to all nodes.

        Rules:
        - Entry points -> batch 1 (always)
        - Remaining nodes sorted by descending in_degree -> distributed across batches 2..max_batches

        Returns dict mapping node_id -> batch_assignment.
        """
        if not nodes:
            return {}

        batches: dict[str, int] = {}

        # Entry points always get batch 1
        for node in nodes:
            if node.node_id in entry_points:
                batches[node.node_id] = 1

        # Non-entry nodes sorted by descending in_degree
        non_entry = [n for n in nodes if n.node_id not in entry_points]
        non_entry.sort(key=lambda n: in_degrees.get(n.node_id, 0), reverse=True)

        if not non_entry:
            return batches

        # Distribute across batches 2..max_batches
        available_batches = max_batches - 1  # Reserve batch 1 for entry points
        if available_batches <= 0:
            available_batches = 1

        nodes_per_batch = max(1, math.ceil(len(non_entry) / available_batches))

        for i, node in enumerate(non_entry):
            batch_num = min(2 + (i // nodes_per_batch), max_batches)
            batches[node.node_id] = batch_num

        return batches
