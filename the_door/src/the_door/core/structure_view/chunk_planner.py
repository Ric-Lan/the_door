"""Chunk Split Principle: 純程式把 structure-view 切成 token 預算內的 chunk。

只讀既有 artifact（複用 locator.load_views），零 LLM、純決定性、純加法。
spec: docs/superpowers/specs/2026-06-22-chunk-split-principle-design.md
"""
from __future__ import annotations

import json
from collections import deque

from the_door.core.structure_view.locator import load_views

# CJK 範圍（通用近似，非窮舉）：中日韓表意 + 假名 + 諺文 + 全形。
_CJK_RANGES = (
    (0x3040, 0x30FF),   # Hiragana + Katakana
    (0x3400, 0x4DBF),   # CJK Ext A
    (0x4E00, 0x9FFF),   # CJK Unified Ideographs
    (0xAC00, 0xD7A3),   # Hangul syllables
    (0xF900, 0xFAFF),   # CJK Compatibility Ideographs
    (0xFF00, 0xFFEF),   # Halfwidth/Fullwidth forms
)


DEFAULT_TARGET_TOKENS = 100_000
DEFAULT_LARGE_RATIO = 8


def triage(total_est: int, target: int, large_ratio: int) -> tuple:
    """粗分 regime：small(≤target,不切) / medium(≤ratio×target) / large(>)。"""
    if total_est <= target:
        return "small", False
    if total_est <= large_ratio * target:
        return "medium", True
    return "large", True


def _is_cjk(ch: str) -> bool:
    o = ord(ch)
    return any(lo <= o <= hi for lo, hi in _CJK_RANGES)


def estimate_tokens(view: dict) -> int:
    """逐節點 token 估計：CJK 每字 ~1 token，其餘 ~4 char/token。保守、不寫死常數。"""
    s = json.dumps(view, ensure_ascii=False)
    cjk = sum(1 for ch in s if _is_cjk(ch))
    other = len(s) - cjk
    return cjk + (other + 3) // 4


def _in_degree(view: dict) -> int:
    topo = view.get("topology")
    return topo.get("in_degree", 0) if isinstance(topo, dict) else 0


def build_adjacency(views: dict) -> dict:
    """無向鄰接表。只遍歷 out_edges（涵蓋所有邊一次）；外部 to_node_id 略過。"""
    adj: dict = {nid: set() for nid in views}
    for nid, view in views.items():
        for e in view.get("out_edges", []):
            tid = e.get("to_node_id")
            if tid in adj and tid != nid:
                adj[nid].add(tid)
                adj[tid].add(nid)
    return adj


def connected_components(adjacency: dict, node_ids) -> list:
    """回連通分量列表；每分量內按 node_id 排序、分量間按首元素排序（決定性）。"""
    seen: set = set()
    comps: list = []
    for start in sorted(node_ids):
        if start in seen:
            continue
        stack = [start]
        seen.add(start)
        comp = []
        while stack:
            n = stack.pop()
            comp.append(n)
            for nb in adjacency.get(n, ()):
                if nb not in seen:
                    seen.add(nb)
                    stack.append(nb)
        comps.append(sorted(comp))
    comps.sort(key=lambda c: c[0])
    return comps


def _slice_by_order(ordered: list, est: dict, target: int) -> list:
    """沿給定序貪婪填滿 target 就斷（Tier 3 原語，總定義域）。
    單節點 est > target → 自成 chunk 並標 oversized。
    前置：est 須涵蓋 ordered 內每個 node_id（呼叫端以同一 node 宇宙建 est）。"""
    chunks: list = []
    cur: list = []
    cur_est = 0
    for nid in ordered:
        e = est[nid]
        if e > target:
            if cur:
                chunks.append({"node_ids": cur, "est_tokens": cur_est, "oversized": False})
                cur, cur_est = [], 0
            chunks.append({"node_ids": [nid], "est_tokens": e, "oversized": True})
            continue
        if cur and cur_est + e > target:
            chunks.append({"node_ids": cur, "est_tokens": cur_est, "oversized": False})
            cur, cur_est = [], 0
        cur.append(nid)
        cur_est += e
    if cur:
        chunks.append({"node_ids": cur, "est_tokens": cur_est, "oversized": False})
    return chunks


def _bfs_order(component: list, adjacency: dict, indeg: dict) -> list:
    """從分量內最高 in_degree 節點起 BFS（鄰居按 (-in_degree, node_id) 序入列）。
    圖鄰近者在序列中相鄰 → 之後依序切時切口落在較稀疏處。決定性。
    前置：component 須為連通分量（由 connected_components 產出）；非連通則自 start
    不可達的節點會被略過。"""
    start = sorted(component, key=lambda n: (-indeg.get(n, 0), n))[0]
    seen = {start}
    queue = deque([start])
    order: list = []
    while queue:
        n = queue.popleft()
        order.append(n)
        for nb in sorted(adjacency.get(n, ()), key=lambda x: (-indeg.get(x, 0), x)):
            if nb not in seen:
                seen.add(nb)
                queue.append(nb)
    return order


def _pack(fitting: list, target: int) -> list:
    """把「各自 ≤ target 的連通分量」first-fit-decreasing 打包進 chunk（Tier 1）。
    fitting: list of (component_node_ids, comp_est)。決定性。"""
    items = sorted(fitting, key=lambda ce: (-ce[1], ce[0][0]))
    bins: list = []
    for comp, comp_est in items:
        assert comp_est <= target, "_pack only takes components that fit (oversized go to _slice_by_order)"
        placed = False
        for b in bins:
            if b["est_tokens"] + comp_est <= target:
                b["node_ids"].extend(comp)
                b["est_tokens"] += comp_est
                placed = True
                break
        if not placed:
            bins.append({"node_ids": list(comp), "est_tokens": comp_est})
    for b in bins:
        b["node_ids"] = sorted(b["node_ids"])
        b["oversized"] = False
    return bins


def _cross_chunk_edges(adjacency: dict, chunks: list) -> int:
    """原圖中兩端點落在不同 chunk 的邊數（無向、每邊算一次）。"""
    loc: dict = {}
    for i, c in enumerate(chunks):
        for nid in c["node_ids"]:
            loc[nid] = i
    count = 0
    for u, nbrs in adjacency.items():
        for v in nbrs:
            if u < v and loc.get(u) != loc.get(v):
                count += 1
    return count


def _assemble(target: int, regime: str, needs_split: bool, total: int,
              chunks: list, cross: int, warnings: list) -> dict:
    """組裝最終輸出：指派 chunk_id、剝除內部 oversized 旗標、附 rollup。"""
    out_chunks = [
        {"chunk_id": f"chunk-{i:03d}", "node_ids": c["node_ids"],
         "est_tokens": c["est_tokens"], "tier": c.get("tier", "whole")}
        for i, c in enumerate(chunks, 1)
    ]
    return {
        "target_tokens": target,
        "regime": regime,
        "needs_split": needs_split,
        "total_est_tokens": total,
        "chunks": out_chunks,
        "rollup": {
            "chunk_count": len(out_chunks),
            "cross_chunk_edges": cross,
            "oversized_node_warnings": sorted(set(warnings)),
        },
    }


def plan(codebase_path, target_tokens: int = DEFAULT_TARGET_TOKENS,
         large_ratio: int = DEFAULT_LARGE_RATIO) -> dict:
    """讀既有 structure-view，triage 後切成 ≤ target_tokens 的 chunk 計畫。
    structure-view 缺失 → load_views 拋 LocateError（自然向上拋）。"""
    return _plan_from_views(load_views(codebase_path), target_tokens, large_ratio)


def _plan_from_views(views: dict, target_tokens: int = DEFAULT_TARGET_TOKENS,
                     large_ratio: int = DEFAULT_LARGE_RATIO) -> dict:
    """純核心：吃 {node_id: view}，回 chunk 計畫。無 IO，便於合成測試。"""
    est = {nid: estimate_tokens(v) for nid, v in views.items()}
    total = sum(est.values())
    regime, needs_split = triage(total, target_tokens, large_ratio)

    if not needs_split:
        whole = {"node_ids": sorted(views), "est_tokens": total, "tier": "whole"}
        return _assemble(target_tokens, regime, needs_split, total, [whole], 0, [])

    adj = build_adjacency(views)
    indeg = {nid: _in_degree(views[nid]) for nid in views}
    fitting: list = []
    sliced: list = []
    warnings: list = []
    for comp in connected_components(adj, views.keys()):
        comp_est = sum(est[n] for n in comp)
        if comp_est <= target_tokens:
            fitting.append((comp, comp_est))            # Tier 1 候選
        else:
            for sub in _slice_by_order(_bfs_order(comp, adj, indeg), est, target_tokens):
                sub["tier"] = "oversized" if sub["oversized"] else "bisect"  # Tier 2/退化
                sliced.append(sub)
                if sub["oversized"]:
                    warnings.append(sub["node_ids"][0])
    packed = _pack(fitting, target_tokens)              # Tier 1
    for b in packed:
        b["tier"] = "cohesion"

    all_chunks = packed + sliced
    for c in all_chunks:                                # 統一輸出：塊內 node_ids 排序
        c["node_ids"] = sorted(c["node_ids"])           # （packed 已排序、sliced 原為 BFS 序）
    all_chunks.sort(key=lambda c: c["node_ids"][0])     # 決定性順序（按塊內最小 node_id）
    cross = _cross_chunk_edges(adj, all_chunks)
    return _assemble(target_tokens, regime, needs_split, total, all_chunks, cross, warnings)
