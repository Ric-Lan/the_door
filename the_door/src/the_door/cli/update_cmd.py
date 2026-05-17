"""CLI command: update — full version update analysis pipeline."""
from __future__ import annotations

import json
import sys

import click


@click.command("update")
@click.argument("path_a", type=click.Path(), required=False)
@click.argument("path_b", type=click.Path(), required=False)
@click.option(
    "--from-snapshot",
    "from_snapshot",
    default=None,
    help=(
        "Baseline snapshot ref (label / tag / SHA / date / UUID)."
        " Mutually exclusive with positional old_path."
    ),
)
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
    path_a: str | None,
    path_b: str | None,
    from_snapshot: str | None,
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

    三種合法呼叫形式：

    \b
    1. ``update <old_path> <new_path>``                    — 傳統雙路徑全量比對
    2. ``update --from-snapshot <ref> <current_path>``     — 對 baseline snapshot 跑增量分析
    3. ``update --from-snapshot <ref>``                    — 同上，預設 current_path = cwd
    """
    from pathlib import Path

    from the_door.cli.main import CliRemediableError
    from the_door.cli.post_run_hook import cli_post_run_hook
    from the_door.core.guidance.actions import NextAction
    from the_door.core.guidance.remediation import Remediation

    # ── Branch A: incremental flow via --from-snapshot ────────────────────
    if from_snapshot:
        # With --from-snapshot we accept AT MOST one positional (the current
        # path). A second positional means the caller is mixing the legacy
        # `<old> <new>` form with the new flag — surface a conflict.
        if path_b is not None:
            raise CliRemediableError(
                Remediation(
                    code="conflicting_flags",
                    message=(
                        "--from-snapshot replaces <old_path>;"
                        " pass at most one positional (the current path)."
                    ),
                    next_action=NextAction(
                        id="update.use_from_snapshot",
                        title="改用 --from-snapshot + 單一 current_path",
                        rationale=(
                            "--from-snapshot 已取代舊版 <old_path>，"
                            "再多一個位置參數會語意混淆。"
                        ),
                        priority=1,
                        cli_command=(
                            f"the-door update --from-snapshot {from_snapshot}"
                            " <current_path>"
                        ),
                    ),
                )
            )

        current_path = Path(path_a).resolve() if path_a else Path.cwd()

        from the_door.core.pipeline.incremental_pipeline import (
            IncrementalAnalysisError,
            run_incremental_pipeline,
        )

        try:
            run_incremental_pipeline(
                codebase_path=current_path, baseline_ref=from_snapshot
            )
        except IncrementalAnalysisError as e:
            raise CliRemediableError(e.remediation) from e

        cli_post_run_hook(current_path, json_mode_active=output_json)
        return

    # ── Branch B: legacy positional form ─────────────────────────────────
    if path_a is None or path_b is None:
        raise click.UsageError(
            "update requires either '<old_path> <new_path>'"
            " or '--from-snapshot <ref> [<current_path>]'"
        )

    old_path = path_a
    new_path = path_b

    # Validate the paths exist (we relaxed click's exists=True so the new
    # incremental branch above can accept defaults / non-required positionals).
    for label, raw in (("OLD_PATH", old_path), ("NEW_PATH", new_path)):
        if not Path(raw).exists():
            raise click.UsageError(f"{label} does not exist: {raw}")

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

    cli_post_run_hook(new_path, json_mode_active=output_json)
