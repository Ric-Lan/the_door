"""CLI command: analyze — one-click mode."""
from __future__ import annotations

import json
import logging
import sys

import click

logger = logging.getLogger(__name__)


@click.command("analyze")
@click.argument("codebase_path", type=click.Path(exists=True))
@click.option("--provider", default=None, help="LLM provider (openai/anthropic/ollama)")
@click.option("--model", default=None, help="Model name override")
@click.option("--yes", "-y", is_flag=True, help="Skip cost confirmation")
@click.option("--output", "-o", type=click.Path(), default=None, help="Output file path")
@click.option("--offline", is_flag=True, help="Use local OSV database for vulnerability scanning")
def analyze_cmd(codebase_path: str, provider: str | None, model: str | None, yes: bool, output: str | None, offline: bool):
    """Run full analysis pipeline: extract → topology → batch read → validate → render."""
    from pathlib import Path
    from the_door.core.flow_guard import CheckpointOption, FlowGuard
    from the_door.cli.checkpoint_renderer import CheckpointRenderer
    from the_door.core.llm.config_manager import ConfigManager
    from the_door.models import AnalyzeConfig, CostConfirmationRequired
    from the_door.core.pipeline.analyze_pipeline import run_analyze_pipeline

    import os
    llm_config = ConfigManager.load()
    if not (
        llm_config.anthropic_api_key
        or llm_config.openai_api_key
        or os.environ.get("ANTHROPIC_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
    ):
        guard = FlowGuard()
        renderer = CheckpointRenderer(guard)
        decision = guard.check(
            "no-api-key",
            "未偵測到 API key（~/.the-door/config.toml 無設定）",
            options=[
                CheckpointOption(
                    "A", "你是 AI agent → 使用 MCP agent-as-LLM 路徑",
                    "extract_structure(codebase_path='<path>')",
                ),
                CheckpointOption(
                    "B", "你是人類使用者 → 設定 API key 後重試",
                    "編輯 ~/.the-door/config.toml：[anthropic] api_key = '...'",
                ),
            ],
        )
        try:
            choice = renderer.prompt(decision)
        except EOFError:
            choice = "A"  # non-interactive (agent context): default to MCP path
        if choice == "B":
            click.echo("請設定 API key 後重新執行。")
            raise SystemExit(0)
        click.echo("請使用 MCP 工具：extract_structure → snapshot_write")
        raise SystemExit(0)

    config = AnalyzeConfig(
        provider=provider,
        model=model,
        skip_cost_confirm=yes,
        offline_vuln=offline,
    )

    progress_callback = lambda msg: click.echo(msg, err=True)

    try:
        result = run_analyze_pipeline(
            Path(codebase_path),
            config,
            progress_callback=progress_callback,
        )
    except CostConfirmationRequired as e:
        click.echo(
            f"Estimated cost: ${e.estimated_cost:.4f} ({e.total_tokens} tokens)"
        )
        if not click.confirm("Proceed?"):
            click.echo("Aborted.")
            sys.exit(0)
        # User confirmed — re-run with skip_cost_confirm=True
        confirmed_config = AnalyzeConfig(
            provider=provider,
            model=model,
            skip_cost_confirm=True,
            offline_vuln=offline,
        )
        result = run_analyze_pipeline(
            Path(codebase_path),
            confirmed_config,
            progress_callback=progress_callback,
        )

    # Output the JSON result
    json_output = json.dumps(result.l1_output_data, indent=2, ensure_ascii=False)

    if output:
        Path(output).write_text(json_output, encoding="utf-8")
        click.echo(f"Output written to {output}")
    else:
        click.echo(json_output)

    from the_door.cli.post_run_hook import cli_post_run_hook
    cli_post_run_hook(codebase_path, json_mode_active=False)
