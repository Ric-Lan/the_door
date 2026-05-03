"""Anchor check — verifies every feature's source_nodes exist in Structure JSON."""
from __future__ import annotations

from the_door.models import CheckResult


class AnchorCheck:
    """Verify that every feature references real AST nodes (no hallucinations)."""

    def check(self, llm_output: dict, structure_json: dict) -> CheckResult:
        """Check that all source_nodes reference existing node_ids.

        Also verifies every feature has at least one source_node.
        """
        # Get valid node_ids from structure
        valid_ids = {n["node_id"] for n in structure_json.get("nodes", [])}

        errors = []
        l1 = llm_output.get("l1", {})

        for feature in l1.get("features", []):
            feature_id = feature.get("feature_id", "unknown")
            source_nodes = feature.get("source_nodes", [])

            # Check: feature must have at least one source_node
            if not source_nodes:
                errors.append(f"Feature '{feature_id}' has empty source_nodes (hallucination risk)")
                continue

            # Check: all source_nodes must exist in structure
            for node_id in source_nodes:
                if node_id not in valid_ids:
                    errors.append(
                        f"Feature '{feature_id}' references non-existent node '{node_id}' "
                        f"(hallucination anchor error)"
                    )

        return CheckResult(passed=len(errors) == 0, errors=errors)
