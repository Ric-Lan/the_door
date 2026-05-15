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
from the_door.core.topology.topology_analyzer import TopologyAnalyzer
from the_door.core.vulnerability.vulnerability_scanner import VulnerabilityScanner

logger = logging.getLogger(__name__)


def _default_output_path(codebase_path: str) -> Path:
    """Where viewer + L2/L3 pipelines read structure.json from."""
    return Path(codebase_path) / ".the-door" / "structure.json"


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

        # Build Structure JSON
        output = {
            "files": [{"path": f.path, "language": f.language} for f in result.files],
            "nodes": [
                {
                    "node_id": n.node_id, "type": n.type, "name": n.name,
                    "file": n.file, "language": n.language,
                    "decorators": n.decorators, "parameters": n.parameters,
                    "return_type": n.return_type, "docstring": n.docstring,
                    "comments": n.comments,
                }
                for n in result.nodes
            ],
            "edges": [
                {"from": e.from_node, "to": e.to_node, "type": e.type}
                for e in result.edges
            ],
            "topology": [
                {
                    "node_id": t.node_id, "in_degree": t.in_degree,
                    "out_degree": t.out_degree, "topology_rank": t.topology_rank,
                    "is_entry_point": t.is_entry_point, "batch_assignment": t.batch_assignment,
                }
                for t in topology.entries
            ],
            "vulnerabilities": [
                {
                    "cve_id": v.cve_id, "package": v.package, "version": v.version,
                    "severity": v.severity, "cvss": v.cvss, "source": v.source,
                }
                for v in scan_result.entries
            ],
        }

        if scan_result.db_freshness:
            output["vulnerability_db_freshness"] = {
                "timestamp": scan_result.db_freshness.timestamp,
                "mode": scan_result.db_freshness.mode,
                "stale_warning": scan_result.db_freshness.stale_warning,
            }

        json_str = json.dumps(output, indent=2, ensure_ascii=False)

        if to_stdout:
            _emit_stdout_utf8(json_str)
            return

        target = Path(output_file) if output_file else _default_output_path(codebase_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json_str, encoding="utf-8")
        click.echo(f"Structure JSON written to {target}")

    except (FileNotFoundError, ValueError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Unexpected error: {e}", err=True)
        sys.exit(1)
