"""Property tests for edge_projection invariants (membrane residue shape)."""
from collections import Counter

from hypothesis import given, strategies as st

from the_door.core.llm.edge_projection import project_edges_for_prompt

KNOWN_RESOLUTIONS = st.sampled_from([
    "scope_rule", "import_alias", "name_match",
    "name_match_ambiguous", "skipped_dynamic",
])
EDGE = st.fixed_dictionaries({
    "from": st.text(min_size=1, max_size=10),
    "to": st.text(min_size=1, max_size=10),
    "type": st.just("calls"),
    "resolution": KNOWN_RESOLUTIONS,
})
EDGES = st.lists(EDGE, max_size=30)
_EMPTY = {"indeterminate": [], "low_confidence_ambiguous": {}}


@given(edges=EDGES)
def test_high_confidence_always_kept(edges):
    high_conf = [e for e in edges if e["resolution"] in ("scope_rule", "import_alias")]
    kept, _residue = project_edges_for_prompt(edges)
    for e in high_conf:
        assert e in kept


@given(edges=EDGES)
def test_ambiguous_and_dynamic_never_in_kept(edges):
    kept, _residue = project_edges_for_prompt(edges)
    for e in kept:
        assert e["resolution"] not in ("name_match_ambiguous", "skipped_dynamic")


@given(edges=EDGES)
def test_idempotent(edges):
    """Re-projecting kept_edges is a no-op (kept edges produce no residue)."""
    kept1, _r1 = project_edges_for_prompt(edges)
    kept2, residue2 = project_edges_for_prompt(kept1)
    assert kept2 == kept1
    assert residue2 == _EMPTY


@given(edges=EDGES)
def test_indeterminate_cardinality_equals_skipped_dynamic_count(edges):
    """N3 反向 property：每 caller 的 indeterminate cardinality
    ＝該 caller 的 skipped_dynamic 邊真實筆數（不去重）。"""
    _kept, residue = project_edges_for_prompt(edges)
    expected = Counter(e["from"] for e in edges if e["resolution"] == "skipped_dynamic")
    got = {el["value"]["caller"]: el["position"]["cardinality"]
           for el in residue["indeterminate"]}
    assert got == dict(expected)
