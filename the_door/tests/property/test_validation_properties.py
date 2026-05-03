"""Property-based tests for output validation.

Tests are written BEFORE implementation (TDD red phase).
Uses Hypothesis to verify universal correctness properties.
"""
import json
from pathlib import Path

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from the_door.core.validation.schema_check import SchemaCheck
from the_door.core.validation.coverage_check import CoverageCheck
from the_door.core.validation.language_check import LanguageCheck, PROHIBITED_TERMS
from the_door.core.validation.anchor_check import AnchorCheck
from the_door.core.validation.relation_check import RelationCheck


# === Strategies ===

NODE_ID = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_.:/"),
    min_size=5, max_size=30
).filter(lambda s: "::" in s)

FEATURE_ID = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="-_"),
    min_size=3, max_size=20
)

CLEAN_TEXT = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "Z"), whitelist_characters=" ,.!?'-"),
    min_size=1, max_size=100
).filter(lambda s: not any(term.lower() in s.lower() for term in [
    "Service", "Handler", "Controller", "Loader", "IoC", "Middleware",
    "Decorator", "Class", "Module", "Import", "Endpoint", "Router",
    "Provider", "Factory", "Repository", "DAO", "ORM", "SDK", "API"
]))


def make_valid_feature(feature_id: str, source_nodes: list[str]) -> dict:
    """Create a minimal valid feature dict."""
    return {
        "feature_id": feature_id,
        "label": "A valid feature label",
        "description": "A valid feature description",
        "trigger": "user_action",
        "trigger_description": "When user performs action",
        "confidence": "high",
        "confidence_reason": "Clear from structure",
        "source_nodes": source_nodes,
        "needs_source_review": False,
        "review_reason": None,
    }


def make_valid_l1_output(features: list[dict], relations: list[dict] = None,
                         unclassified: list[str] = None, infrastructure: list[str] = None) -> dict:
    """Create a valid L1 output dict."""
    return {
        "l1": {
            "summary": "A system that does things.",
            "features": features,
            "feature_relations": relations or [],
            "unclassified_nodes": unclassified or [],
            "infrastructure_nodes": infrastructure or [],
        }
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
                "file": "file.py",
                "language": "python",
                "decorators": [],
                "parameters": [],
                "return_type": None,
                "docstring": None,
                "comments": [],
            }
            for nid in node_ids
        ],
        "edges": [],
        "topology": [],
    }


# === Property 8: Schema validation accepts valid / rejects invalid ===

class TestProperty8SchemaValidation:
    """Feature: the-door-phase-1-min, Property 8: Schema validation accepts valid output and rejects invalid output"""

    @settings(max_examples=50)
    @given(num_features=st.integers(min_value=1, max_value=5))
    def test_valid_output_passes_schema(self, num_features):
        """Valid L1 output with all required fields passes schema check.

        **Validates: Requirements 9.1, 9.3**
        """
        features = [
            make_valid_feature(f"feat-{i}", [f"file.py::func_{i}"])
            for i in range(num_features)
        ]
        output = make_valid_l1_output(features)

        checker = SchemaCheck()
        result = checker.check(output)
        assert result.passed, f"Valid output should pass: {result.errors}"

    @settings(max_examples=50)
    @given(field_to_remove=st.sampled_from([
        "description", "trigger", "confidence", "confidence_reason", "source_nodes"
    ]))
    def test_missing_required_field_fails_schema(self, field_to_remove):
        """L1 output missing a required field fails schema check.

        **Validates: Requirements 9.1, 9.3**
        """
        feature = make_valid_feature("feat-1", ["file.py::func_1"])
        del feature[field_to_remove]
        output = make_valid_l1_output([feature])

        checker = SchemaCheck()
        result = checker.check(output)
        assert not result.passed, f"Missing '{field_to_remove}' should fail schema"


# === Property 9: Coverage check detects uncovered nodes ===

class TestProperty9CoverageCheck:
    """Feature: the-door-phase-1-min, Property 9: Coverage check detects uncovered nodes"""

    @settings(max_examples=100)
    @given(
        total_nodes=st.integers(min_value=2, max_value=10),
        covered_fraction=st.floats(min_value=0.1, max_value=1.0),
    )
    def test_coverage_passes_iff_all_nodes_covered(self, total_nodes, covered_fraction):
        """Coverage passes iff union of source_nodes + unclassified + infrastructure = all node_ids.

        **Validates: Requirements 10.1, 10.2**
        """
        node_ids = [f"file.py::func_{i}" for i in range(total_nodes)]
        covered_count = max(1, int(total_nodes * covered_fraction))
        covered_nodes = node_ids[:covered_count]
        uncovered_nodes = node_ids[covered_count:]

        features = [make_valid_feature("feat-1", covered_nodes)]
        output = make_valid_l1_output(features)
        structure = make_structure_json(node_ids)

        checker = CoverageCheck()
        result = checker.check(output, structure)

        if covered_count == total_nodes:
            assert result.passed, "Full coverage should pass"
        else:
            assert not result.passed, "Incomplete coverage should fail"
            # Verify uncovered list matches
            assert set(result.details.get("uncovered_nodes", [])) == set(uncovered_nodes)


# === Property 10: Language check detects prohibited terms ===

class TestProperty10LanguageCheck:
    """Feature: the-door-phase-1-min, Property 10: Language check detects prohibited technical terms"""

    @settings(max_examples=50)
    @given(clean_label=CLEAN_TEXT, clean_desc=CLEAN_TEXT)
    def test_clean_text_passes_language_check(self, clean_label, clean_desc):
        """L1 output with no prohibited terms passes language check.

        **Validates: Requirements 11.1, 11.2**
        """
        feature = make_valid_feature("feat-1", ["file.py::func_1"])
        feature["label"] = clean_label
        feature["description"] = clean_desc
        output = make_valid_l1_output([feature])

        checker = LanguageCheck()
        result = checker.check(output)
        assert result.passed, f"Clean text should pass: {result.errors}"

    @settings(max_examples=50)
    @given(term=st.sampled_from([
        "Service", "Handler", "Controller", "Middleware", "Endpoint", "Router"
    ]))
    def test_prohibited_term_in_label_fails(self, term):
        """L1 output with prohibited term in label fails language check.

        **Validates: Requirements 11.1, 11.2**
        """
        feature = make_valid_feature("feat-1", ["file.py::func_1"])
        feature["label"] = f"The {term} for users"
        output = make_valid_l1_output([feature])

        checker = LanguageCheck()
        result = checker.check(output)
        assert not result.passed, f"'{term}' in label should fail"


# === Property 11: Anchor check detects hallucinated node references ===

class TestProperty11AnchorCheck:
    """Feature: the-door-phase-1-min, Property 11: Anchor check detects hallucinated node references"""

    @settings(max_examples=100)
    @given(
        num_real_nodes=st.integers(min_value=1, max_value=5),
        num_fake_nodes=st.integers(min_value=0, max_value=3),
    )
    def test_anchor_passes_iff_all_source_nodes_exist(self, num_real_nodes, num_fake_nodes):
        """Anchor check passes iff all source_nodes exist in Structure JSON.

        **Validates: Requirements 8.1, 8.2, 12.1, 12.2**
        """
        real_ids = [f"file.py::func_{i}" for i in range(num_real_nodes)]
        fake_ids = [f"FAKE::phantom_{i}" for i in range(num_fake_nodes)]

        source_nodes = real_ids + fake_ids
        features = [make_valid_feature("feat-1", source_nodes)]
        output = make_valid_l1_output(features)
        structure = make_structure_json(real_ids)

        checker = AnchorCheck()
        result = checker.check(output, structure)

        if num_fake_nodes == 0:
            assert result.passed, "All real nodes should pass anchor check"
        else:
            assert not result.passed, "Fake nodes should fail anchor check"


# === Property 12: Relation check validates static and inferred relations ===

class TestProperty12RelationCheck:
    """Feature: the-door-phase-1-min, Property 12: Relation check validates static and inferred relations at correct strictness levels"""

    @settings(max_examples=50)
    @given(has_edge_path=st.booleans())
    def test_static_relation_requires_ast_edge_path(self, has_edge_path):
        """Static relation passes iff AST edge path exists between source_nodes.

        **Validates: Requirements 8.3, 13.1, 13.2, 13.3, 13.4**
        """
        node_ids = ["file.py::func_a", "file.py::func_b"]
        features = [
            make_valid_feature("feat-a", ["file.py::func_a"]),
            make_valid_feature("feat-b", ["file.py::func_b"]),
        ]
        relations = [{
            "from": "feat-a",
            "to": "feat-b",
            "relation": "A triggers B",
            "relation_type": "static",
        }]
        output = make_valid_l1_output(features, relations)

        structure = make_structure_json(node_ids)
        if has_edge_path:
            structure["edges"] = [{"from": "file.py::func_a", "to": "file.py::func_b", "type": "calls"}]

        checker = RelationCheck()
        result = checker.check(output, structure)

        if has_edge_path:
            assert result.passed, "Static relation with edge path should pass"
        else:
            assert not result.passed, "Static relation without edge path should fail"

    @settings(max_examples=50)
    @given(has_reason=st.booleans())
    def test_inferred_relation_requires_non_empty_reason(self, has_reason):
        """Inferred relation passes iff inferred_reason is non-empty.

        **Validates: Requirements 8.3, 13.1, 13.2, 13.3, 13.4**
        """
        node_ids = ["file.py::func_a", "file.py::func_b"]
        features = [
            make_valid_feature("feat-a", ["file.py::func_a"]),
            make_valid_feature("feat-b", ["file.py::func_b"]),
        ]
        relations = [{
            "from": "feat-a",
            "to": "feat-b",
            "relation": "A relates to B",
            "relation_type": "inferred",
            "inferred_reason": "They share context" if has_reason else None,
        }]
        output = make_valid_l1_output(features, relations)
        structure = make_structure_json(node_ids)

        checker = RelationCheck()
        result = checker.check(output, structure)

        if has_reason:
            assert result.passed, "Inferred relation with reason should pass"
        else:
            assert not result.passed, "Inferred relation without reason should fail"
