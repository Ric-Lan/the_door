"""Locate Query: 對既有 structure-view artifact 做 symbol 定位點查。

輔助便利功能（secondary）。零重抽取——只讀持久化 artifact，不呼叫 ASTExtractor。
"""
from __future__ import annotations

import gzip
import json
from pathlib import Path

from the_door.core.checklist import read_checklist
from the_door.core.structure_view.structure_index import view_dir

SEARCH_DEFAULT_LIMIT = 20
FRESHNESS_CHANGED_CAP = 20

_NO_ARTIFACTS_MSG = (
    "no structure-view artifacts; run extract_structure(codebase_path=...) first"
)


class LocateError(Exception):
    """定位查詢的可預期錯誤（artifact 缺、node 不存在、query 空）。"""


def load_views(codebase_path: str | Path) -> dict[str, dict]:
    """讀所有 regions/*.json.gz，回 {node_id: view}。缺 artifact → LocateError。"""
    regions_dir = view_dir(codebase_path) / "regions"
    if not regions_dir.is_dir():
        raise LocateError(_NO_ARTIFACTS_MSG)
    views: dict[str, dict] = {}
    for gz_path in sorted(regions_dir.glob("*.json.gz")):
        with gzip.open(gz_path, "rt", encoding="utf-8") as f:
            payload = json.load(f)
        for view in payload.get("nodes", []):
            views[view["node_id"]] = view
    if not views:
        raise LocateError(_NO_ARTIFACTS_MSG)
    return views


def _in_degree(view: dict) -> int:
    topo = view.get("topology")
    return topo.get("in_degree", 0) if isinstance(topo, dict) else 0


_KIND_RANK = {"name": 0, "path": 1}


def search_views(views: dict[str, dict], query: str,
                 limit: int = SEARCH_DEFAULT_LIMIT) -> dict:
    q = query.strip()
    if not q:
        raise LocateError("query is required")
    ql = q.lower()
    matched: list[tuple[str, dict, str]] = []
    for node_id, view in views.items():
        in_name = ql in (view.get("name") or "").lower()
        in_path = ql in node_id.lower()
        if not (in_name or in_path):
            continue
        matched.append(("name" if in_name else "path", view, node_id))
    matched.sort(key=lambda t: (_KIND_RANK[t[0]], -_in_degree(t[1]), t[2]))
    total = len(matched)
    results = [
        {
            "node_id": nid, "name": v.get("name"), "type": v.get("type"),
            "file": v.get("file"), "start_line": v.get("start_line"),
            "end_line": v.get("end_line"), "in_degree": _in_degree(v),
            "match_kind": mk,
        }
        for (mk, v, nid) in matched[:limit]
    ]
    return {"query": q, "total_matched": total,
            "returned": len(results), "results": results}
