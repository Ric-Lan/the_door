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
    write_versioned_structure,
)
from the_door.core.topology.topology_analyzer import TopologyAnalyzer
from the_door.core.vulnerability.vulnerability_scanner import VulnerabilityScanner
from the_door.models import StructureJSON

logger = logging.getLogger(__name__)


def _count_empty_source_nodes(snapshot) -> int:
    """Return number of features with empty source_nodes.

    source_nodes must be provided by agent-as-LLM; this only counts
    how many need to be filled in.
    """
    return sum(
        1 for feature in snapshot.l1_snapshot.values()
        if not feature.source_nodes
    )


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
@click.option(
    "--as-version", "as_version",
    default=None,
    help=(
        "Backfill .the-door/structures/<vid>.json.gz for an existing snapshot "
        "(no API key needed)."
    ),
)
def extract_cmd(
    codebase_path: str,
    output_file: str | None,
    to_stdout: bool,
    as_version: str | None,
):
    """Extract AST structure and topology from a codebase.

    By default, writes to ``<codebase_path>/.the-door/structure.json``, which
    is the location the viewer's L2 generation and ``/api/structure`` endpoint
    read from. Use ``-o <path>`` to write elsewhere, or ``--stdout`` to print.

    Pass ``--as-version <ref>`` to backfill the per-version persisted gz
    structure for an existing snapshot. This skips LLM calls and writes only
    to ``.the-door/structures/<version_id>.json.gz``.
    """
    # --- O1.3: --as-version backfill path (early return) ---
    if as_version:
        from the_door.cli.main import CliRemediableError
        from the_door.core.diff.snapshot_store import SnapshotStore
        from the_door.core.guidance.remediation import Remediation
        from the_door.models import SnapshotNotFoundError

        if to_stdout:
            raise CliRemediableError(
                Remediation(
                    code="conflicting_flags",
                    message="--as-version cannot be combined with --stdout",
                )
            )

        project_root = Path(codebase_path)
        store = SnapshotStore(project_root)
        try:
            baseline = store.resolve_baseline(as_version)
        except SnapshotNotFoundError:
            baseline = store.get_snapshot(as_version)  # fallback: literal UUID

        if baseline is None:
            raise CliRemediableError(
                Remediation(
                    code="baseline_not_found",
                    message=f"Cannot resolve {as_version!r}",
                )
            )

        try:
            extractor = ASTExtractor()
            result = extractor.extract(codebase_path)
            analyzer = TopologyAnalyzer()
            topology = analyzer.analyze(result.nodes, result.edges)
            structure = StructureJSON(
                files=result.files,
                nodes=result.nodes,
                edges=result.edges,
                topology=topology.entries,
            )
            gz_path = write_versioned_structure(
                project_root, baseline.version_id, structure, scan_result=None
            )
        except (FileNotFoundError, ValueError) as e:
            click.echo(f"Error: {e}", err=True)
            sys.exit(1)

        click.echo(
            f"Backfilled .the-door/structures/{baseline.version_id}.json.gz"
        )

        # Notify agent about source_nodes that need to be filled in
        snapshot = store.get_snapshot(baseline.version_id)
        if snapshot is not None:
            from the_door.core.flow_guard import CheckpointOption, FlowGuard
            from the_door.cli.checkpoint_renderer import CheckpointRenderer
            guard = FlowGuard()
            renderer = CheckpointRenderer(guard)
            empty_count = _count_empty_source_nodes(snapshot)
            decision = guard.check(
                "backfill-complete",
                (
                    f"結構已回填（.the-door/structures/{baseline.version_id}.json.gz）。"
                    f"{empty_count} 個 feature 的 source_nodes 為空，"
                    f"需由 agent 執行 agent-as-LLM 流程補入後再呼叫 snapshot_write 更新。"
                ),
                options=[
                    CheckpointOption(
                        "A", "執行 analyze_changes 驗證差異",
                        f"analyze_changes(codebase_path='{project_root}', baseline='{as_version}')",
                    ),
                    CheckpointOption(
                        "B", "直接開啟 viewer",
                        f"the-door ui {project_root}",
                    ),
                ],
            )
            try:
                renderer.prompt(decision)
            except EOFError:
                pass  # non-interactive environment: skip CHECKPOINT interaction

        from the_door.cli.post_run_hook import cli_post_run_hook
        cli_post_run_hook(codebase_path)
        return

    # --- Legacy flow unchanged ---
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
