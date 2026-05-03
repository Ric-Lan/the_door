"""MCP tool: update — execute full version update analysis pipeline."""
from __future__ import annotations

TOOL_SCHEMA = {
    "type": "object",
    "required": ["old_path", "new_path"],
    "properties": {
        "old_path": {
            "type": "string",
            "description": "舊版 codebase 根目錄路徑",
        },
        "new_path": {
            "type": "string",
            "description": "新版 codebase 根目錄路徑",
        },
        "scope_name": {
            "type": "string",
            "description": "Scope definition 名稱（可選）",
        },
        "offline_vuln": {
            "type": "boolean",
            "default": False,
            "description": "漏洞掃描使用本地 OSV 資料庫",
        },
        "skip_timeline": {
            "type": "boolean",
            "default": False,
            "description": "跳過時間軸更新",
        },
        "output_format": {
            "type": "string",
            "enum": ["json", "markdown", "mermaid"],
            "default": "json",
            "description": "輸出格式",
        },
    },
}


async def execute(arguments: dict) -> dict:
    """Execute the update MCP tool.

    Returns the UpdateReport in the requested format.
    MCP environment defaults: AnalyzeConfig.skip_cost_confirm = True
    (MCP clients cannot do interactive cost confirmation).
    """
    from pathlib import Path

    from the_door.core.pipeline.pipeline_orchestrator import PipelineOrchestrator
    from the_door.core.pipeline.report_renderer import ReportRenderer
    from the_door.models import (
        AnalyzeConfig,
        PipelineConfig,
        PipelineError,
    )

    old_path = arguments.get("old_path", "")
    new_path = arguments.get("new_path", "")
    scope_name = arguments.get("scope_name")
    offline_vuln = arguments.get("offline_vuln", False)
    skip_timeline = arguments.get("skip_timeline", False)
    output_format = arguments.get("output_format", "json")

    # Validate paths
    old = Path(old_path)
    new = Path(new_path)

    if not old.exists():
        return {"error": f"舊版路徑不存在：{old_path}"}
    if not old.is_dir():
        return {"error": f"舊版路徑不是目錄：{old_path}"}
    if not new.exists():
        return {"error": f"新版路徑不存在：{new_path}"}
    if not new.is_dir():
        return {"error": f"新版路徑不是目錄：{new_path}"}
    if old.resolve() == new.resolve():
        return {"error": "舊版路徑和新版路徑不可相同"}

    # MCP environment: skip_cost_confirm defaults to True
    analyze_config = AnalyzeConfig(
        skip_cost_confirm=True,
        offline_vuln=offline_vuln,
    )

    config = PipelineConfig(
        old_path=old.resolve(),
        new_path=new.resolve(),
        analyze_config=analyze_config,
        scope_name=scope_name,
        skip_timeline=skip_timeline,
    )

    orchestrator = PipelineOrchestrator()
    try:
        result = orchestrator.run(config)
    except PipelineError as e:
        return {"error": str(e)}
    except Exception as e:
        return {"error": f"管線執行失敗：{e}"}

    # Render report in requested format
    renderer = ReportRenderer()
    if output_format == "markdown":
        return {"markdown": renderer.render_markdown(result)}
    elif output_format == "mermaid":
        return {"mermaid": renderer.render_mermaid(result)}
    else:
        # Default: JSON
        return renderer.render_json(result)
