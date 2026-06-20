"""MCP tool: integration_check — 驗證功能宣稱依賴 (static) 是否有結構連線支撐。

判定（per relation）：
- static + 有 ≤max_hops 跳 edge path → "backed"（附 evidence_path）
- static + 無路徑                     → "gap"
- static + 目標 feature 節點不在結構圖 → "undetermined"
- inferred                            → "conceptual"（回報 inferred_reason，不查邊）
- 無 relation_type（舊資料）           → "not_assessed"
"""
from __future__ import annotations

import gzip
import json
from collections import deque
from pathlib import Path

from the_door.core.diff.snapshot_store import SnapshotStore

TOOL_SCHEMA = {
    "type": "object",
    "required": ["codebase_path", "version_ref"],
    "properties": {
        "codebase_path": {"type": "string", "description": "Path to the codebase root."},
        "version_ref": {"type": "string",
                        "description": "Snapshot ref: label / git tag / date / commit SHA / version_id."},
        "max_hops": {"type": "integer", "minimum": 1, "default": 2,
                     "description": "static 關係的 edge path 最大跳數（1=只認直接邊）。"},
    },
}


def _path_within_hops(from_nodes, to_nodes, adjacency, max_hops):
    """回傳第一條 ≤max_hops 跳（邊數）的路徑 node 列表；找不到回 None。"""
    if not from_nodes or not to_nodes:
        return None
    to_set = set(to_nodes)
    visited = set(from_nodes)
    queue = deque((n, [n]) for n in from_nodes)
    while queue:
        cur, path = queue.popleft()
        if cur in to_set:
            return path
        if len(path) - 1 >= max_hops:
            continue
        for nxt in adjacency.get(cur, ()):
            if nxt not in visited:
                visited.add(nxt)
                queue.append((nxt, path + [nxt]))
    return None


def classify_relation(rel, l1, graph_nodes, adjacency, max_hops):
    """rel: {from_feature,to_feature,relation_type?,inferred_reason?}；l1: feature_id->list(node_id)。"""
    base = {"from_feature": rel.get("from_feature"), "to_feature": rel.get("to_feature")}
    rtype = rel.get("relation_type")
    if not rtype:
        return {**base, "verdict": "not_assessed"}
    if rtype == "inferred":
        return {**base, "verdict": "conceptual", "inferred_reason": rel.get("inferred_reason")}
    # static
    from_nodes = l1.get(rel.get("from_feature"), [])
    to_nodes = l1.get(rel.get("to_feature"), [])
    present_to = set(to_nodes) & set(graph_nodes)
    if not present_to:
        return {**base, "verdict": "undetermined",
                "evidence": "target feature has no nodes in the structure graph"}
    path = _path_within_hops(from_nodes, present_to, adjacency, max_hops)
    if path is not None:
        return {**base, "verdict": "backed", "evidence_path": path}
    return {**base, "verdict": "gap",
            "evidence": f"no edge path within {max_hops} hop(s)"}


def _load_structure(codebase_path):
    gz = Path(codebase_path) / ".the-door" / "structure-view" / "structure.full.json.gz"
    if not gz.is_file():
        return None
    with gzip.open(gz, "rt", encoding="utf-8") as f:
        data = json.load(f)
    edges = data.get("edges", [])
    nodes = {n["node_id"] for n in data.get("nodes", [])}
    adjacency = {}
    for e in edges:
        adjacency.setdefault(e["from"], set()).add(e["to"])
    return nodes, adjacency


async def execute(arguments: dict) -> dict:
    codebase_path = arguments.get("codebase_path")
    version_ref = arguments.get("version_ref")
    max_hops = arguments.get("max_hops", 2)
    if not codebase_path:
        return {"error": "codebase_path is required"}
    if not version_ref:
        return {"error": "version_ref is required"}

    store = SnapshotStore(Path(codebase_path))
    # resolve_baseline 解析所有 ref 形式（label/git tag/date/SHA/version_id）、查不到時 raise；
    # 不用 get_snapshot fallback——它只吃 UUID 且查不到回 None（會漏接成 snap=None）。
    try:
        snap = store.resolve_baseline(version_ref)
    except Exception as e:
        return {"error": f"snapshot {version_ref!r} not found: {e}"}

    loaded = _load_structure(codebase_path)
    if loaded is None:
        return {"error": "no structure.full.json.gz found — run extract_structure first"}
    graph_nodes, adjacency = loaded

    l1 = {fid: list(fs.source_nodes) for fid, fs in snap.l1_snapshot.items()}
    relations = []
    for r in snap.feature_relations_snapshot:
        rel = {"from_feature": r.from_feature, "to_feature": r.to_feature,
               "relation_type": r.relation_type, "inferred_reason": r.inferred_reason}
        relations.append(classify_relation(rel, l1, graph_nodes, adjacency, max_hops))

    rollup = {}
    for v in ("backed", "gap", "undetermined", "conceptual", "not_assessed"):
        rollup[v] = sum(1 for r in relations if r["verdict"] == v)

    return {
        "version_ref": version_ref,
        "version_id": snap.version_id,
        "label": snap.label,
        "max_hops": max_hops,
        "relations": relations,
        "rollup": rollup,
    }
