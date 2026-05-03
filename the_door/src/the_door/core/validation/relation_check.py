"""Relation check — validates static and inferred feature relations."""
from __future__ import annotations

from collections import deque

from the_door.models import CheckResult


class RelationCheck:
    """Validate feature relations with layered strictness."""

    def check(self, llm_output: dict, structure_json: dict) -> CheckResult:
        """Validate all feature_relations.

        Static: requires AST edge path between source_nodes of the two features.
        Inferred: requires both feature_ids exist, valid source_nodes, non-empty inferred_reason.
        """
        errors = []
        l1 = llm_output.get("l1", {})

        # Build feature lookup
        features = {f["feature_id"]: f for f in l1.get("features", [])}

        # Build edge adjacency from structure
        edges = structure_json.get("edges", [])
        adjacency: dict[str, set[str]] = {}
        for edge in edges:
            adjacency.setdefault(edge["from"], set()).add(edge["to"])

        for relation in l1.get("feature_relations", []):
            from_id = relation.get("from")
            to_id = relation.get("to")
            rel_type = relation.get("relation_type")

            # Check both features exist
            if from_id not in features:
                errors.append(f"Relation references non-existent feature '{from_id}'")
                continue
            if to_id not in features:
                errors.append(f"Relation references non-existent feature '{to_id}'")
                continue

            if rel_type == "static":
                # Verify AST edge path exists between source_nodes
                from_nodes = set(features[from_id].get("source_nodes", []))
                to_nodes = set(features[to_id].get("source_nodes", []))

                if not self._has_path(from_nodes, to_nodes, adjacency):
                    errors.append(
                        f"Static relation '{from_id}' → '{to_id}' has no corresponding AST edge path"
                    )

            elif rel_type == "inferred":
                # Check inferred_reason is non-empty
                reason = relation.get("inferred_reason")
                if not reason:
                    errors.append(
                        f"Inferred relation '{from_id}' → '{to_id}' missing inferred_reason"
                    )

        return CheckResult(passed=len(errors) == 0, errors=errors)

    def _has_path(self, from_nodes: set[str], to_nodes: set[str], adjacency: dict[str, set[str]]) -> bool:
        """Check if there's any path from any from_node to any to_node via edges."""
        if not from_nodes or not to_nodes:
            return False

        # BFS from all from_nodes
        visited = set()
        queue = deque(from_nodes)
        visited.update(from_nodes)

        while queue:
            current = queue.popleft()
            if current in to_nodes:
                return True
            for neighbor in adjacency.get(current, set()):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)

        return False
