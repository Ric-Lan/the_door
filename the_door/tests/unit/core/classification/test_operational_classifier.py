"""Unit tests for the operational classifier (Cut 1).

Pure path/filename classification of a ``node_id`` into operational vs
non-operational categories — zero-graph, deterministic. The default is
``operational`` (fact-finder: never hide a real node), so the classifier only
ever produces false negatives (a test in a weird location stays listed), never
false positives.
"""
from __future__ import annotations

import pytest

from the_door.core.classification.operational_classifier import (
    CAT_FIXTURE,
    CAT_OPERATIONAL,
    CAT_PROTOTYPE,
    CAT_SCRIPT,
    CAT_TEST,
    NON_OPERATIONAL,
    classify_node,
    is_operational,
)


@pytest.mark.parametrize(
    "node_id, expected",
    [
        # filename signals
        ("the_door/tests/unit/cli/test_x.py::test_foo", CAT_TEST),
        ("the_door/tests/unit/cli/widget_test.py::check", CAT_TEST),
        ("the_door/tests/conftest.py::fixture_x", CAT_TEST),
        # path signals
        ("the_door/tests/integration/flow.py::run", CAT_TEST),
        ("the_door/tests/fixtures/sample.py::data", CAT_TEST),  # /tests/ wins over /fixtures/
        ("some/pkg/fixtures/blob.py::payload", CAT_FIXTURE),
        ("scripts/dogfood_x.py::run", CAT_SCRIPT),
        ("tooling/scripts/release.py::main", CAT_SCRIPT),
        ("docs/frontend-local-version-viewer/prototype/flow.js::buildWalk", CAT_PROTOTYPE),
        # operational (default-safe)
        ("the_door/src/the_door/core/diff/feature_attribution.py::compute", CAT_OPERATIONAL),
        ("docs/frontend-local-version-viewer/viewer/app.js::render", CAT_OPERATIONAL),
    ],
)
def test_classify_node_categories(node_id, expected):
    assert classify_node(node_id) == expected


def test_unrecognized_path_defaults_to_operational():
    """A node in an unexpected location must default to operational — the
    classifier never hides a real node (no false positives)."""
    assert classify_node("weird/place/thing.py::do") == CAT_OPERATIONAL
    assert classify_node("just_a_name") == CAT_OPERATIONAL


def test_is_operational_consistent_with_classify_node():
    operational = "the_door/src/the_door/core/x.py::m"
    a_test = "the_door/tests/unit/test_y.py::test_z"
    assert is_operational(operational) is True
    assert is_operational(a_test) is False
    assert classify_node(operational) == CAT_OPERATIONAL
    assert classify_node(a_test) in NON_OPERATIONAL


def test_classification_is_case_and_separator_insensitive():
    """Windows-style backslash separators and mixed case still classify."""
    assert classify_node("the_door\\tests\\unit\\Test_X.py::T") == CAT_TEST
