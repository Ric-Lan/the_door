"""Unit tests for L1.5 validation extensions.

Tests are written BEFORE implementation (TDD red phase).
"""
from __future__ import annotations

import pytest

from the_door.core.validation.schema_check import SchemaCheck
from the_door.core.validation.output_validator import OutputValidator
from the_door.core.validation.language_check import LanguageCheck


class TestL15SchemaValidation:
    """Unit tests for L1.5 schema validation."""

    def test_valid_l1_5_passes_schema(self):
        """Valid L1.5 output passes schema check."""
        output = {
            "l1_5": {
                "blocks": [
                    {
                        "block_id": "blk-auth",
                        "label": "Authentication gateway handling user identity",
                        "responsibility": "Manages sign-in flow",
                        "trigger_mechanism": "User submits credentials",
                        "related_features": ["feat-auth"],
                    }
                ],
                "block_relations": [],
                "infrastructure_block": {"label": "System Infrastructure", "components": []},
            }
        }
        checker = SchemaCheck()
        result = checker.check_l1_5(output)
        assert result.passed

    def test_missing_block_id_fails(self):
        """Missing block_id field → schema check fails with specific error."""
        output = {
            "l1_5": {
                "blocks": [
                    {
                        "label": "Auth block",
                        "responsibility": "Auth",
                        "trigger_mechanism": "Login",
                        "related_features": [],
                    }
                ],
                "block_relations": [],
                "infrastructure_block": {"label": "Infra", "components": []},
            }
        }
        checker = SchemaCheck()
        result = checker.check_l1_5(output)
        assert not result.passed
        assert any("block_id" in e for e in result.errors)

    def test_dangling_block_id_in_relations_fails(self):
        """Dangling block_id in block_relations → cross-reference error."""
        output = {
            "l1_5": {
                "blocks": [
                    {
                        "block_id": "blk-a",
                        "label": "Block A with functional description",
                        "responsibility": "Does A",
                        "trigger_mechanism": "Trigger A",
                        "related_features": [],
                    }
                ],
                "block_relations": [
                    {
                        "from": "blk-a",
                        "to": "blk-nonexistent",
                        "relation": "Dangling",
                        "relation_type": "static",
                        "inferred_reason": None,
                    }
                ],
                "infrastructure_block": {"label": "Infra", "components": []},
            }
        }
        validator = OutputValidator()
        result = validator.check_l1_5_cross_references(output)
        assert not result.passed

    def test_dangling_feature_id_in_related_features_fails(self):
        """Dangling feature_id in related_features → cross-reference error."""
        l1_5_output = {
            "l1_5": {
                "blocks": [
                    {
                        "block_id": "blk-a",
                        "label": "Block A with functional description",
                        "responsibility": "Does A",
                        "trigger_mechanism": "Trigger A",
                        "related_features": ["feat-nonexistent"],
                    }
                ],
                "block_relations": [],
                "infrastructure_block": {"label": "Infra", "components": []},
            }
        }
        l1_output = {
            "l1": {
                "summary": "Test",
                "features": [
                    {
                        "feature_id": "feat-auth",
                        "label": "Auth",
                        "description": "Auth desc",
                        "trigger": "user_action",
                        "trigger_description": "Login",
                        "confidence": "high",
                        "confidence_reason": "Clear",
                        "source_nodes": ["app.py::login"],
                    }
                ],
                "feature_relations": [],
                "unclassified_nodes": [],
                "infrastructure_nodes": [],
            }
        }
        validator = OutputValidator()
        result = validator.check_l1_5_cross_references(l1_5_output, l1_output=l1_output)
        assert not result.passed

    def test_valid_l1_5_with_infrastructure_block_passes(self):
        """Valid L1.5 with infrastructure_block → passes all checks."""
        output = {
            "l1_5": {
                "blocks": [
                    {
                        "block_id": "blk-main",
                        "label": "Main application handling request routing",
                        "responsibility": "Routes requests",
                        "trigger_mechanism": "HTTP request received",
                        "related_features": ["feat-auth"],
                    }
                ],
                "block_relations": [],
                "infrastructure_block": {
                    "label": "System Infrastructure",
                    "components": ["config.py::load_settings", "utils.py::logger"],
                },
            }
        }
        checker = SchemaCheck()
        result = checker.check_l1_5(output)
        assert result.passed


class TestL15LanguageCheck:
    """Unit tests for L1.5 language check (relaxed rules)."""

    def test_bare_technical_term_fails(self):
        """Bare technical term in block label → language check fails."""
        output = {
            "l1_5": {
                "blocks": [
                    {
                        "block_id": "blk-a",
                        "label": "Controller",
                        "responsibility": "Controls things",
                        "trigger_mechanism": "Request",
                        "related_features": [],
                    }
                ],
                "block_relations": [],
                "infrastructure_block": {"label": "Infra", "components": []},
            }
        }
        checker = LanguageCheck()
        result = checker.check_l1_5(output)
        assert not result.passed

    def test_technical_term_with_functional_description_passes(self):
        """Technical term + functional description in block label → passes (relaxed rule)."""
        output = {
            "l1_5": {
                "blocks": [
                    {
                        "block_id": "blk-a",
                        "label": "Controller handling user authentication and session management",
                        "responsibility": "Manages auth",
                        "trigger_mechanism": "Login request",
                        "related_features": [],
                    }
                ],
                "block_relations": [],
                "infrastructure_block": {"label": "Infra", "components": []},
            }
        }
        checker = LanguageCheck()
        result = checker.check_l1_5(output)
        assert result.passed
