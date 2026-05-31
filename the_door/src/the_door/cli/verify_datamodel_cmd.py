"""CLI verify-data-model — Tier 0 local localization (+ --deep candidate list for agent Tier 1)."""
from __future__ import annotations

import click

from the_door.core.extraction.ast_extractor import ASTExtractor
from the_door.core.datamodel.datamodel_localizer import DataModelLocalizer
from the_door.core.datamodel.datamodel_renderer import render_localization


@click.command("verify-data-model")
@click.argument("codebase_path")
@click.option("--deep", is_flag=True, default=False,
              help="Emit the candidate file list + agent Tier 1 instructions (no LLM call).")
def verify_datamodel_cmd(codebase_path: str, deep: bool) -> None:
    """Localize data-model touch points (Tier 0); --deep prints the Tier 1 hand-off."""
    result = ASTExtractor().extract(codebase_path)
    loc = DataModelLocalizer().localize(result, codebase_path)
    click.echo(render_localization(loc))
    if deep:
        click.echo("")
        click.echo("Next (Tier 1, hand to your agent — no API key needed):")
        files = sorted(
            {c.file for c in loc.code_candidates} | {c.file for c in loc.schema_candidates}
        )
        for f in files:
            click.echo(f"  read: {f}")
        click.echo("  then call MCP verify_data_model_contract with the normalized field-sets.")
