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
    from the_door.mcp.tools._response_envelope import wrap

    codebase_path = arguments["codebase_path"]
    project_root = Path(arguments.get("codebase_path") or arguments.get("project_path") or Path.cwd())
    offline = arguments.get("offline", False)
    fmt = arguments.get("format", "summary")

    scanner = VulnerabilityScanner(offline=offline)
    result = scanner.scan(Path(codebase_path))

    if fmt == "raw":
        return wrap({
            "vulnerabilities": [
                {
                    "cve_id": v.cve_id,
                    "package": v.package,
                    "version": v.version,
                    "severity": v.severity,
                    "cvss": v.cvss,
                    "source": v.source,
                }
                for v in result.entries
            ],
            "warnings": result.warnings,
            "scanner_available": result.scanner_available,
        }, project_path=project_root, context="mcp")
    else:
        renderer = VulnerabilityRenderer()
        summary = renderer.build_vulnerability_summary(result.entries, result.db_freshness)
        header = renderer.format_summary_header(summary)
        return wrap({
            "header": header,
            "total_critical": summary.total_critical,
            "total_high": summary.total_high,
            "total_medium": summary.total_medium,
            "total_low": summary.total_low,
            "entries": [
                {
                    "cve_id": e.cve_id,
                    "package": e.package,
                    "version": e.version,
                    "severity": e.severity,
                    "cvss": e.cvss,
                    "action": e.action,
                }
                for e in summary.entries
            ],
            "db_freshness": summary.db_freshness_display,
            "warnings": result.warnings,
            "scanner_available": result.scanner_available,
        }, project_path=project_root, context="mcp")
