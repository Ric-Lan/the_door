"""Edge projection pure-function behavior (membrane residue shape)."""
from the_door.core.llm.edge_projection import project_edges_for_prompt
from the_door.core.reading.confidence_membrane import confidence_element

_EMPTY = {"indeterminate": [], "low_confidence_ambiguous": []}


def _edge(from_, to, res):
    return {"from": from_, "to": to, "type": "calls", "resolution": res}


def _low(caller, methods):
    """S4：name_match_ambiguous 升巢狀 confidence Signal（payload="low" I4 合法）。"""
    return {
        "caller": caller,
        "methods": methods,
        "cardinality": sum(methods.values()),
        "confidence": confidence_element("low").to_json(),
    }


def test_scope_rule_edges_kept():
    edges = [_edge("a", "b", "scope_rule")]
    kept, residue = project_edges_for_prompt(edges)
    assert kept == edges
    assert residue == _EMPTY


def test_import_alias_edges_kept():
    edges = [_edge("a", "b", "import_alias")]
    kept, residue = project_edges_for_prompt(edges)
    assert kept == edges
    assert residue == _EMPTY


def test_name_match_edges_kept():
    edges = [_edge("a", "b", "name_match")]
    kept, residue = project_edges_for_prompt(edges)
    assert kept == edges
    assert residue == _EMPTY


def test_ambiguous_dropped_into_low_confidence_with_count():
    edges = [_edge("caller", "pkg.Foo.write", "name_match_ambiguous")]
    kept, residue = project_edges_for_prompt(edges)
    assert kept == []
    assert residue["low_confidence_ambiguous"] == [_low("caller", {"write": 1})]
    assert residue["indeterminate"] == []


def test_dynamic_dropped_into_indeterminate_noise():
    edges = [_edge("caller", "Bus.send", "skipped_dynamic")]
    kept, residue = project_edges_for_prompt(edges)
    assert kept == []
    ind = residue["indeterminate"]
    assert len(ind) == 1
    assert ind[0]["value"] == {"caller": "caller", "methods": {"send": 1}}
    assert ind[0]["position"]["kind"] == "noise"
    assert ind[0]["position"]["gap_kind"] == "indeterminate"
    assert ind[0]["position"]["cardinality"] == 1
    assert ind[0]["position"]["proportion"] == 1.0
    assert residue["low_confidence_ambiguous"] == []


def test_dynamic_same_method_counted_not_deduped():
    """N3: 同名 method 多筆 → cardinality 真實計數（修 F5 病灶①）。"""
    edges = [_edge("caller", f"M{i}.send", "skipped_dynamic") for i in range(50)]
    _kept, residue = project_edges_for_prompt(edges)
    ind = residue["indeterminate"]
    assert ind[0]["value"]["methods"] == {"send": 50}
    assert ind[0]["position"]["cardinality"] == 50


def test_two_gap_kinds_split_not_conflated():
    """N4: skipped_dynamic 與 name_match_ambiguous 座標分流（修 F5 病灶②）。"""
    edges = [
        _edge("a", "Bus.send", "skipped_dynamic"),
        _edge("a", "F.write", "name_match_ambiguous"),
    ]
    _kept, residue = project_edges_for_prompt(edges)
    assert residue["indeterminate"][0]["value"]["methods"] == {"send": 1}
    assert residue["low_confidence_ambiguous"] == [_low("a", {"write": 1})]


def test_mixed_resolutions_partial_drop():
    edges = [
        _edge("a", "b", "scope_rule"),
        _edge("a", "c", "name_match"),
        _edge("a", "F.write",  "name_match_ambiguous"),
        _edge("a", "Bus.send", "skipped_dynamic"),
        _edge("a", "f", "import_alias"),
    ]
    kept, residue = project_edges_for_prompt(edges)
    assert {e["to"] for e in kept} == {"b", "c", "f"}
    assert residue["indeterminate"][0]["value"]["methods"] == {"send": 1}
    assert residue["low_confidence_ambiguous"] == [_low("a", {"write": 1})]


def test_to_node_without_dot_uses_whole_id_as_method_name():
    edges = [_edge("caller", "bare", "name_match_ambiguous")]
    _kept, residue = project_edges_for_prompt(edges)
    assert residue["low_confidence_ambiguous"] == [_low("caller", {"bare": 1})]


def test_indeterminate_list_sorted_by_caller_deterministic():
    """清單順序依 caller 排序＝prompt 跨次穩定（亂序輸入→相同順序輸出）。"""
    edges = [
        _edge("zeta", "B.f", "skipped_dynamic"),
        _edge("alpha", "B.g", "skipped_dynamic"),
        _edge("mu", "B.h", "skipped_dynamic"),
    ]
    _kept, residue = project_edges_for_prompt(edges)
    callers = [el["value"]["caller"] for el in residue["indeterminate"]]
    assert callers == ["alpha", "mu", "zeta"]


def test_empty_edges_returns_empty():
    kept, residue = project_edges_for_prompt([])
    assert kept == []
    assert residue == _EMPTY


def test_unknown_resolution_kept_defensively():
    edges = [{"from": "a", "to": "b", "type": "calls", "resolution": "future_value"}]
    kept, residue = project_edges_for_prompt(edges)
    assert kept == edges
    assert residue == _EMPTY
