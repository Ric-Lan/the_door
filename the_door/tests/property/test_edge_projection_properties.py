"""Property tests for edge_projection invariants."""
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


@given(edges=EDGES)
def test_high_confidence_always_kept(edges):
    """scope_rule and import_alias edges always survive projection."""
    high_conf = [e for e in edges
                 if e["resolution"] in ("scope_rule", "import_alias")]
    kept, _hints = project_edges_for_prompt(edges)
    for e in high_conf:
        assert e in kept


@given(edges=EDGES)
def test_ambiguous_and_dynamic_never_in_kept(edges):
    """ambiguous + dynamic must NOT appear in kept_edges."""
    kept, _hints = project_edges_for_prompt(edges)
    for e in kept:
        assert e["resolution"] not in ("name_match_ambiguous", "skipped_dynamic")


@given(edges=EDGES)
def test_idempotent(edges):
    """Re-projecting kept_edges is a no-op (kept edges produce no new hints)."""
    kept1, _hints1 = project_edges_for_prompt(edges)
    kept2, hints2 = project_edges_for_prompt(kept1)
    assert kept2 == kept1
    assert hints2 == {}


@given(edges=EDGES)
def test_hint_method_lists_sorted_and_unique(edges):
    """Hint method-name lists are deduplicated and sorted."""
    _kept, hints = project_edges_for_prompt(edges)
    for _caller, names in hints.items():
        assert names == sorted(names)
        assert len(names) == len(set(names))
