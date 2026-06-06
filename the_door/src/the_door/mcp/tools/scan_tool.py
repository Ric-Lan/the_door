"""MCP tool: scan — scan codebase for known vulnerabilities."""
from __future__ import annotations

TOOL_SCHEMA = {
    "type": "object",
    "required": ["codebase_path"],
    "properties": {
        "codebase_path": {
            "type": "string",
            "description": "Path to the codebase root",
        },
        "offline": {
            "type": "boolean",
            "default": False,
            "description": "Use local OSV database",
        },
        "format": {
            "type": "string",
            "enum": ["raw", "summary"],
            "default": "summary",
            "description": "Output format",
        },
    },
}


async def execute(arguments: dict) -> dict:
    from pathlib import Path
    from the_door.core.vulnerability.vulnerability_scanner import VulnerabilityScanner
    from the_door.core.vulnerability.vulnerability_renderer import VulnerabilityRenderer
    from the_door.core.vulnerability.vulnerability_membrane import verdict_element
    from the_door.mcp.tools._response_envelope import wrap

    codebase_path = arguments["codebase_path"]
    project_root = Path(arguments.get("codebase_path") or arguments.get("project_path") or Path.cwd())
    offline = arguments.get("offline", False)
    fmt = arguments.get("format", "summary")

    scanner = VulnerabilityScanner(offline=offline)
    result = scanner.scan(Path(codebase_path))

    if fmt == "raw":
        # 每筆裁決經膜投影：有 evidence→RelayedVerdict、無→NoisePosition(indeterminate)。
        # 不再 emit 裸假 cvss（意義由 position 結構承載，非 prompt）。
        return wrap({
            "vulnerabilities": [verdict_element(v).to_json() for v in result.entries],
            "warnings": result.warnings,
            "scanner_available": result.scanner_available,
        }, project_path=project_root, context="mcp")
    else:
        renderer = VulnerabilityRenderer()
        summary = renderer.build_vulnerability_summary(result.entries, result.db_freshness)
        header = renderer.format_summary_header(summary)
        # 保留決定性 severity 排序（不退成掃描序）；entries 經膜投影、無自鑄 action。
        sorted_entries = sorted(
            result.entries,
            key=lambda v: (renderer.SEVERITY_ORDER.get(v.severity, 9), -(v.cvss or 0.0)),
        )
        return wrap({
            "header": header,
            "total_critical": summary.total_critical,
            "total_high": summary.total_high,
            "total_medium": summary.total_medium,
            "total_low": summary.total_low,
            "entries": [verdict_element(v).to_json() for v in sorted_entries],
            "db_freshness": summary.db_freshness_display,
            "warnings": result.warnings,
            "scanner_available": result.scanner_available,
        }, project_path=project_root, context="mcp")
