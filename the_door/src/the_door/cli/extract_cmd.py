"""CLI extract command — runs AST extraction + topology analysis."""
from __future__ import annotations

import io
import json
import logging
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import click

from the_door.core.extraction.ast_extractor import ASTExtractor
from the_door.core.extraction.structure_serializer import (
    build_structure_dict,
    default_structure_path,
    write_structure_json,
)
from the_door.core.topology.topology_analyzer import TopologyAnalyzer
from the_door.core.vulnerability.vulnerability_scanner import VulnerabilityScanner
from the_door.models import StructureJSON

logger = logging.getLogger(__name__)


def _emit_stdout_utf8(text: str) -> None:
    """Print text to stdout as UTF-8.

    On Windows the default stdout codec follows the system locale
    (e.g. cp950 for Traditional Chinese), which fails when the codebase's
    docstrings or comments contain emoji / CJK chars not in that codepage.
    We reconfigure stdout to UTF-8 before writing.
    """
    try:
        # Python 3.7+ — reconfigure works on TextIOWrapper backing real stdout.
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, io.UnsupportedOperation):
        # Click's CliRunner replaces stdout with a non-reconfigurable buffer;
        # the runner itself doesn't enforce a locale codec so the write below
        # is safe.
        pass
    click.echo(text)


@click.command("extract")
@click.argument("codebase_path")
@click.option(
    "-o", "--output", "output_file",
    default=None,
    help="Output file path (default: <codebase_path>/.the-door/structure.json)",
)
@click.option(
    "--stdout", "to_stdout",
    is_flag=True, default=False,
    help="Print JSON to stdout instead of writing to a file.",
)
def extract_cmd(codebase_path: str, output_file: str | None, to_stdout: bool):
    """Extract AST structure and topology from a codebase.

    By default, writes to ``<codebase_path>/.the-door/structure.json``, which
    is the location the viewer's L2 generation and ``/api/structure`` endpoint
    read from. Use ``-o <path>`` to write elsewhere, or ``--stdout`` to print.
    """
    if output_file and to_stdout:
        click.echo("Error: --stdout cannot be combined with -o/--output.", err=True)
        sys.exit(2)

    try:
        extractor = ASTExtractor()
        scanner = VulnerabilityScanner()

        # Run AST extraction and vulnerability scan in parallel
        with ThreadPoolExecutor(max_workers=2) as executor:
            ast_future = executor.submit(extractor.extract, codebase_path)
            vuln_future = executor.submit(scanner.scan, Path(codebase_path))

            result = ast_future.result()

            # Vulnerability scan is non-fatal — proceed with empty on failure
            try:
                scan_result = vuln_future.result()
            except Exception as e:
                logger.warning("Vulnerability scan failed: %s", e)
                from the_door.models import ScanResult
                scan_result = ScanResult(entries=[], warnings=[str(e)])

        # Run topology analysis
        analyzer = TopologyAnalyzer()
        topology = analyzer.analyze(result.nodes, result.edges)

        # Pack into the canonical StructureJSON dataclass + delegate
        # on-disk shape to the shared serializer (shared with analyze pipeline).
        structure = StructureJSON(
            files=result.files,
            nodes=result.nodes,
            edges=result.edges,
            topology=topology.entries,
        )

        if to_stdout:
            data = build_structure_dict(structure, scan_result)
            _emit_stdout_utf8(json.dumps(data, indent=2, ensure_ascii=False))
            from the_door.cli.post_run_hook import cli_post_run_hook
            cli_post_run_hook(codebase_path, json_mode_active=to_stdout)
            return

        target = Path(output_file) if output_file else default_structure_path(codebase_path)
        write_structure_json(target, structure, scan_result)
        click.echo(f"Structure JSON written to {target}")

        from the_door.cli.post_run_hook import cli_post_run_hook
        cli_post_run_hook(codebase_path, json_mode_active=to_stdout)

    except (FileNotFoundError, ValueError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Unexpected error: {e}", err=True)
        sys.exit(1)
