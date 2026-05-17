"""CLI command: estimate — show token/cost preview."""
from __future__ import annotations

import json

import click


@click.command("estimate")
@click.argument("codebase_path", type=click.Path(exists=True))
@click.option("--provider", default=None, help="LLM provider (openai/anthropic/ollama)")
@click.option("--model", default=None, help="Model name override")
@click.option("--output", "-o", type=click.Path(), default=None, help="Output file path")
def estimate_cmd(codebase_path: str, provider: str | None, model: str | None, output: str | None):
    """Show estimated token count and API cost for analyzing a codebase."""
    from pathlib import Path
    from the_door.core.extraction.ast_extractor import ASTExtractor
    from the_door.core.topology.topology_analyzer import TopologyAnalyzer
    from the_door.core.llm.config_manager import ConfigManager
    from the_door.core.rendering.cost_estimator import CostEstimator
    from the_door.models import StructureJSON

    config = ConfigManager.load()
    if provider:
        config.default_provider = provider

    provider_name = config.default_provider
    model_name = model or getattr(config, f"{provider_name}_model", "")

    # Extract structure
    extractor = ASTExtractor()
    extraction = extractor.extract(Path(codebase_path))
    analyzer = TopologyAnalyzer()
    topo_result = analyzer.analyze(extraction.nodes, extraction.edges)

    structure = StructureJSON(
        files=extraction.files,
        nodes=extraction.nodes,
        edges=extraction.edges,
        topology=topo_result.entries,
    )

    # Estimate
    estimator = CostEstimator(provider_name=provider_name, model_name=model_name)
    estimate = estimator.estimate(structure)

    result = {
        "provider": estimate.provider,
        "model": estimate.model,
        "batch_count": estimate.batch_count,
        "total_input_tokens": estimate.total_input_tokens,
        "total_output_tokens": estimate.total_output_tokens,
        "estimated_cost_usd": estimate.estimated_cost_usd,
        "is_local": estimate.is_local,
        "node_count": len(structure.nodes),
    }

    if estimate.is_local:
        click.echo(f"Provider: {provider_name} (local) — free")
    else:
        click.echo(f"Provider: {provider_name} / {model_name}")
        click.echo(f"Estimated cost: ${estimate.estimated_cost_usd:.4f}")

    click.echo(f"Nodes: {len(structure.nodes)}, Batches: {estimate.batch_count}")
    click.echo(f"Tokens: {estimate.total_input_tokens} input + {estimate.total_output_tokens} output")

    json_output = json.dumps(result, indent=2)
    if output:
        Path(output).write_text(json_output, encoding="utf-8")
    else:
        click.echo(json_output)

    from the_door.cli.post_run_hook import cli_post_run_hook
    cli_post_run_hook(codebase_path, json_mode_active=False)
