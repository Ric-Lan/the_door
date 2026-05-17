"""Incremental analysis orchestrator (O1).

Glue layer: resolve baseline snapshot + persisted structure, extract current
codebase AST, then attribute changes back to baseline L1 features via
``compute_affected_features``.

All error paths raise :class:`IncrementalAnalysisError` carrying a
:class:`Remediation` so the CLI/MCP surface can show actionable next steps.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from the_door.core.diff.feature_attribution import (
    IncrementalDiff,
    compute_affected_features,
)
from the_door.core.diff.snapshot_store import SnapshotStore
from the_door.core.extraction.ast_extractor import ASTExtractor
from the_door.core.guidance.actions import NextAction
from the_door.core.guidance.remediation import Remediation
from the_door.models import StructureJSON, VersionSnapshot


@dataclass(frozen=True)
class IncrementalResult:
    """Outcome of a successful incremental pipeline run."""

    diff: IncrementalDiff
    baseline_label: str | None


class IncrementalAnalysisError(Exception):
    """Raised when the incremental pipeline cannot complete.

    The attached :class:`Remediation` describes the failure code, a
    human-readable message, and a :class:`NextAction` the user can run
    to recover.
    """

    def __init__(self, remediation: Remediation):
        super().__init__(remediation.message)
        self.remediation = remediation


def _resolve_baseline(store: SnapshotStore, baseline_ref: str) -> VersionSnapshot | None:
    """Resolve ``baseline_ref`` via tag/date/label, then fall back to version_id.

    Returns ``None`` if no snapshot matches — the orchestrator turns that into
    the ``baseline_not_found`` remediation.
    """
    try:
        return store.resolve_baseline(baseline_ref)
    except Exception:
        return store.get_snapshot(baseline_ref)


def _extraction_result_to_structure(result) -> StructureJSON:
    """Project an ``ExtractionResult`` onto the ``StructureJSON`` shape that
    :func:`compute_affected_features` consumes.

    ``ASTExtractor.extract`` returns ``ExtractionResult`` (which carries
    errors/warnings in addition to files/nodes/edges); the diff layer only
    needs the pure structural fields.
    """
    return StructureJSON(
        files=list(result.files),
        nodes=list(result.nodes),
        edges=list(result.edges),
        topology=[],
    )


def run_incremental_pipeline(
    codebase_path: Path | str, baseline_ref: str
) -> IncrementalResult:
    """Run the incremental analysis pipeline against ``codebase_path``.

    Parameters
    ----------
    codebase_path:
        Project root containing ``.the-door/snapshots/`` and (ideally)
        ``.the-door/structures/<version_id>.json.gz``.
    baseline_ref:
        Git tag, ISO date, manual label, commit SHA, or raw version_id.

    Raises
    ------
    IncrementalAnalysisError
        When the baseline cannot be resolved or its persisted AST is missing.
    """
    codebase_path = Path(codebase_path)
    store = SnapshotStore(codebase_path)

    baseline = _resolve_baseline(store, baseline_ref)
    if baseline is None:
        raise IncrementalAnalysisError(
            Remediation(
                code="baseline_not_found",
                message=f"Cannot resolve baseline {baseline_ref!r}",
                next_action=NextAction(
                    id="system_status.show",
                    title="查看可用 snapshot",
                    rationale="列出目前 .the-door/snapshots 內容",
                    priority=1,
                    cli_command=f"the-door status {codebase_path.as_posix()}",
                ),
            )
        )

    baseline_structure = store.get_structure(baseline.version_id)
    if baseline_structure is None:
        raise IncrementalAnalysisError(
            Remediation(
                code="no_persisted_structure_for_baseline",
                message=(
                    f"Baseline {baseline_ref!r} 缺少持久化 AST。"
                    " 如仍有原始碼：跑 `the-door extract --as-version <baseline_ref>"
                    " <baseline_source_path>` 補檔（不需 API key）。"
                    " 如原始碼已遺失：以 `the-door analyze <current_path>` 重跑完整分析。"
                ),
                next_action=NextAction(
                    id="extract.backfill_structure",
                    title="補既有 baseline 的 persisted structure",
                    rationale="增量分析需要 baseline 的 AST 結構檔。",
                    priority=1,
                    cli_command=(
                        f"the-door extract --as-version {baseline_ref}"
                        " <baseline_source_path>"
                    ),
                ),
            )
        )

    extraction = ASTExtractor().extract(str(codebase_path))
    current_structure = _extraction_result_to_structure(extraction)
    diff = compute_affected_features(baseline_structure, current_structure, baseline)
    return IncrementalResult(diff=diff, baseline_label=baseline.label)
