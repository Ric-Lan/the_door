"""CLI command: render — generate Mermaid text from L1 or L1.5 JSON."""
from __future__ import annotations

import json

import click


@click.command("render")
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--output", "-o", type=click.Path(), default=None, help="Output file path")
def render_cmd(input_file: str, output: str | None):
    """Generate Mermaid flowchart text from L1 or L1.5 JSON output."""
    from pathlib import Path
    from the_door.core.rendering.mermaid_renderer import MermaidRenderer
    from the_door.models import L1Output, L1_5Output, Feature, FeatureRelation
    from the_door.models import L1_5Block, BlockRelation, InfrastructureBlock

    content = Path(input_file).read_text(encoding="utf-8")
    data = json.loads(content)

    renderer = MermaidRenderer()

    # Auto-detect L1 vs L1.5
    if "l1_5" in data:
        # Parse L1.5
        l1_5_data = data["l1_5"]
        blocks = [
            L1_5Block(
                block_id=b["block_id"], label=b["label"],
                responsibility=b["responsibility"],
                trigger_mechanism=b["trigger_mechanism"],
                related_features=b.get("related_features", []),
            )
            for b in l1_5_data.get("blocks", [])
        ]
        relations = [
            BlockRelation(
                from_block=r["from"], to_block=r["to"],
                relation=r["relation"], relation_type=r["relation_type"],
                inferred_reason=r.get("inferred_reason"),
            )
            for r in l1_5_data.get("block_relations", [])
        ]
        infra_data = l1_5_data.get("infrastructure_block")
        infra = InfrastructureBlock(
            label=infra_data["label"], components=infra_data.get("components", [])
        ) if infra_data else None

        l1_5 = L1_5Output(blocks=blocks, block_relations=relations, infrastructure_block=infra)
        mermaid = renderer.render_l1_5(l1_5)

    elif "l1" in data:
        # Parse L1
        l1_data = data["l1"]
        features = [
            Feature(
                feature_id=f["feature_id"], label=f["label"],
                description=f["description"], trigger=f["trigger"],
                trigger_description=f["trigger_description"],
                confidence=f["confidence"], confidence_reason=f["confidence_reason"],
                source_nodes=f.get("source_nodes", []),
                needs_source_review=f.get("needs_source_review", False),
                review_reason=f.get("review_reason"),
                source_reviewed=f.get("source_reviewed", False),
            )
            for f in l1_data.get("features", [])
        ]
        relations = [
            FeatureRelation(
                from_feature=r["from"], to_feature=r["to"],
                relation=r["relation"], relation_type=r["relation_type"],
                inferred_reason=r.get("inferred_reason"),
            )
            for r in l1_data.get("feature_relations", [])
        ]
        l1 = L1Output(
            summary=l1_data.get("summary", ""),
            features=features, feature_relations=relations,
        )
        mermaid = renderer.render_l1(l1)
    else:
        click.echo("Error: Input file must contain 'l1' or 'l1_5' key.", err=True)
        raise SystemExit(1)

    if output:
        Path(output).write_text(mermaid, encoding="utf-8")
        click.echo(f"Mermaid output written to {output}")
    else:
        click.echo(mermaid)
