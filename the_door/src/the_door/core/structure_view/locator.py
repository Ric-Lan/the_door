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
