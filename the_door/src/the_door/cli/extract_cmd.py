"""CLI extract command — runs AST extraction + topology analysis."""
from __future__ import annotations

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


@click.command("extract")
@click.argument("codebase_path")
@click.option("-o", "--output", "output_file", default=None, help="Output file path (default: stdout)")
def extract_cmd(codebase_path: str, output_file: str | None):
    """Extract AST structure and topology from a codebase."""
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

        if output_file:
            Path(output_file).write_text(json_str, encoding="utf-8")
            click.echo(f"Structure JSON written to {output_file}")
        else:
            click.echo(json_str)

    except (FileNotFoundError, ValueError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Unexpected error: {e}", err=True)
        sys.exit(1)
