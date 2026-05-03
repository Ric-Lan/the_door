"""CLI command: update — full version update analysis pipeline."""
from __future__ import annotations

import json
import sys

import click


@click.command("update")
@click.argument("old_path", type=click.Path(exists=True))
@click.argument("new_path", type=click.Path(exists=True))
@click.option("--scope", "scope_name", default=None, help="Scope definition 名稱，用於範圍驗核")
@click.option("--json", "output_json", is_flag=True, help="輸出結構化 JSON 報告")
@click.option("--render", is_flag=True, help="輸出 Mermaid diff 圖形")
@click.option("--offline", is_flag=True, help="漏洞掃描使用本地 OSV 資料庫")
@click.option("--skip-timeline", is_flag=True, help="跳過時間軸更新步驟")
@click.option("--provider", default=None, help="LLM provider 覆蓋")
@click.option("--yes", "-y", is_flag=True, help="跳過 LLM 成本確認")
@click.option("-o", "--output", "output_file", type=click.Path(), default=None, help="輸出到檔案（UTF-8）")
@click.option("--force-reanalyze", is_flag=True, help="強制重新分析（忽略既存 snapshot）")
def update_cmd(
    old_path: str,
    new_path: str,
    scope_name: str | None,
    output_json: bool,
    render: bool,
    offline: bool,
    skip_timeline: bool,
    provider: str | None,
    yes: bool,
    output_file: str | None,
    force_reanalyze: bool,
):
    """執行完整的版本更新分析管線。

    比較 OLD_PATH（舊版）和 NEW_PATH（新版）兩個 codebase，
    自動執行分析、比對、範圍驗核、時間軸更新，
    輸出互動式版本更新報告。
    """
    from pathlib import Path

    from the_door.core.pipeline.pipeline_orchestrator import PipelineOrchestrator
    from the_door.core.pipeline.report_renderer import ReportRenderer
    from the_door.models import (
        AnalyzeConfig,
        CostConfirmationRequired,
        PipelineConfig,
        PipelineError,
    )

    old = Path(old_path).resolve()
    new = Path(new_path).resolve()

    # Validate old_path ≠ new_path
    if old == new:
        click.echo("錯誤：舊版路徑和新版路徑不可相同", err=True)
        sys.exit(1)

    # Assemble AnalyzeConfig
    analyze_config = AnalyzeConfig(
        provider=provider,
        skip_cost_confirm=yes,
        offline_vuln=offline,
    )

    # Assemble PipelineConfig
    config = PipelineConfig(
        old_path=old,
        new_path=new,
        analyze_config=analyze_config,
        scope_name=scope_name,
        skip_timeline=skip_timeline,
        force_reanalyze=force_reanalyze,
    )

    # Progress messages → stderr
    def progress(msg: str) -> None:
        click.echo(msg, err=True)

    # Run pipeline
    orchestrator = PipelineOrchestrator()
    try:
        result = orchestrator.run(config, progress_callback=progress)
    except CostConfirmationRequired as e:
        click.echo(
            f"Estimated cost: ${e.estimated_cost:.4f} ({e.total_tokens} tokens)",
            err=True,
        )
        if not click.confirm("Proceed?"):
            click.echo("Aborted.", err=True)
            sys.exit(0)
        # User confirmed — re-run with skip_cost_confirm=True
        confirmed_analyze = AnalyzeConfig(
            provider=provider,
            skip_cost_confirm=True,
            offline_vuln=offline,
        )
        confirmed_config = PipelineConfig(
            old_path=old,
            new_path=new,
            analyze_config=confirmed_analyze,
            scope_name=scope_name,
            skip_timeline=skip_timeline,
            force_reanalyze=force_reanalyze,
        )
        result = orchestrator.run(confirmed_config, progress_callback=progress)
    except PipelineError as e:
        click.echo(f"錯誤：{e}", err=True)
        sys.exit(1)

    # Render report
    renderer = ReportRenderer()
    if output_json:
        report_data = renderer.render_json(result)
        text = json.dumps(report_data, indent=2, ensure_ascii=False)
    elif render:
        text = renderer.render_mermaid(result)
    else:
        text = renderer.render_markdown(result)

    # Output
    if output_file:
        Path(output_file).write_text(text, encoding="utf-8")
        click.echo(f"Output written to {output_file}", err=True)
    else:
        click.echo(text)
