"""Output validator — orchestrates all 5 validation checks."""
from __future__ import annotations

from the_door.models import CheckResult, ValidationResult
from the_door.core.validation.schema_check import SchemaCheck
from the_door.core.validation.coverage_check import CoverageCheck
from the_door.core.validation.language_check import LanguageCheck
from the_door.core.validation.anchor_check import AnchorCheck
from the_door.core.validation.relation_check import RelationCheck


class OutputValidator:
    """Run all 5 validation checks and return aggregated result."""

    def __init__(self):
        self._schema_check = SchemaCheck()
        self._coverage_check = CoverageCheck()
        self._language_check = LanguageCheck()
        self._anchor_check = AnchorCheck()
        self._relation_check = RelationCheck()

    def validate(self, llm_output: dict, structure_json: dict) -> ValidationResult:
        """Run all validation checks and return aggregated result.

        All checks run regardless of earlier failures (no short-circuit).
        """
        schema_result = self._schema_check.check(llm_output)
        coverage_result = self._coverage_check.check(llm_output, structure_json)
        language_result = self._language_check.check(llm_output)
        anchor_result = self._anchor_check.check(llm_output, structure_json)
        relation_result = self._relation_check.check(llm_output, structure_json)

        all_passed = all([
            schema_result.passed,
            coverage_result.passed,
            language_result.passed,
            anchor_result.passed,
            relation_result.passed,
        ])

        return ValidationResult(
            passed=all_passed,
            schema_result=schema_result,
            coverage_result=coverage_result,
            language_result=language_result,
            anchor_result=anchor_result,
            relation_result=relation_result,
        )

    # === Phase 1-full extensions ===

    def check_l1_5_cross_references(
        self, l1_5_output: dict, l1_output: dict | None = None
    ) -> CheckResult:
        """Verify L1.5 cross-reference integrity.

        - Every block_id in block_relations exists in blocks array
        - Every feature_id in related_features exists in L1 features (if l1_output provided)
        """
        errors: list[str] = []
        l1_5 = l1_5_output.get("l1_5", {})

        # Collect valid block_ids
        blocks = l1_5.get("blocks", [])
        valid_block_ids = {b["block_id"] for b in blocks if "block_id" in b}

        # Check block_relations reference valid block_ids
        for rel in l1_5.get("block_relations", []):
            from_id = rel.get("from", "")
            to_id = rel.get("to", "")
            if from_id not in valid_block_ids:
                errors.append(f"block_relations 'from' references non-existent block_id: '{from_id}'")
            if to_id not in valid_block_ids:
                errors.append(f"block_relations 'to' references non-existent block_id: '{to_id}'")

        # Check related_features reference valid L1 feature_ids
        if l1_output is not None:
            l1 = l1_output.get("l1", {})
            valid_feature_ids = {
                f["feature_id"] for f in l1.get("features", []) if "feature_id" in f
            }

            for block in blocks:
                for feat_id in block.get("related_features", []):
                    if feat_id not in valid_feature_ids:
                        errors.append(
                            f"Block '{block.get('block_id', '?')}' references non-existent "
                            f"feature_id in related_features: '{feat_id}'"
                        )

        return CheckResult(passed=len(errors) == 0, errors=errors)

    def check_l2_anomaly_references(
        self, l2_output: dict, structure_json: dict
    ) -> CheckResult:
        """Verify L2 anomaly node reference integrity.

        Every node_id in anomaly affected_node_ids must exist in Structure JSON.
        """
        errors: list[str] = []

        # Collect valid node_ids from structure
        nodes = structure_json.get("nodes", [])
        valid_node_ids = {n["node_id"] for n in nodes if "node_id" in n}

        l2 = l2_output.get("l2", {})
        for anomaly in l2.get("anomalies", []):
            for node_id in anomaly.get("affected_node_ids", []):
                if node_id not in valid_node_ids:
                    errors.append(
                        f"Anomaly '{anomaly.get('anomaly_type', '?')}' references "
                        f"non-existent node_id: '{node_id}'"
                    )

        return CheckResult(passed=len(errors) == 0, errors=errors)
