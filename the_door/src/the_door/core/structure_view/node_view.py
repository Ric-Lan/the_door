"""L2 node 座標視圖：單 node 的多軸並置（屬性＋出入邊＋topology＋殘餘基數）。

定址欄位統一 node_id 詞彙（out_edges[].to_node_id / in_edges[].from_node_id）——
消滅 F-b 型手工 join 失誤。殘餘只存基數引用，完整條目在 edge-residue.json。
"""
from __future__ import annotations

from collections import Counter

from the_door.models import ASTNode, Edge, TopologyEntry


def assemble_views(
    nodes: list[ASTNode],
    edges: list[Edge],
    topology_entries: list[TopologyEntry],
    residue: dict,
) -> dict[str, dict]:
    """回 {node_id: 視圖 dict}。決定性：邊列表按 (對端 id, type) 排序。"""
    topo = {t.node_id: t for t in topology_entries}
    out_by: dict[str, list[dict]] = {}
    in_by: dict[str, list[dict]] = {}
    for e in edges:
        out_by.setdefault(e.from_node, []).append(
            {"to_node_id": e.to_node, "type": e.type, "resolution": e.resolution})
        in_by.setdefault(e.to_node, []).append(
            {"from_node_id": e.from_node, "type": e.type, "resolution": e.resolution})

    low_callers = Counter(ent.get("caller") for ent in residue.get("low_confidence_ambiguous", []))
    ind_callers = Counter(ent.get("caller") for ent in residue.get("indeterminate", []))

    views: dict[str, dict] = {}
    for n in nodes:
        t = topo.get(n.node_id)
        views[n.node_id] = {
            "node_id": n.node_id,
            "type": n.type, "name": n.name, "file": n.file, "language": n.language,
            "decorators": n.decorators, "parameters": n.parameters,
            "return_type": n.return_type, "docstring": n.docstring, "comments": n.comments,
            "topology": ({
                "in_degree": t.in_degree, "out_degree": t.out_degree,
                "topology_rank": t.topology_rank, "is_entry_point": t.is_entry_point,
                "batch_assignment": t.batch_assignment,
            } if t else None),
            "out_edges": sorted(out_by.get(n.node_id, []),
                                key=lambda d: (d["to_node_id"], d["type"])),
            "in_edges": sorted(in_by.get(n.node_id, []),
                               key=lambda d: (d["from_node_id"], d["type"])),
            "residue_as_caller": {
                "low_confidence_ambiguous": low_callers.get(n.node_id, 0),
                "indeterminate": ind_callers.get(n.node_id, 0),
            },
        }
    return views
