"""MCP tool: edge_residue — persist the membrane noise residue (zero token, zero key)."""
from __future__ import annotations

import json
from pathlib import Path

from the_door.core.checklist import STAGE_EDGE_RESIDUE, checklist_path, stamp_stage
from the_door.core.extraction.ast_extractor import ASTExtractor
from the_door.core.llm.edge_projection import project_edges_for_prompt
from the_door.mcp.tools._response_envelope import wrap
from the_door.models.snapshot import SNAPSHOT_CONTRACT_VERSION

TOOL_SCHEMA = {
    "type": "object",
    "required": ["codebase_path"],
    "properties": {
        "codebase_path": {
            "type": "string",
            "description": "Path to the codebase root.",
        },
    },
}

EDGE_RESIDUE_FILENAME = "edge-residue.json"


def _artifact_path(codebase_path: str | Path) -> Path:
    return Path(codebase_path) / ".the-door" / EDGE_RESIDUE_FILENAME


async def execute(arguments: dict) -> dict:
    codebase_path = arguments.get("codebase_path")
    if not codebase_path:
        return {"error": "codebase_path is required"}

    extraction = ASTExtractor().extract(codebase_path)
    edge_dicts = [
        {"from": e.from_node, "to": e.to_node, "type": e.type, "resolution": e.resolution}
        for e in extraction.edges
    ]
    kept, residue = project_edges_for_prompt(edge_dicts)

    artifact = {
        "indeterminate": residue["indeterminate"],
        "low_confidence_ambiguous": residue["low_confidence_ambiguous"],
        "total_edges": len(edge_dicts),
        "kept_edges": len(kept),
    }
    out_path = _artifact_path(codebase_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")

    # C2: stamp the execution checklist so the snapshot_write gate can verify
    # node-coverage + contract currency (not just artifact existence). A stamp
    # failure must surface — silently "succeeding" would leave the agent stuck at
    # a deny it can't explain.
    covered_nodes = sorted({n.node_id for n in extraction.nodes})
    # Record a per-file (mtime_ns, size) fingerprint of every discovered source
    # file so the staleness gate (C3 #4) can detect deletion / in-place
    # modification since this stamp without re-extracting AST. `.the-door/*.json`
    # is filtered out of extraction.files by extension → no self-staleness.
    root = Path(codebase_path)
    source_files: dict[str, list[int]] = {}
    for fi in extraction.files:
        try:
            st = (root / fi.path).stat()
        except OSError:
            continue  # vanished between discovery and stat → skip (fail-soft)
        source_files[fi.path] = [st.st_mtime_ns, st.st_size]
    try:
        stamp_stage(
            codebase_path,
            STAGE_EDGE_RESIDUE,
            covered_nodes=covered_nodes,
            source_files=source_files,
            contract_version=SNAPSHOT_CONTRACT_VERSION,
        )
    except Exception as exc:  # disk / permission — fail loud, not silent
        return {"error": f"checklist stamp failed: {exc}"}

    payload = {
        "artifact_path": str(out_path),
        "checklist_path": str(checklist_path(codebase_path)),
        "indeterminate_count": len(residue["indeterminate"]),
        "low_confidence_count": len(residue["low_confidence_ambiguous"]),
        "total_edges": len(edge_dicts),
        "kept_edges": len(kept),
    }
    return wrap(payload, Path(codebase_path))
