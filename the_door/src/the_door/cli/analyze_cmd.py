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
    from the_door.models import AnalyzeConfig, CostConfirmationRequired
    from the_door.core.pipeline.analyze_pipeline import run_analyze_pipeline

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
