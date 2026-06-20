"""MCP tool: integration_check — 驗證功能宣稱依賴 (static) 是否有結構連線支撐。

判定邏輯住在 the_door.core.integration.checker（與 viewer API 共用）；
本檔保留 MCP schema 與薄 execute（解析 snapshot ref → 呼叫 core）。
"""
from __future__ import annotations

from pathlib import Path

from the_door.core.diff.snapshot_store import SnapshotStore
from the_door.core.integration.checker import (  # re-export：保既有測試的 ic.* 可用
    _load_structure,
    _path_within_hops,
    aggregate_features,
    classify_relation,
    run_integration_check,
)

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


async def execute(arguments: dict) -> dict:
    codebase_path = arguments.get("codebase_path")
    version_ref = arguments.get("version_ref")
    max_hops = arguments.get("max_hops", 2)
    if not codebase_path:
        return {"error": "codebase_path is required"}
    if not version_ref:
        return {"error": "version_ref is required"}
    store = SnapshotStore(Path(codebase_path))
    try:
        snap = store.resolve_baseline(version_ref)
    except Exception as e:
        return {"error": f"snapshot {version_ref!r} not found: {e}"}
    payload = run_integration_check(snap, codebase_path, max_hops)
    if payload.get("structure_missing"):
        return {"error": "no structure.full.json.gz found — run extract_structure first"}
    return {"version_ref": version_ref, "version_id": snap.version_id,
            "label": snap.label, "max_hops": max_hops, **payload}
