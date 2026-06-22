"""Chunk Split Principle: 純程式把 structure-view 切成 token 預算內的 chunk。

只讀既有 artifact（複用 locator.load_views），零 LLM、純決定性、純加法。
spec: docs/superpowers/specs/2026-06-22-chunk-split-principle-design.md
"""
from __future__ import annotations

import json
from collections import deque

# CJK 範圍（通用近似，非窮舉）：中日韓表意 + 假名 + 諺文 + 全形。
_CJK_RANGES = (
    (0x3040, 0x30FF),   # Hiragana + Katakana
    (0x3400, 0x4DBF),   # CJK Ext A
    (0x4E00, 0x9FFF),   # CJK Unified Ideographs
    (0xAC00, 0xD7A3),   # Hangul syllables
    (0xF900, 0xFAFF),   # CJK Compatibility Ideographs
    (0xFF00, 0xFFEF),   # Halfwidth/Fullwidth forms
)


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
    單節點 est > target → 自成 chunk 並標 oversized。"""
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
    圖鄰近者在序列中相鄰 → 之後依序切時切口落在較稀疏處。決定性。"""
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
