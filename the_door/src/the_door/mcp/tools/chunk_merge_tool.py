"""MCP tool: chunk_merge — 收齊各 chunk 的 features，從結構邊決定性推導 static
relations，回傳可寫入 snapshot_write 的 payload。唯讀、不寫 snapshot、不入 C3 gate。"""
from __future__ import annotations

from pathlib import Path

from the_door.core.structure_view import chunk_merge
from the_door.core.structure_view.locator import LocateError
from the_door.mcp.tools._response_envelope import wrap

TOOL_SCHEMA = {
    "type": "object",
    "required": ["codebase_path", "chunks"],
    "properties": {
        "codebase_path": {"type": "string", "description": "Path to the codebase root."},
        "chunks": {
            "type": "array",
            "description": (
                "Per-chunk subagent outputs. Each: {chunk_id, features:[{feature_id "
                "(chunk-namespaced, globally unique), label, description, confidence, "
                "source_nodes:[node_id]}]}. Subagents produce features only — relations "
                "are derived here deterministically from structural edges."
            ),
            "items": {
                "type": "object",
                "required": ["chunk_id", "features"],
                "properties": {
                    "chunk_id": {"type": "string"},
                    "features": {"type": "array", "items": {"type": "object"}},
                },
            },
        },
    },
}


async def execute(arguments: dict) -> dict:
    codebase_path = arguments.get("codebase_path")
    if not codebase_path:
        return {"error": "codebase_path is required"}
    chunks = arguments.get("chunks")
    if not chunks:
        return {"error": "chunks is required and must be non-empty"}
    try:
        payload = chunk_merge.merge(codebase_path, chunks)
    except (chunk_merge.ChunkMergeError, LocateError) as exc:
        return {"error": str(exc)}
    return wrap(payload, Path(codebase_path))
