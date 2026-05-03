"""Analyze pipeline — reusable core function extracted from cli/analyze_cmd.py.

Orchestrates: file fingerprint → config load → parallel AST extraction + vuln scan
→ topology → cost estimation → LLM batch reading → auto-snapshot → AnalyzeResult.

All file I/O uses encoding="utf-8" for Windows compatibility.
"""
from __future__ import annotations

import asyncio
import logging
import subprocess
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from the_door.core.diff.snapshot_store import SnapshotStore
from the_door.core.extraction.ast_extractor import ASTExtractor
from the_door.core.extraction.file_discovery import FileDiscovery
from the_door.core.llm.config_manager import ConfigManager
from the_door.core.llm.provider import create_provider
from the_door.core.reading.batch_reader import BatchReader
from the_door.core.rendering.cost_estimator import CostEstimator
from the_door.core.rendering.mermaid_renderer import build_confidence_marker
from the_door.core.topology.topology_analyzer import TopologyAnalyzer
from the_door.core.vulnerability.vulnerability_scanner import VulnerabilityScanner
from the_door.models import (
    AnalyzeConfig,
    AnalyzeError,
    AnalyzeResult,
    CostConfirmationRequired,
    FeatureSummary,
    RelationSummary,
    ScanResult,
    StructureJSON,
)

logger = logging.getLogger(__name__)


def _noop_progress(msg: str) -> None:
    """Default no-op progress callback."""


def run_analyze_pipeline(
    codebase_path: Path,
    config: AnalyzeConfig,
    *,
    progress_callback: Callable[[str], None] | None = None,
) -> AnalyzeResult:
    """Execute the full analysis pipeline.

    This function contains ALL the analysis logic previously in cli/analyze_cmd.py,
    made reusable for both CLI and Pipeline_Orchestrator.

    Parameters
    ----------
    codebase_path : Path
        Root directory of the codebase to analyse.
    config : AnalyzeConfig
        Pipeline configuration (provider, model, skip_cost_confirm, offline_vuln).
    progress_callback : Callable[[str], None] | None
        Optional progress reporter. CLI passes ``click.echo(err=True)``,
        MCP passes ``logger.info``.

    Returns
    -------
    AnalyzeResult
        Complete analysis result including snapshot, L1 output, scan result,
        file fingerprint, batch/token counts.

    Raises
    ------
    AnalyzeError
        Unrecoverable analysis error.
    CostConfirmationRequired
        When estimated cost exceeds threshold and ``skip_cost_confirm`` is False.
    """
    progress = progress_callback or _noop_progress

    try:
        return _run_pipeline_inner(codebase_path, config, progress)
    except (AnalyzeError, CostConfirmationRequired):
        raise
    except Exception as exc:
        raise AnalyzeError(f"Analysis failed: {exc}") from exc


def _run_pipeline_inner(
    codebase_path: Path,
    config: AnalyzeConfig,
    progress: Callable[[str], None],
) -> AnalyzeResult:
    """Inner implementation — separated so the outer function can wrap exceptions."""

    # 1. Compute file fingerprint
    file_fingerprint = compute_file_fingerprint(codebase_path)

    # 2. Load config (ConfigManager.load() + overrides from AnalyzeConfig)
    td_config = ConfigManager.load()
    if config.provider:
        td_config.default_provider = config.provider
    if config.model:
        if td_config.default_provider == "openai":
            td_config.openai_model = config.model
        elif td_config.default_provider == "anthropic":
            td_config.anthropic_model = config.model
        elif td_config.default_provider == "ollama":
            td_config.ollama_model = config.model

    progress(f"Provider: {td_config.default_provider}")

    # 3. Parallel AST extraction + vulnerability scan
    progress(f"Extracting structure from {codebase_path}...")
    extractor = ASTExtractor()
    scanner = VulnerabilityScanner(offline=config.offline_vuln)

    with ThreadPoolExecutor(max_workers=2) as executor:
        ast_future = executor.submit(extractor.extract, Path(codebase_path))
        vuln_future = executor.submit(scanner.scan, Path(codebase_path))

        extraction = ast_future.result()

        # Vulnerability scan is non-fatal — proceed with empty on failure
        try:
            scan_result = vuln_future.result()
        except Exception as e:
            logger.warning("Vulnerability scan failed: %s", e)
            scan_result = ScanResult(entries=[], warnings=[str(e)])

    # 4. Topology analysis
    analyzer = TopologyAnalyzer()
    topo_result = analyzer.analyze(extraction.nodes, extraction.edges)

    structure = StructureJSON(
        files=extraction.files,
        nodes=extraction.nodes,
        edges=extraction.edges,
        topology=topo_result.entries,
    )

    # 5. Cost estimation
    estimator = CostEstimator(
        provider_name=td_config.default_provider,
        model_name=getattr(td_config, f"{td_config.default_provider}_model", ""),
    )
    estimate = estimator.estimate(structure)

    if not config.skip_cost_confirm and estimate.estimated_cost_usd > td_config.cost_warning_threshold:
        raise CostConfirmationRequired(
            estimated_cost=estimate.estimated_cost_usd,
            total_tokens=estimate.total_input_tokens + estimate.total_output_tokens,
        )

    # 6. LLM batch reading
    progress("Running batch analysis...")
    llm_provider = create_provider(td_config)
    reader = BatchReader(llm_provider=llm_provider, structure=structure)
    result = asyncio.run(reader.read())

    # 7. Build output_data dict
    output_data = _build_output_data(result, scan_result, td_config)

    # 8. Auto-snapshot creation (git info detection)
    snapshot = _create_auto_snapshot(
        codebase_path, extraction, result, scan_result, progress,
    )

    return AnalyzeResult(
        snapshot=snapshot,
        l1_output=result.l1_output,
        l1_output_data=output_data,
        scan_result=scan_result,
        file_fingerprint=file_fingerprint,
        total_batches=result.total_batches,
        total_tokens=result.total_tokens_used,
    )


def _build_output_data(result, scan_result: ScanResult, td_config) -> dict:
    """Build the output_data dict (same format as the original analyze_cmd)."""
    output_data: dict = {
        "l1": {
            "summary": result.l1_output.summary,
            "features": [
                {
                    "feature_id": f.feature_id,
                    "label": f.label,
                    "description": f.description,
                    "trigger": f.trigger,
                    "trigger_description": f.trigger_description,
                    "confidence": f.confidence,
                    "confidence_reason": f.confidence_reason,
                    "source_nodes": list(f.source_nodes),
                    "confidence_marker": build_confidence_marker(f),
                }
                for f in result.l1_output.features
            ],
            "feature_relations": [
                {
                    "from": r.from_feature,
                    "to": r.to_feature,
                    "relation": r.relation,
                    "relation_type": r.relation_type,
                    "inferred_reason": r.inferred_reason,
                }
                for r in result.l1_output.feature_relations
            ],
            "unclassified_nodes": result.l1_output.unclassified_nodes,
            "infrastructure_nodes": result.l1_output.infrastructure_nodes,
        },
        "vulnerabilities": [
            {
                "cve_id": v.cve_id,
                "package": v.package,
                "version": v.version,
                "severity": v.severity,
                "cvss": v.cvss,
                "source": v.source,
            }
            for v in scan_result.entries
        ],
        "meta": {
            "provider": td_config.default_provider,
            "total_batches": result.total_batches,
            "total_tokens": result.total_tokens_used,
        },
    }

    if scan_result.db_freshness:
        output_data["vulnerability_db_freshness"] = {
            "timestamp": scan_result.db_freshness.timestamp,
            "mode": scan_result.db_freshness.mode,
            "stale_warning": scan_result.db_freshness.stale_warning,
        }

    return output_data


def _create_auto_snapshot(codebase_path, extraction, result, scan_result, progress):
    """Create an auto-snapshot with git info detection.

    Snapshot failure is non-fatal — returns the snapshot on success,
    raises AnalyzeError only if snapshot creation itself fails critically.
    """
    # Extract git info
    git_commit = None
    git_tags_list: list[str] = []
    try:
        git_commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, cwd=str(Path(codebase_path)),
            timeout=5,
        ).stdout.strip() or None

        if git_commit:
            tags_output = subprocess.run(
                ["git", "tag", "--points-at", "HEAD"],
                capture_output=True, text=True, cwd=str(Path(codebase_path)),
                timeout=5,
            ).stdout.strip()
            git_tags_list = [t for t in tags_output.split("\n") if t]
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass  # git not available, proceed without

    # Build snapshot data from analysis result
    l1_snap: dict[str, FeatureSummary] = {}
    for f in result.l1_output.features:
        l1_snap[f.feature_id] = FeatureSummary(
            feature_id=f.feature_id,
            label=f.label,
            description=f.description,
            source_node_count=len(f.source_nodes),
            confidence=f.confidence,
        )

    relations = [
        RelationSummary(
            from_feature=r.from_feature,
            to_feature=r.to_feature,
            relation=r.relation,
        )
        for r in result.l1_output.feature_relations
    ]

    analyzed_files_list = [fi.path for fi in extraction.files]

    # Determine trigger
    trigger = "commit" if git_commit else "manual"

    store = SnapshotStore(Path(codebase_path))
    snapshot = store.create_snapshot(
        l1_snapshot=l1_snap,
        feature_relations=relations,
        analyzed_files=analyzed_files_list,
        commit_hash=git_commit,
        git_tags=git_tags_list,
        trigger=trigger,
        vulnerabilities=scan_result.entries if scan_result.entries else [],
        db_freshness=scan_result.db_freshness,
    )
    progress(f"Snapshot saved: {snapshot.version_id[:8]}")
    return snapshot


def compute_file_fingerprint(codebase_path: Path) -> dict[str, tuple[int, float]]:
    """Compute a file fingerprint for the codebase.

    Returns dict[relative_path → (file_size_bytes, mtime_timestamp)].
    Only includes source code files that ASTExtractor would process
    (uses the same FileDiscovery logic).

    Used to determine whether an existing snapshot is still valid.
    """
    discovery = FileDiscovery()
    files = discovery.discover(str(codebase_path))
    root = Path(codebase_path).resolve()

    fingerprint: dict[str, tuple[int, float]] = {}
    for fi in files:
        abs_path = root / fi.path
        try:
            stat = abs_path.stat()
            fingerprint[fi.path] = (stat.st_size, stat.st_mtime)
        except OSError:
            # File disappeared between discovery and stat — skip it
            continue

    return fingerprint


def validate_snapshot_fingerprint(
    stored: dict[str, tuple[int, float]],
    current: dict[str, tuple[int, float]],
) -> bool:
    """Validate that a stored fingerprint matches the current codebase state.

    Compares key sets and each file's (size, mtime).
    Returns True only if key sets are identical AND all sizes and mtimes match.
    Any file addition, deletion, or modification returns False.
    """
    if stored.keys() != current.keys():
        return False

    for path, (stored_size, stored_mtime) in stored.items():
        current_size, current_mtime = current[path]
        if stored_size != current_size or stored_mtime != current_mtime:
            return False

    return True
