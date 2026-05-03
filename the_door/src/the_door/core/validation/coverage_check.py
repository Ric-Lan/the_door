"""Coverage check — verifies all AST nodes are accounted for in LLM output."""
from __future__ import annotations

from the_door.models import CheckResult


class CoverageCheck:
    """Verify that LLM output covers all nodes from Structure JSON."""

    def check(self, llm_output: dict, structure_json: dict) -> CheckResult:
        """Check that union of source_nodes + unclassified + infrastructure = all node_ids.

        Returns uncovered node_ids if incomplete.
        """
        # Get all node_ids from structure
        all_node_ids = {n["node_id"] for n in structure_json.get("nodes", [])}

        # Collect covered nodes from LLM output
        l1 = llm_output.get("l1", {})
        covered = set()

        # From features' source_nodes
        for feature in l1.get("features", []):
            for node_id in feature.get("source_nodes", []):
                covered.add(node_id)

        # From unclassified_nodes
        for node_id in l1.get("unclassified_nodes", []):
            covered.add(node_id)

        # From infrastructure_nodes
        for node_id in l1.get("infrastructure_nodes", []):
            covered.add(node_id)

        # Compute uncovered
        uncovered = all_node_ids - covered

        if not uncovered:
            return CheckResult(passed=True)

        return CheckResult(
            passed=False,
            errors=[f"Uncovered nodes: {len(uncovered)} node(s) not accounted for"],
            details={"uncovered_nodes": sorted(uncovered)},
        )
