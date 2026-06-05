"""S2 characterization + 膜投影：先釘 F5 併桶+去重現狀（Task 3），
Task 4 retrofit 後改為座標分流+真實基數的 residue（見證契約變更）。"""
from the_door.core.llm.edge_projection import project_edges_for_prompt


def _edge(from_, to, res):
    return {"from": from_, "to": to, "type": "calls", "resolution": res}


def test_f5_current_conflates_and_dedups():
    """CHARACTERIZATION（Task 3 現狀＝F5 病灶）：兩 gap-kind 併一桶 + 同名去重。"""
    edges = [
        _edge("a", "Bus.send", "skipped_dynamic"),
        _edge("a", "F.write", "name_match_ambiguous"),
        _edge("a", "G.write", "name_match_ambiguous"),     # 同名 write → 去重成 1
    ]
    kept, hints = project_edges_for_prompt(edges)
    assert kept == []
    assert hints == {"a": ["send", "write"]}   # send(dynamic)+write(ambiguous) 混桶、write 去重
