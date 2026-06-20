"""整合落差判定核心（MCP 工具與 viewer API 共用、純結構、零 agent）。"""
from __future__ import annotations

import gzip
import json
from collections import deque
from pathlib import Path

_VERDICTS = ("backed", "gap", "undetermined", "conceptual", "not_assessed")


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
    base = {"from_feature": rel.get("from_feature"), "to_feature": rel.get("to_feature")}
    rtype = rel.get("relation_type")
    if not rtype:
        return {**base, "verdict": "not_assessed"}
    if rtype == "inferred":
        return {**base, "verdict": "conceptual", "inferred_reason": rel.get("inferred_reason")}
    from_nodes = l1.get(rel.get("from_feature"), [])
    to_nodes = l1.get(rel.get("to_feature"), [])
    present_to = set(to_nodes) & set(graph_nodes)
    if not present_to:
        return {**base, "verdict": "undetermined",
                "evidence": "target feature has no nodes in the structure graph"}
    path = _path_within_hops(from_nodes, present_to, adjacency, max_hops)
    if path is not None:
        return {**base, "verdict": "backed", "evidence_path": path}
    return {**base, "verdict": "gap", "evidence": f"no edge path within {max_hops} hop(s)"}


def _load_structure(codebase_path):
    gz = Path(codebase_path) / ".the-door" / "structure-view" / "structure.full.json.gz"
    if not gz.is_file():
        return None
    with gzip.open(gz, "rt", encoding="utf-8") as f:
        data = json.load(f)
    nodes = {n["node_id"] for n in data.get("nodes", [])}
    adjacency = {}
    for e in data.get("edges", []):
        adjacency.setdefault(e["from"], set()).add(e["to"])
    return nodes, adjacency


def aggregate_features(relations):
    """per-feature 徽章：以 from_feature 聚合 outgoing 判定。
    優先序 gap > undetermined > backed > none（只剩 conceptual/not_assessed）。"""
    by_feat: dict[str, list[str]] = {}
    for r in relations:
        by_feat.setdefault(r["from_feature"], []).append(r["verdict"])
    out = {}
    for ff, verds in by_feat.items():
        if "gap" in verds:
            out[ff] = "gap"
        elif "undetermined" in verds:
            out[ff] = "undetermined"
        elif "backed" in verds:
            out[ff] = "backed"
        else:
            out[ff] = "none"
    return out


def run_integration_check(snapshot, codebase_path, max_hops=2):
    """組裝單一 payload：relations[] + features{} 聚合 + rollup。結構缺檔回 structure_missing。"""
    loaded = _load_structure(codebase_path)
    if loaded is None:
        return {"relations": [], "features": {},
                "rollup": {v: 0 for v in _VERDICTS}, "structure_missing": True}
    graph_nodes, adjacency = loaded
    l1 = {fid: list(fs.source_nodes) for fid, fs in snapshot.l1_snapshot.items()}
    relations = []
    for r in snapshot.feature_relations_snapshot:
        rel = {"from_feature": r.from_feature, "to_feature": r.to_feature,
               "relation_type": r.relation_type, "inferred_reason": r.inferred_reason}
        relations.append(classify_relation(rel, l1, graph_nodes, adjacency, max_hops))
    rollup = {v: sum(1 for r in relations if r["verdict"] == v) for v in _VERDICTS}
    return {"relations": relations, "features": aggregate_features(relations), "rollup": rollup}
