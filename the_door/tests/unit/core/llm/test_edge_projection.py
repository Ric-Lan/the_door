"""Edge projection pure-function behavior."""
from the_door.core.llm.edge_projection import project_edges_for_prompt


def _edge(from_, to, res):
    return {"from": from_, "to": to, "type": "calls", "resolution": res}


def test_scope_rule_edges_kept():
    edges = [_edge("a", "b", "scope_rule")]
    kept, hints = project_edges_for_prompt(edges)
    assert kept == edges
    assert hints == {}


def test_import_alias_edges_kept():
    edges = [_edge("a", "b", "import_alias")]
    kept, hints = project_edges_for_prompt(edges)
    assert kept == edges
    assert hints == {}


def test_name_match_edges_kept():
    edges = [_edge("a", "b", "name_match")]
    kept, hints = project_edges_for_prompt(edges)
    assert kept == edges
    assert hints == {}


def test_ambiguous_dropped_and_hinted_with_class_dot_method():
    edges = [_edge("caller", "pkg.Foo.write", "name_match_ambiguous")]
    kept, hints = project_edges_for_prompt(edges)
    assert kept == []
    assert hints == {"caller": ["write"]}


def test_dynamic_dropped_and_hinted():
    edges = [_edge("caller", "Bus.send", "skipped_dynamic")]
    kept, hints = project_edges_for_prompt(edges)
    assert kept == []
    assert hints == {"caller": ["send"]}


def test_to_node_without_dot_uses_whole_id_as_method_name():
    edges = [_edge("caller", "bare", "name_match_ambiguous")]
    kept, hints = project_edges_for_prompt(edges)
    assert hints == {"caller": ["bare"]}


def test_multiple_ambiguous_same_caller_deduped_sorted():
    edges = [
        _edge("caller", "F.write", "name_match_ambiguous"),
        _edge("caller", "G.get",   "name_match_ambiguous"),
        _edge("caller", "H.write", "name_match_ambiguous"),  # dup method name
    ]
    kept, hints = project_edges_for_prompt(edges)
    assert kept == []
    assert hints == {"caller": ["get", "write"]}


def test_mixed_resolutions_partial_drop():
    edges = [
        _edge("a", "b", "scope_rule"),
        _edge("a", "c", "name_match"),
        _edge("a", "F.write",  "name_match_ambiguous"),
        _edge("a", "Bus.send", "skipped_dynamic"),
        _edge("a", "f", "import_alias"),
    ]
    kept, hints = project_edges_for_prompt(edges)
    assert {e["to"] for e in kept} == {"b", "c", "f"}
    assert hints == {"a": ["send", "write"]}


def test_empty_edges_returns_empty():
    kept, hints = project_edges_for_prompt([])
    assert kept == []
    assert hints == {}


def test_unknown_resolution_kept_defensively():
    """Unknown resolution doesn't crash, edge stays in kept."""
    edges = [{"from": "a", "to": "b", "type": "calls",
              "resolution": "future_value"}]
    kept, hints = project_edges_for_prompt(edges)
    assert kept == edges
    assert hints == {}
