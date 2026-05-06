"""Property-based tests for view_model conversion functions.

Uses Hypothesis with ASCII-only strategies (min_codepoint=32, max_codepoint=126)
for Windows cp950 compatibility.

**Validates: Requirements 10**
"""
from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from the_door.core.ui.view_model import (
    MISSING_VALUE,
    build_update_report_view_model,
)


# === Strategies ===

FEATURE_ID_ST = st.from_regex(r"feat-[a-z]{3,10}", fullmatch=True)

CHANGE_TYPE_ST = st.sampled_from(
    ["added", "removed", "attribute_changed", "dependency_changed"]
)

RISK_FLAG_ST = st.lists(
    st.sampled_from(["out_of_scope", "vulnerability", "semantic_drift"]),
    unique=True,
    max_size=3,
)

# ASCII-only label: avoids Unicode encoding issues on Windows cp950
ASCII_LABEL_ST = st.one_of(
    st.none(),
    st.text(
        alphabet=st.characters(min_codepoint=32, max_codepoint=126),
        min_size=1,
        max_size=50,
    ).filter(lambda s: s.strip()),
)

L1_CHANGE_ST = st.fixed_dictionaries({
    "feature_id": FEATURE_ID_ST,
    "change_type": CHANGE_TYPE_ST,
    "risk_flags": RISK_FLAG_ST,
    "current_label": ASCII_LABEL_ST,
    "baseline_label": ASCII_LABEL_ST,
})

UPDATE_REPORT_ST = st.fixed_dictionaries({
    "l0_summary": st.text(
        alphabet=st.characters(min_codepoint=32, max_codepoint=126),
        max_size=100,
    ),
    "l1_changes": st.lists(L1_CHANGE_ST, max_size=20),
    "l2_details": st.lists(L1_CHANGE_ST, max_size=20),
    "interrupted": st.booleans(),
})


# ============================================================================
# Property 1: change_counts values sum to len(l1_changes)
# **Validates: Requirements 10.1**
# ============================================================================

@given(report=UPDATE_REPORT_ST)
def test_prop_change_counts_sum(report):
    """sum(change_counts.values()) == len(l1_changes)."""
    vm = build_update_report_view_model(report)
    assert sum(vm["change_counts"].values()) == len(report["l1_changes"])


# ============================================================================
# Property 2: every changes[i].id is in l1_changes feature_id set
# **Validates: Requirements 10.2**
# ============================================================================

@given(report=UPDATE_REPORT_ST)
def test_prop_changes_ids_in_l1(report):
    """Every changes[i].id corresponds to a feature_id in l1_changes."""
    vm = build_update_report_view_model(report)
    l1_ids = {entry["feature_id"] for entry in report["l1_changes"]}
    for change in vm["changes"]:
        assert change["id"] in l1_ids


# ============================================================================
# Property 3: every details key is in changes id set
# **Validates: Requirements 10.3**
# ============================================================================

@given(report=UPDATE_REPORT_ST)
def test_prop_details_keys_in_changes(report):
    """Every key in details corresponds to an id present in changes."""
    vm = build_update_report_view_model(report)
    change_ids = {c["id"] for c in vm["changes"]}
    for key in vm["details"]:
        assert key in change_ids


# ============================================================================
# Property 4: l1_changes=[] → diff_available=False
# **Validates: Requirements 10.4**
# ============================================================================

@given(
    summary=st.text(
        alphabet=st.characters(min_codepoint=32, max_codepoint=126),
        max_size=100,
    ),
    interrupted=st.booleans(),
)
def test_prop_diff_available_false_when_empty(summary, interrupted):
    """l1_changes=[] → diff_available=False."""
    report = {
        "l0_summary": summary,
        "l1_changes": [],
        "l2_details": [],
        "interrupted": interrupted,
    }
    vm = build_update_report_view_model(report)
    assert vm["diff_available"] is False


# ============================================================================
# Property 5: baseline_label=null → before.label=MISSING_VALUE
# **Validates: Requirements 10.5**
# ============================================================================

@given(
    feature_id=FEATURE_ID_ST,
    change_type=CHANGE_TYPE_ST,
    current_label=ASCII_LABEL_ST,
)
def test_prop_missing_value_when_baseline_null(feature_id, change_type, current_label):
    """baseline_label=null in l2_details → before.label=MISSING_VALUE."""
    report = {
        "l0_summary": "test",
        "l1_changes": [
            {
                "feature_id": feature_id,
                "change_type": change_type,
                "risk_flags": [],
                "current_label": current_label,
                "baseline_label": None,
            }
        ],
        "l2_details": [
            {
                "feature_id": feature_id,
                "change_type": change_type,
                "current_label": current_label,
                "current_description": None,
                "baseline_label": None,
                "baseline_description": None,
                "scope_state": None,
                "related_vulnerabilities": [],
                "affected_relations": [],
            }
        ],
        "interrupted": False,
    }
    vm = build_update_report_view_model(report)
    assert vm["details"][feature_id]["before"]["label"] == MISSING_VALUE


# ============================================================================
# Property 6: current_label=null → after.label=MISSING_VALUE
# **Validates: Requirements 10.6**
# ============================================================================

@given(
    feature_id=FEATURE_ID_ST,
    change_type=CHANGE_TYPE_ST,
    baseline_label=ASCII_LABEL_ST,
)
def test_prop_missing_value_when_current_null(feature_id, change_type, baseline_label):
    """current_label=null in l2_details → after.label=MISSING_VALUE."""
    report = {
        "l0_summary": "test",
        "l1_changes": [
            {
                "feature_id": feature_id,
                "change_type": change_type,
                "risk_flags": [],
                "current_label": None,
                "baseline_label": baseline_label,
            }
        ],
        "l2_details": [
            {
                "feature_id": feature_id,
                "change_type": change_type,
                "current_label": None,
                "current_description": None,
                "baseline_label": baseline_label,
                "baseline_description": None,
                "scope_state": None,
                "related_vulnerabilities": [],
                "affected_relations": [],
            }
        ],
        "interrupted": False,
    }
    vm = build_update_report_view_model(report)
    assert vm["details"][feature_id]["after"]["label"] == MISSING_VALUE


# ============================================================================
# Property 7: len(changes) == len(l1_changes)
# **Validates: Requirements 10.7**
# ============================================================================

@given(report=UPDATE_REPORT_ST)
def test_prop_changes_length_equals_l1_changes(report):
    """len(changes) == len(l1_changes)."""
    vm = build_update_report_view_model(report)
    assert len(vm["changes"]) == len(report["l1_changes"])
