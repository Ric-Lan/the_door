"""MCP tool: scope_create — create a new scope definition file."""
from __future__ import annotations

TOOL_SCHEMA = {
    "type": "object",
    "required": ["scope_name"],
    "properties": {
        "scope_name": {
            "type": "string",
            "description": "Scope 名稱",
        },
        "codebase_path": {
            "type": "string",
            "description": "Codebase 根目錄路徑（預設 '.'）",
        },
    },
}


async def execute(arguments: dict) -> dict:
    import json
    from pathlib import Path
    from the_door.core.scope.scope_verifier import (
        scope_name_to_filename,
        serialize_scope_definition,
    )
    from the_door.mcp.tools._response_envelope import wrap
    from the_door.models import ScopeDefinition

    scope_name = arguments["scope_name"]
    codebase_path = arguments.get("codebase_path", ".")
    project_root = Path(codebase_path)

    scopes_dir = project_root / ".the-door" / "scopes"
    scopes_dir.mkdir(parents=True, exist_ok=True)

    kebab_name = scope_name_to_filename(scope_name)
    scope_file = scopes_dir / f"{kebab_name}.json"

    # Create empty scope definition
    scope_def = ScopeDefinition(scope_name=scope_name, features=[], description=None)
    data = serialize_scope_definition(scope_def)
    data["features"] = []
    scope_file.write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    return wrap({
        "scope_file": str(scope_file),
        "scope_name": scope_name,
    }, project_path=project_root, context="mcp")
