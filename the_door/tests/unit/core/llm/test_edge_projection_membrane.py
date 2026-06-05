"""S2 characterization + 膜投影：先釘 F5 併桶+去重現狀（Task 3），
Task 4 retrofit 後改為座標分流+真實基數的 residue（見證契約變更）。"""
from the_door.core.llm.edge_projection import project_edges_for_prompt


def _edge(from_, to, res):
    return {"from": from_, "to": to, "type": "calls", "resolution": res}


def test_f5_retrofit_splits_and_counts():
    """retrofit 後：座標分流（N4）+ 真實基數（N3）。"""
    edges = [
        _edge("a", "Bus.send", "skipped_dynamic"),
        _edge("a", "Bus.send", "skipped_dynamic"),     # 同名 2 筆 → cardinality=2
        _edge("a", "F.write", "name_match_ambiguous"),
        _edge("a", "G.write", "name_match_ambiguous"),
        _edge("a", "b", "scope_rule"),
    ]
    kept, residue = project_edges_for_prompt(edges)
    assert [e["to"] for e in kept] == ["b"]
    ind = residue["indeterminate"]
    assert len(ind) == 1 and ind[0]["value"]["caller"] == "a"
    assert ind[0]["value"]["methods"] == {"send": 2}        # 真實基數、不去重
    assert ind[0]["position"]["gap_kind"] == "indeterminate"
    assert ind[0]["position"]["cardinality"] == 2
    assert ind[0]["position"]["proportion"] == 2 / 5
    assert residue["low_confidence_ambiguous"] == {"a": {"write": 2}}   # 座標分流、基數保留
