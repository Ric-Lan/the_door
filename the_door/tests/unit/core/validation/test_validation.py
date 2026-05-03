"""Unit tests for output validation modules (TDD red phase).

Tests are written BEFORE implementation — all should fail until modules are implemented.
Covers: SchemaCheck (11.1), CoverageCheck (11.2), LanguageCheck (11.3),
        AnchorCheck (11.4), RelationCheck (11.5), OutputValidator (11.6).
"""
import json
from pathlib import Path

import pytest

from the_door.core.validation.schema_check import SchemaCheck
from the_door.core.validation.coverage_check import CoverageCheck
from the_door.core.validation.language_check import LanguageCheck
from the_door.core.validation.anchor_check import AnchorCheck
from the_door.core.validation.relation_check import RelationCheck
from the_door.core.validation.output_validator import OutputValidator
from the_door.models import CheckResult, ValidationResult


FIXTURES = Path(__file__).parent.parent.parent.parent / "fixtures"


def load_fixture(name):
    """Load a JSON fixture file by relative path under fixtures/."""
    with open(FIXTURES / name) as f:
        return json.load(f)


# === SchemaCheck tests (Task 11.1) ===


class TestSchemaCheck:
    """Unit tests for schema_check module."""

    def test_valid_output_passes(self):
        output = load_fixture("sample_l1_output/valid_output.json")
        checker = SchemaCheck()
        result = checker.check(output)
        assert isinstance(result, CheckResult)
        assert result.passed

    def test_missing_required_field_fails(self):
        output = load_fixture("sample_l1_output/invalid_missing_fields.json")
        checker = SchemaCheck()
        result = checker.check(output)
        assert not result.passed
        assert len(result.errors) > 0

    def test_invalid_enum_value_fails(self):
        output = load_fixture("sample_l1_output/valid_output.json")
        output["l1"]["features"][0]["trigger"] = "invalid_trigger"
        checker = SchemaCheck()
        result = checker.check(output)
        assert not result.passed

    def test_invalid_relation_type_detected(self):
        output = load_fixture("sample_l1_output/valid_output.json")
        output["l1"]["feature_relations"][0]["relation_type"] = "unknown"
        checker = SchemaCheck()
        result = checker.check(output)
        assert not result.passed


# === CoverageCheck tests (Task 11.2) ===


class TestCoverageCheck:
    """Unit tests for coverage_check module."""

    def test_complete_coverage_passes(self):
        output = load_fixture("sample_l1_output/valid_output.json")
        structure = load_fixture("sample_structure_json/python_simple.json")
        checker = CoverageCheck()
        result = checker.check(output, structure)
        assert isinstance(result, CheckResult)
        assert result.passed

    def test_incomplete_coverage_returns_uncovered(self):
        output = load_fixture("sample_l1_output/invalid_incomplete_coverage.json")
        structure = load_fixture("sample_structure_json/python_simple.json")
        checker = CoverageCheck()
        result = checker.check(output, structure)
        assert not result.passed
        assert len(result.details["uncovered_nodes"]) > 0

    def test_all_nodes_in_unclassified_passes(self):
        structure = load_fixture("sample_structure_json/python_simple.json")
        all_node_ids = [n["node_id"] for n in structure["nodes"]]
        output = {
            "l1": {
                "summary": "A system.",
                "features": [],
                "feature_relations": [],
                "unclassified_nodes": all_node_ids,
                "infrastructure_nodes": [],
            }
        }
        checker = CoverageCheck()
        result = checker.check(output, structure)
        assert result.passed


# === LanguageCheck tests (Task 11.3) ===


class TestLanguageCheck:
    """Unit tests for language_check module."""

    def test_clean_output_passes(self):
        output = load_fixture("sample_l1_output/valid_output.json")
        checker = LanguageCheck()
        result = checker.check(output)
        assert isinstance(result, CheckResult)
        assert result.passed

    def test_service_in_label_detected(self):
        output = load_fixture("sample_l1_output/invalid_prohibited_terms.json")
        checker = LanguageCheck()
        result = checker.check(output)
        assert not result.passed
        assert any("Service" in e for e in result.errors)

    def test_controller_in_description_detected(self):
        output = load_fixture("sample_l1_output/invalid_prohibited_terms.json")
        checker = LanguageCheck()
        result = checker.check(output)
        assert not result.passed
        assert any("Controller" in e for e in result.errors)

    def test_case_insensitive_matching(self):
        output = load_fixture("sample_l1_output/valid_output.json")
        output["l1"]["features"][0]["label"] = "the handler for requests"
        checker = LanguageCheck()
        result = checker.check(output)
        assert not result.passed

    def test_multiple_prohibited_terms_all_reported(self):
        output = load_fixture("sample_l1_output/invalid_prohibited_terms.json")
        checker = LanguageCheck()
        result = checker.check(output)
        assert not result.passed
        # The fixture has "Service" in label and "Controller", "API", "Endpoint" in description
        assert len(result.errors) >= 2


# === AnchorCheck tests (Task 11.4) ===


class TestAnchorCheck:
    """Unit tests for anchor_check module."""

    def test_valid_source_nodes_pass(self):
        output = load_fixture("sample_l1_output/valid_output.json")
        structure = load_fixture("sample_structure_json/python_simple.json")
        checker = AnchorCheck()
        result = checker.check(output, structure)
        assert isinstance(result, CheckResult)
        assert result.passed

    def test_hallucinated_node_flagged(self):
        output = load_fixture("sample_l1_output/invalid_hallucinated_nodes.json")
        structure = load_fixture("sample_structure_json/python_simple.json")
        checker = AnchorCheck()
        result = checker.check(output, structure)
        assert not result.passed
        assert any("DOES_NOT_EXIST" in e for e in result.errors)

    def test_empty_source_nodes_flagged(self):
        output = load_fixture("sample_l1_output/valid_output.json")
        output["l1"]["features"][0]["source_nodes"] = []
        structure = load_fixture("sample_structure_json/python_simple.json")
        checker = AnchorCheck()
        result = checker.check(output, structure)
        assert not result.passed


# === RelationCheck tests (Task 11.5) ===


class TestRelationCheck:
    """Unit tests for relation_check module."""

    def test_static_relation_with_edge_path_passes(self):
        output = load_fixture("sample_l1_output/valid_output.json")
        # Set up a static relation between features whose source_nodes are connected
        output["l1"]["feature_relations"] = [
            {
                "from": "feat-auth",
                "to": "feat-cleanup",
                "relation": "Auth triggers cleanup",
                "relation_type": "static",
            }
        ]
        structure = load_fixture("sample_structure_json/python_simple.json")
        # Add edge connecting their source nodes
        structure["edges"].append(
            {
                "from": "app.py::login",
                "to": "tasks.py::schedule_cleanup",
                "type": "calls",
            }
        )
        checker = RelationCheck()
        result = checker.check(output, structure)
        assert result.passed

    def test_static_relation_no_path_flagged(self):
        output = load_fixture(
            "sample_l1_output/invalid_static_relation_no_path.json"
        )
        structure = load_fixture("sample_structure_json/python_simple.json")
        checker = RelationCheck()
        result = checker.check(output, structure)
        assert not result.passed

    def test_inferred_relation_with_reason_passes(self):
        output = load_fixture("sample_l1_output/valid_output.json")
        structure = load_fixture("sample_structure_json/python_simple.json")
        checker = RelationCheck()
        result = checker.check(output, structure)
        assert isinstance(result, CheckResult)
        assert result.passed

    def test_inferred_relation_missing_reason_flagged(self):
        output = load_fixture(
            "sample_l1_output/invalid_inferred_missing_reason.json"
        )
        structure = load_fixture("sample_structure_json/python_simple.json")
        checker = RelationCheck()
        result = checker.check(output, structure)
        assert not result.passed

    def test_inferred_relation_referencing_nonexistent_feature_flagged(self):
        output = load_fixture("sample_l1_output/valid_output.json")
        output["l1"]["feature_relations"] = [
            {
                "from": "feat-auth",
                "to": "feat-nonexistent",
                "relation": "Some relation",
                "relation_type": "inferred",
                "inferred_reason": "Some reason",
            }
        ]
        structure = load_fixture("sample_structure_json/python_simple.json")
        checker = RelationCheck()
        result = checker.check(output, structure)
        assert not result.passed


# === OutputValidator orchestrator tests (Task 11.6) ===


class TestOutputValidator:
    """Unit tests for output_validator orchestrator."""

    def test_all_checks_pass(self):
        output = load_fixture("sample_l1_output/valid_output.json")
        structure = load_fixture("sample_structure_json/python_simple.json")
        validator = OutputValidator()
        result = validator.validate(output, structure)
        assert isinstance(result, ValidationResult)
        assert result.passed

    def test_single_check_fails_overall_fails(self):
        output = load_fixture("sample_l1_output/invalid_prohibited_terms.json")
        structure = load_fixture("sample_structure_json/python_simple.json")
        validator = OutputValidator()
        result = validator.validate(output, structure)
        assert not result.passed

    def test_multiple_failures_all_reported(self):
        output = load_fixture("sample_l1_output/invalid_hallucinated_nodes.json")
        structure = load_fixture("sample_structure_json/python_simple.json")
        validator = OutputValidator()
        result = validator.validate(output, structure)
        assert not result.passed
        # Should have at least anchor failure
        assert not result.anchor_result.passed

    def test_returns_validation_result_with_all_sub_results(self):
        output = load_fixture("sample_l1_output/valid_output.json")
        structure = load_fixture("sample_structure_json/python_simple.json")
        validator = OutputValidator()
        result = validator.validate(output, structure)
        assert hasattr(result, "schema_result")
        assert hasattr(result, "coverage_result")
        assert hasattr(result, "language_result")
        assert hasattr(result, "anchor_result")
        assert hasattr(result, "relation_result")
