"""Unit tests for L2 validation extensions.

Tests are written BEFORE implementation (TDD red phase).
"""
from __future__ import annotations

import pytest

from the_door.core.validation.schema_check import SchemaCheck
from the_door.core.validation.output_validator import OutputValidator


class TestL2SchemaValidation:
    """Unit tests for L2 schema validation."""

    def test_valid_l2_passes_schema(self):
        """Valid L2 output passes schema check."""
        output = {
            "l2": {
                "modules": [
                    {
                        "module_id": "mod-auth",
                        "label": "Authentication Module",
                        "source_nodes": ["app.py::login"],
                        "confidence": "high",
                        "confidence_reason": "Clear module boundary",
                    }
                ],
                "module_interactions": [],
                "anomalies": [],
            }
        }
        checker = SchemaCheck()
        result = checker.check_l2(output)
        assert result.passed

    def test_invalid_anomaly_type_fails(self):
        """Invalid anomaly_type → schema check fails."""
        output = {
            "l2": {
                "modules": [
                    {
                        "module_id": "mod-a",
                        "label": "Module A",
                        "source_nodes": ["file.py::func"],
                        "confidence": "high",
                        "confidence_reason": "Clear",
                    }
                ],
                "module_interactions": [],
                "anomalies": [
                    {
                        "anomaly_type": "invalid_type",
                        "affected_node_ids": ["file.py::func"],
                        "explanation": "Test",
                        "confidence": "high",
                    }
                ],
            }
        }
        checker = SchemaCheck()
        result = checker.check_l2(output)
        assert not result.passed

    def test_valid_anomaly_types_pass(self):
        """Valid anomaly types (dead_code, logic_dead_end, uncertain_boundary) → passes."""
        for anomaly_type in ["dead_code", "logic_dead_end", "uncertain_boundary"]:
            output = {
                "l2": {
                    "modules": [
                        {
                            "module_id": "mod-a",
                            "label": "Module A",
                            "source_nodes": ["file.py::func"],
                            "confidence": "high",
                            "confidence_reason": "Clear",
                        }
                    ],
                    "module_interactions": [],
                    "anomalies": [
                        {
                            "anomaly_type": anomaly_type,
                            "affected_node_ids": ["file.py::func"],
                            "explanation": "Test explanation",
                            "confidence": "medium",
                        }
                    ],
                }
            }
            checker = SchemaCheck()
            result = checker.check_l2(output)
            assert result.passed, f"Valid anomaly_type '{anomaly_type}' should pass"

    def test_missing_required_fields_fails(self):
        """Missing required fields → schema check fails with specific error."""
        output = {
            "l2": {
                "modules": [
                    {
                        "module_id": "mod-a",
                        "label": "Module A",
                        # Missing: source_nodes, confidence, confidence_reason
                    }
                ],
                "module_interactions": [],
                "anomalies": [],
            }
        }
        checker = SchemaCheck()
        result = checker.check_l2(output)
        assert not result.passed


class TestL2AnomalyReferenceValidation:
    """Unit tests for L2 anomaly node reference checks."""

    def test_dangling_node_id_in_anomaly_fails(self):
        """Dangling node_id in anomaly affected_node_ids → anchor error."""
        output = {
            "l2": {
                "modules": [
                    {
                        "module_id": "mod-a",
                        "label": "Module A",
                        "source_nodes": ["file.py::func_1"],
                        "confidence": "high",
                        "confidence_reason": "Clear",
                    }
                ],
                "module_interactions": [],
                "anomalies": [
                    {
                        "anomaly_type": "dead_code",
                        "affected_node_ids": ["nonexistent.py::ghost"],
                        "explanation": "No callers",
                        "confidence": "high",
                    }
                ],
            }
        }
        structure = {
            "nodes": [
                {"node_id": "file.py::func_1", "type": "function", "name": "func_1", "file": "file.py", "language": "python"}
            ],
            "edges": [],
        }
        validator = OutputValidator()
        result = validator.check_l2_anomaly_references(output, structure)
        assert not result.passed

    def test_valid_anomaly_references_pass(self):
        """Valid anomaly node references → passes."""
        output = {
            "l2": {
                "modules": [
                    {
                        "module_id": "mod-a",
                        "label": "Module A",
                        "source_nodes": ["file.py::func_1"],
                        "confidence": "high",
                        "confidence_reason": "Clear",
                    }
                ],
                "module_interactions": [],
                "anomalies": [
                    {
                        "anomaly_type": "dead_code",
                        "affected_node_ids": ["file.py::func_1"],
                        "explanation": "No callers",
                        "confidence": "high",
                    }
                ],
            }
        }
        structure = {
            "nodes": [
                {"node_id": "file.py::func_1", "type": "function", "name": "func_1", "file": "file.py", "language": "python"}
            ],
            "edges": [],
        }
        validator = OutputValidator()
        result = validator.check_l2_anomaly_references(output, structure)
        assert result.passed
