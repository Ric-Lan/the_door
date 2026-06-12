"""L0 撥離索引組裝＋artifact 落檔。

回應本體＝索引（索引尺寸）；bulk 落 .the-door/structure-view/：
  index.json                 — L0 索引（同回應內容，落檔供重讀）
  structure.full.json.gz     — 全量 raw structure（validate_output 接縫用；
                               複用 structure_serializer.build_structure_dict）
  regions/<region_id>.json.gz — 該區全部 L2 node 視圖
撥離≠刪除：被標示區資料完整在檔（加法不減法）。
"""
from __future__ import annotations

import gzip
import json
from pathlib import Path

from the_door.core.extraction.structure_serializer import build_structure_dict
from the_door.core.structure_view.node_view import assemble_views
from the_door.core.structure_view.peel_membrane import evaluate_peel
from the_door.core.structure_view.region_partition import partition
from the_door.models import StructureJSON

STRUCTURE_VIEW_DIRNAME = "structure-view"

_CONSUMPTION_GUIDE = {
    "addressing": "node_id",
    "region_artifact_format": "gzip JSON: {region_id, nodes: [L2 view]}；view 鍵＝node_id/"
                              "out_edges[].to_node_id/in_edges[].from_node_id/topology/residue_as_caller",
    "batch_semantics": "topology-guided LLM reading: batch 1＝entry points，batch 2..5＝"
                       "其餘按 in_degree 降冪分配；建議按批次序消費",
    "full_structure": "structure.full.json.gz＝raw nodes/edges/topology 全量（edges 用 from/to 舊欄位名）",
    "edge_residue": "完整殘餘條目在 .the-door/edge-residue.json（先跑 edge_residue 工具）",
}


def view_dir(codebase_path: str | Path) -> Path:
    return Path(codebase_path) / ".the-door" / STRUCTURE_VIEW_DIRNAME


def write_artifacts(codebase_path: str | Path, structure: StructureJSON, residue: dict) -> dict:
    """落 artifact 並回傳 L0 索引 dict（即 MCP 回應本體）。"""
    base = view_dir(codebase_path)
    (base / "regions").mkdir(parents=True, exist_ok=True)

    views = assemble_views(structure.nodes, structure.edges, structure.topology, residue)
    regions = partition(structure.nodes, structure.edges)
    batch_of = {t.node_id: t.batch_assignment for t in structure.topology}
    total_nodes = len(structure.nodes)

    region_entries = []
    for r in regions:
        region_payload = {"region_id": r.region_id, "nodes": [views[nid] for nid in r.node_ids]}
        path = base / "regions" / f"{r.region_id}.json.gz"
        with gzip.open(path, "wt", encoding="utf-8") as f:
            json.dump(region_payload, f, ensure_ascii=False)

        batches: dict[str, int] = {}
        for nid in r.node_ids:
            b = str(batch_of.get(nid, 0))
            batches[b] = batches.get(b, 0) + 1

        region_entries.append({
            "region_id": r.region_id,
            "node_count": len(r.node_ids),
            "share_pct": round(len(r.node_ids) / total_nodes * 100, 1) if total_nodes else 0.0,
            "edges": {"internal": r.internal_edges, "inbound": r.inbound_edges,
                      "outbound": r.outbound_edges},
            "flow_to": r.flow_to,
            "batches": dict(sorted(batches.items())),
            "artifact_path": str(path),
            "size_bytes": path.stat().st_size,
            "peel": evaluate_peel(r),
        })

    full_path = base / "structure.full.json.gz"
    with gzip.open(full_path, "wt", encoding="utf-8") as f:
        json.dump(build_structure_dict(structure, None), f, ensure_ascii=False)

    index = {
        "totals": {"files": len(structure.files), "nodes": total_nodes,
                   "edges": len(structure.edges), "regions": len(regions)},
        "regions": region_entries,
        "artifact_dir": str(base),
        "full_structure_path": str(full_path),
        "consumption_guide": _CONSUMPTION_GUIDE,
    }
    (base / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    return index
