"""CLI validate command — validates LLM output against Structure JSON."""
from __future__ import annotations

import json
import sys

import click

from the_door.core.validation.output_validator import OutputValidator


@click.command("validate")
@click.argument("llm_output_path")
@click.argument("structure_json_path")
def validate_cmd(llm_output_path: str, structure_json_path: str):
    """Validate LLM output against Structure JSON."""
    try:
        with open(llm_output_path, encoding="utf-8") as f:
            llm_output = json.load(f)
        with open(structure_json_path, encoding="utf-8") as f:
            structure_json = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    validator = OutputValidator()
    result = validator.validate(llm_output, structure_json)

    output = {
        "passed": result.passed,
        "schema": {"passed": result.schema_result.passed, "errors": result.schema_result.errors},
        "coverage": {"passed": result.coverage_result.passed, "errors": result.coverage_result.errors},
        "language": {"passed": result.language_result.passed, "errors": result.language_result.errors},
        "anchor": {"passed": result.anchor_result.passed, "errors": result.anchor_result.errors},
        "relation": {"passed": result.relation_result.passed, "errors": result.relation_result.errors},
    }

    click.echo(json.dumps(output, indent=2))
    if not result.passed:
        sys.exit(1)
