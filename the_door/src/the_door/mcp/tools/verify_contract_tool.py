"""MCP tool: verify_data_model_contract — Tier 1 contract diff over agent-normalized field-sets."""
from __future__ import annotations

from pathlib import Path

from the_door.core.datamodel.models import DeclaredField, CodeTouch
from the_door.core.datamodel.contract_verifier import ContractVerifier
from the_door.core.datamodel.datamodel_renderer import contract_diff_to_json
from the_door.mcp.tools._response_envelope import wrap

TOOL_SCHEMA = {
    "type": "object",
    "required": ["codebase_path", "declared_model", "code_touched_model"],
    "properties": {
        "codebase_path": {"type": "string", "description": "Path to the codebase root."},
        "declared_model": {
            "type": "object",
            "description": "entity -> list of {field, type?} (agent-normalized declared schema).",
        },
        "code_touched_model": {
            "type": "array",
            "description": "list of {op: 'write'|'read', entity, fields: [..]} (agent-normalized).",
        },
    },
}


async def execute(arguments: dict) -> dict:
    codebase_path = arguments.get("codebase_path")
    declared_raw = arguments.get("declared_model")
    touched_raw = arguments.get("code_touched_model")
    if not codebase_path:
        return {"error": "codebase_path is required"}
    if not isinstance(declared_raw, dict):
        return {"error": "declared_model must be an object of entity -> fields"}
    if not isinstance(touched_raw, list):
        return {"error": "code_touched_model must be a list of touches"}

    try:
        declared = {
            entity: [DeclaredField(field=f["field"], type=f.get("type")) for f in fields]
            for entity, fields in declared_raw.items()
        }
        touched = [
            CodeTouch(op=t["op"], entity=t["entity"], fields=tuple(t["fields"]))
            for t in touched_raw
        ]
    except (KeyError, TypeError) as exc:
        return {"error": f"malformed field-set: {exc}"}

    diff = ContractVerifier().verify(declared, touched)

    root = Path(codebase_path)
    report_dir = root / ".the-door" / "datamodel"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "contract.json"
    report_path.write_text(contract_diff_to_json(diff), encoding="utf-8")

    payload = {
        "report_path": str(report_path),
        "summary": {
            "write_gap": sum(1 for e in diff.entries if e.status == "write_gap"),
            "coverage_gap": sum(1 for e in diff.entries if e.status == "coverage_gap"),
            "match": sum(1 for e in diff.entries if e.status == "match"),
        },
    }
    return wrap(payload, root)
