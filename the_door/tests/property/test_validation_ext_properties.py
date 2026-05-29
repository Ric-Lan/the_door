"""Property-based tests for validation extensions (Phase 1-full).

Tests are written BEFORE implementation (TDD red phase).
Uses Hypothesis to verify universal correctness properties for L1.5 and L2 validation.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from the_door.core.validation.schema_check import SchemaCheck
from the_door.core.validation.output_validator import OutputValidator
from the_door.core.validation.language_check import LanguageCheck, PROHIBITED_TERMS


# === Strategies ===

NODE_ID = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_.:/"),
    min_size=5,
    max_size=30,
).filter(lambda s: "::" in s and not s.startswith("::") and not s.endswith("::"))

BLOCK_ID = st.from_regex(r"blk-[a-z]{3,10}", fullmatch=True)

FEATURE_ID = st.from_regex(r"feat-[a-z]{3,10}", fullmatch=True)

MODULE_ID = st.from_regex(r"mod-[a-z]{3,10}", fullmatch=True)

CONFIDENCE = st.sampled_from(["high", "medium", "low"])

RELATION_TYPE = st.sampled_from(["static", "inferred"])

ANOMALY_TYPE = st.sampled_from(["dead_code", "logic_dead_end", "uncertain_boundary"])

# Labels that are clean (no bare technical terms)
CLEAN_LABEL = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "Z"), whitelist_characters=" ,-"),
    min_size=5,
    max_size=60,
).filter(lambda s: s.strip() and not any(
    term.lower() == word.lower()
    for term in PROHIBITED_TERMS
    for word in s.split()
))


# === Helpers ===


def make_valid_l1_5_output(
    blocks: list[dict],
    block_relations: list[dict] | None = None,
    infrastructure_block: dict | None = None,
) -> dict:
    """Create a valid L1.5 output dict."""
    return {
        "l1_5": {
            "blocks": blocks,
            "block_relations": block_relations or [],
            "infrastructure_block": infrastructure_block or {"label": "System Infrastructure", "components": []},
        }
    }


def make_valid_l1_5_block(block_id: str, label: str = "Valid functional label", related_features: list[str] | None = None) -> dict:
    """Create a valid L1.5 block dict."""
    return {
        "block_id": block_id,
        "label": label,
        "responsibility": "Handles some responsibility",
        "trigger_mechanism": "Activated by some trigger",
        "related_features": related_features or [],
    }


def make_valid_l2_output(
    modules: list[dict],
    module_interactions: list[dict] | None = None,
    anomalies: list[dict] | None = None,
) -> dict:
    """Create a valid L2 output dict."""
    return {
        "l2": {
            "modules": modules,
            "module_interactions": module_interactions or [],
            "anomalies": anomalies or [],
        }
    }


def make_valid_l2_module(module_id: str, source_nodes: list[str] | None = None) -> dict:
    """Create a valid L2 module dict."""
    return {
        "module_id": module_id,
        "label": "Valid module label",
        "source_nodes": source_nodes or ["file.py::func_1"],
        "confidence": "high",
        "confidence_reason": "Clear module boundary",
    }


def make_structure_json(node_ids: list[str]) -> dict:
    """Create a minimal Structure JSON with given node_ids."""
    return {
        "files": [{"path": "file.py", "language": "python"}],
        "nodes": [
            {
                "node_id": nid,
                "type": "function",
                "name": nid.split("::")[-1],
                "file": nid.split("::")[0],
                "language": "python",
            }
            for nid in node_ids
        ],
        "edges": [],
        "topology": [],
    }


def make_l1_output_with_features(feature_ids: list[str]) -> dict:
    """Create a minimal L1 output with given feature_ids."""
    return {
        "l1": {
            "summary": "Test",
            "features": [
                {
                    "feature_id": fid,
                    "label": f"Feature {fid}",
                    "description": f"Description for {fid}",
                    "trigger": "user_action",
                    "trigger_description": "User action",
                    "confidence": "high",
                    "confidence_reason": "Clear",
                    "source_nodes": ["file.py::func_1"],
                }
                for fid in feature_ids
            ],
            "feature_relations": [],
            "unclassified_nodes": [],
            "infrastructure_nodes": [],
        }
    }


# ============================================================================
# Property 24: L1.5 schema validation accepts valid / rejects invalid
# ============================================================================


class TestProperty24L15SchemaValidation:
    """Property 24: L1.5 schema validation accepts valid and rejects invalid."""

    @settings(max_examples=50)
    @given(num_blocks=st.integers(min_value=1, max_value=5))
    def test_valid_l1_5_passes_schema(self, num_blocks):
        """Valid L1.5 output with all required fields passes schema check."""
        blocks = [
            make_valid_l1_5_block(f"blk-{chr(97 + i)}")
            for i in range(num_blocks)
        ]
        output = make_valid_l1_5_output(blocks)

        checker = SchemaCheck()
        result = checker.check_l1_5(output)
        assert result.passed, f"Valid L1.5 output should pass: {result.errors}"

    @settings(max_examples=50)
    @given(
        field_to_remove=st.sampled_from([
            "block_id", "label", "responsibility", "trigger_mechanism", "related_features"
        ])
    )
    def test_missing_required_field_fails_schema(self, field_to_remove):
        """L1.5 output missing a required block field fails schema check."""
        block = make_valid_l1_5_block("blk-test")
        del block[field_to_remove]
        output = make_valid_l1_5_output([block])

        checker = SchemaCheck()
        result = checker.check_l1_5(output)
        assert not result.passed, f"Missing '{field_to_remove}' should fail schema"

    @settings(max_examples=30)
    @given(
        relation_type=RELATION_TYPE,
        has_inferred_reason=st.booleans(),
    )
    def test_inferred_relation_requires_reason(self, relation_type, has_inferred_reason):
        """Inferred block_relations require non-empty inferred_reason."""
        blocks = [
            make_valid_l1_5_block("blk-a"),
            make_valid_l1_5_block("blk-b"),
        ]
        relation = {
            "from": "blk-a",
            "to": "blk-b",
            "relation": "Some relation",
            "relation_type": relation_type,
        }
        if has_inferred_reason:
            relation["inferred_reason"] = "Shared data store"
        else:
            relation["inferred_reason"] = None

        output = make_valid_l1_5_output(blocks, block_relations=[relation])

        checker = SchemaCheck()
        result = checker.check_l1_5(output)

        if relation_type == "inferred" and not has_inferred_reason:
            assert not result.passed, "Inferred relation without reason should fail"
        else:
            # Static relations don't require inferred_reason
            # Inferred with reason should pass
            if relation_type == "static" or has_inferred_reason:
                assert result.passed, f"Should pass: type={relation_type}, has_reason={has_inferred_reason}"


# ============================================================================
# Property 25: L1.5 cross-reference integrity
# ============================================================================


class TestProperty25L15CrossReference:
    """Property 25: Every block_id in block_relations exists in blocks,
    every feature_id in related_features exists in L1 features.
    """

    @settings(max_examples=50)
    @given(
        num_blocks=st.integers(min_value=2, max_value=5),
        use_valid_refs=st.booleans(),
    )
    def test_block_relation_references_valid_block_ids(self, num_blocks, use_valid_refs):
        """Block relations reference only existing block_ids."""
        block_ids = [f"blk-{chr(97 + i)}" for i in range(num_blocks)]
        blocks = [make_valid_l1_5_block(bid) for bid in block_ids]

        if use_valid_refs:
            relation = {
                "from": block_ids[0],
                "to": block_ids[1],
                "relation": "Valid relation",
                "relation_type": "static",
                "inferred_reason": None,
            }
        else:
            relation = {
                "from": block_ids[0],
                "to": "blk-nonexistent",
                "relation": "Dangling relation",
                "relation_type": "static",
                "inferred_reason": None,
            }

        output = make_valid_l1_5_output(blocks, block_relations=[relation])

        validator = OutputValidator()
        result = validator.check_l1_5_cross_references(output)

        if use_valid_refs:
            assert result.passed, "Valid block references should pass"
        else:
            assert not result.passed, "Dangling block_id should fail"

    @settings(max_examples=50)
    @given(use_valid_feature_refs=st.booleans())
    def test_related_features_reference_valid_feature_ids(self, use_valid_feature_refs):
        """related_features reference only existing L1 feature_ids."""
        feature_ids = ["feat-auth", "feat-users"]
        l1_output = make_l1_output_with_features(feature_ids)

        if use_valid_feature_refs:
            block = make_valid_l1_5_block("blk-a", related_features=["feat-auth"])
        else:
            block = make_valid_l1_5_block("blk-a", related_features=["feat-nonexistent"])

        l1_5_output = make_valid_l1_5_output([block])

        validator = OutputValidator()
        result = validator.check_l1_5_cross_references(l1_5_output, l1_output=l1_output)

        if use_valid_feature_refs:
            assert result.passed, "Valid feature references should pass"
        else:
            assert not result.passed, "Dangling feature_id should fail"


# ============================================================================
# Property 27: L2 schema validation accepts valid / rejects invalid
# ============================================================================


class TestProperty27L2SchemaValidation:
    """Property 27: L2 schema validation accepts valid and rejects invalid."""

    @settings(max_examples=50)
    @given(num_modules=st.integers(min_value=1, max_value=5))
    def test_valid_l2_passes_schema(self, num_modules):
        """Valid L2 output with all required fields passes schema check."""
        modules = [
            make_valid_l2_module(f"mod-{chr(97 + i)}")
            for i in range(num_modules)
        ]
        output = make_valid_l2_output(modules)

        checker = SchemaCheck()
        result = checker.check_l2(output)
        assert result.passed, f"Valid L2 output should pass: {result.errors}"

    @settings(max_examples=30)
    @given(anomaly_type=st.text(min_size=3, max_size=20, alphabet=st.characters(whitelist_categories=("L",))))
    def test_invalid_anomaly_type_fails_schema(self, anomaly_type):
        """Invalid anomaly_type enum value fails schema check."""
        assume(anomaly_type not in ("dead_code", "logic_dead_end", "uncertain_boundary"))

        modules = [make_valid_l2_module("mod-a")]
        anomalies = [{
            "anomaly_type": anomaly_type,
            "affected_node_ids": ["file.py::func_1"],
            "explanation": "Some explanation",
            "confidence": "high",
        }]
        output = make_valid_l2_output(modules, anomalies=anomalies)

        checker = SchemaCheck()
        result = checker.check_l2(output)
        assert not result.passed, f"Invalid anomaly_type '{anomaly_type}' should fail"

    @settings(max_examples=30)
    @given(valid_type=ANOMALY_TYPE)
    def test_valid_anomaly_types_pass_schema(self, valid_type):
        """Valid anomaly_type enum values pass schema check."""
        modules = [make_valid_l2_module("mod-a")]
        anomalies = [{
            "anomaly_type": valid_type,
            "affected_node_ids": ["file.py::func_1"],
            "explanation": "Some explanation",
            "confidence": "high",
        }]
        output = make_valid_l2_output(modules, anomalies=anomalies)

        checker = SchemaCheck()
        result = checker.check_l2(output)
        assert result.passed, f"Valid anomaly_type '{valid_type}' should pass"

    @settings(max_examples=30)
    @given(
        field_to_remove=st.sampled_from([
            "module_id", "label", "source_nodes", "confidence", "confidence_reason"
        ])
    )
    def test_missing_module_field_fails_schema(self, field_to_remove):
        """L2 output missing a required module field fails schema check."""
        module = make_valid_l2_module("mod-a")
        del module[field_to_remove]
        output = make_valid_l2_output([module])

        checker = SchemaCheck()
        result = checker.check_l2(output)
        assert not result.passed, f"Missing '{field_to_remove}' should fail schema"


# ============================================================================
# Property 28: L2 anomaly node reference integrity
# ============================================================================


class TestProperty28L2AnomalyReferences:
    """Property 28: Dangling node_ids in anomaly affected_node_ids are flagged."""

    @settings(max_examples=50)
    @given(use_valid_refs=st.booleans())
    def test_anomaly_node_references_validated(self, use_valid_refs):
        """Anomaly affected_node_ids must reference existing Structure JSON nodes."""
        real_nodes = ["file.py::func_1", "file.py::func_2"]
        structure = make_structure_json(real_nodes)

        if use_valid_refs:
            affected = ["file.py::func_1"]
        else:
            affected = ["nonexistent.py::ghost_func"]

        modules = [make_valid_l2_module("mod-a", source_nodes=real_nodes)]
        anomalies = [{
            "anomaly_type": "dead_code",
            "affected_node_ids": affected,
            "explanation": "No callers found",
            "confidence": "high",
        }]
        output = make_valid_l2_output(modules, anomalies=anomalies)

        validator = OutputValidator()
        result = validator.check_l2_anomaly_references(output, structure)

        if use_valid_refs:
            assert result.passed, "Valid node references should pass"
        else:
            assert not result.passed, "Dangling node_id should fail"


# ============================================================================
# Property 29: L1.5 language check with relaxed rules
# ============================================================================


class TestProperty29L15LanguageCheck:
    """Property 29: L1.5 block labels allow technical terms WITH functional context."""

    @settings(max_examples=50)
    @given(clean_label=CLEAN_LABEL)
    def test_clean_label_passes(self, clean_label):
        """Block label without prohibited terms passes language check."""
        block = make_valid_l1_5_block("blk-test", label=clean_label)
        output = make_valid_l1_5_output([block])

        checker = LanguageCheck()
        result = checker.check_l1_5(output)
        assert result.passed, f"Clean label should pass: {result.errors}"

    @settings(max_examples=30)
    @given(
        term=st.sampled_from([
            "Service", "Handler", "Controller", "Middleware", "Router"
        ])
    )
    def test_bare_technical_term_fails(self, term):
        """Block label that IS just a bare technical term fails."""
        # Bare term: just the term itself or with minimal non-functional context
        bare_label = f"{term}"
        block = make_valid_l1_5_block("blk-test", label=bare_label)
        output = make_valid_l1_5_output([block])

        checker = LanguageCheck()
        result = checker.check_l1_5(output)
        assert not result.passed, f"Bare technical term '{term}' should fail"

    @settings(max_examples=30)
    @given(
        term=st.sampled_from([
            "Service", "Handler", "Controller", "Middleware", "Router"
        ]),
        functional_desc=st.builds(
            lambda w1, w2, w3: f"{w1} {w2} {w3}",
            w1=st.sampled_from(["handling", "managing", "providing", "processing", "orchestrating"]),
            w2=st.sampled_from(["user", "data", "request", "session", "payment"]),
            w3=st.sampled_from(["authentication", "validation", "management", "processing", "routing"]),
        ),
    )
    def test_technical_term_with_functional_description_passes(self, term, functional_desc):
        """Block label with technical term + functional description passes (relaxed rule)."""
        # Technical term + functional context: "AuthController handling user identity verification"
        label_with_context = f"{term} {functional_desc}"
        block = make_valid_l1_5_block("blk-test", label=label_with_context)
        output = make_valid_l1_5_output([block])

        checker = LanguageCheck()
        result = checker.check_l1_5(output)
        assert result.passed, (
            f"Technical term '{term}' with functional description should pass (relaxed rule)"
        )
