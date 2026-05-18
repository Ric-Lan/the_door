"""Unit tests for `the-door update --from-snapshot` flag (Task 04.5 / O1.9).

Three legal call shapes are exercised:

1. Legacy: ``update <old_path> <new_path>`` — still parses cleanly.
2. New incremental: ``update --from-snapshot <ref> <new_path>``.
3. Conflict: ``--from-snapshot <ref> <a> <b>`` raises ``conflicting_flags``.

The happy path (``exit_code == 0`` against a seeded baseline + persisted
structure + a real source delta) is exercised by
``test_update_from_snapshot_runs_to_completion`` below.
"""
from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner


def _seed_minimal_snapshot(project_root: Path, label: str = "v1.0.0") -> str:
    """Persist a minimal empty-L1 snapshot and return its version_id.

    No gzipped structure → pipelines that load one hit the
    ``no_persisted_structure_for_baseline`` remediation, which is exactly
    what the parse-level + remediation-routing assertions want.
    """
    from tests._seed_helpers import seed_baseline_snapshot

    return seed_baseline_snapshot(project_root, label=label).version_id


def test_update_from_snapshot_flag_parses(tmp_path):
    """--from-snapshot is a recognised option (no 'unknown option' error)."""
    from the_door.cli.main import main

    project = tmp_path / "proj"
    project.mkdir()
    _seed_minimal_snapshot(project, label="v1.0.0")

    result = CliRunner().invoke(
        main, ["update", "--from-snapshot", "v1.0.0", str(project)]
    )
    # Parser must accept the option; we do NOT assert success because the
    # minimal seed has no persisted structure → pipeline raises
    # no_persisted_structure_for_baseline (CliRemediableError, exit 1).
    output = (result.output or "") + (result.stderr or "")
    assert "no such option" not in output.lower()
    assert "unknown option" not in output.lower()
    # The known failure mode should be the persisted-structure remediation,
    # not an arg-parse failure.
    assert result.exit_code in (0, 1)
    if result.exit_code == 1:
        assert (
            "no_persisted_structure_for_baseline" in output
            or "持久化" in output
            or "baseline" in output.lower()
        )


def test_update_from_snapshot_with_conflicting_positionals_raises(tmp_path):
    """--from-snapshot + 2 positionals → conflicting_flags remediation."""
    from the_door.cli.main import main

    project = tmp_path / "proj"
    project.mkdir()
    other = tmp_path / "other"
    other.mkdir()
    _seed_minimal_snapshot(project, label="v1.0.0")

    result = CliRunner().invoke(
        main,
        [
            "update",
            "--from-snapshot",
            "v1.0.0",
            str(project),
            str(other),  # second positional is the conflict
        ],
    )
    assert result.exit_code != 0
    combined = (result.output or "") + (result.stderr or "")
    # CliRemediableError renders via render_remediation → message + Try block
    assert "--from-snapshot" in combined
    assert (
        "conflicting_flags" in combined
        or "替代" in combined
        or "replaces" in combined
        or "互斥" in combined
        or "at most one positional" in combined
    )


def test_update_legacy_positional_form_parses(tmp_path):
    """Legacy `update <old> <new>` still accepted at CLI parse level."""
    from the_door.cli.main import main

    old = tmp_path / "old"
    new = tmp_path / "new"
    old.mkdir()
    new.mkdir()

    result = CliRunner().invoke(main, ["update", str(old), str(new)])
    # We don't assert success — the pipeline may fail on empty dirs — but
    # the parser must not reject the positional form, and the early
    # "old == new" guard or any pipeline error is acceptable.
    output = (result.output or "") + (result.stderr or "")
    assert "no such option" not in output.lower()
    assert "got unexpected extra argument" not in output.lower()


def test_update_without_args_and_without_flag_errors(tmp_path):
    """`update` with neither positional pair nor --from-snapshot → usage error."""
    from the_door.cli.main import main

    result = CliRunner().invoke(main, ["update"])
    assert result.exit_code != 0
    output = (result.output or "") + (result.stderr or "")
    # Either click's UsageError ("Usage:") or our explicit usage message.
    assert (
        "Usage" in output
        or "update requires" in output
        or "from-snapshot" in output
    )


def test_update_from_snapshot_runs_to_completion(tmp_path):
    """O1-T9/T10 happy path: the incremental pipeline runs to ``exit_code == 0``
    against a seeded baseline + persisted structure + a real source delta.

    No API key needed — `run_incremental_pipeline` is pure AST + diff
    (no LLM step).
    """
    from the_door.cli.main import main
    from the_door.core.extraction.ast_extractor import ASTExtractor
    from the_door.models import FeatureSummary
    from tests._seed_helpers import seed_baseline_snapshot

    # 1. Write the baseline source tree.
    (tmp_path / "mod_a.py").write_text(
        "def hello():\n    return 'old'\n", encoding="utf-8"
    )

    # 2. Discover real node_ids the extractor will produce so the seeded
    #    snapshot's source_nodes map to nodes that genuinely exist.
    baseline_extraction = ASTExtractor().extract(str(tmp_path))
    baseline_node_ids = tuple(n.node_id for n in baseline_extraction.nodes)
    assert baseline_node_ids, "baseline extraction produced no nodes — fixture broken"

    # 3. Seed a baseline snapshot whose feature owns those real nodes.
    seed_baseline_snapshot(
        tmp_path,
        label="v1.0.0",
        features={
            "feat-hello": FeatureSummary(
                feature_id="feat-hello",
                label="Hello",
                description="hello function family",
                source_node_count=len(baseline_node_ids),
                confidence="high",
                source_nodes=baseline_node_ids,
            )
        },
        analyzed_files=["mod_a.py"],
    )

    # 4. Backfill the v1.0.0 persisted structure via the real CLI
    #    (same `extract --as-version` path the v105_fixture uses).
    backfill = CliRunner().invoke(
        main, ["extract", "--as-version", "v1.0.0", str(tmp_path)]
    )
    assert backfill.exit_code == 0, (
        f"backfill failed: {backfill.output}\n{backfill.stderr or ''}"
    )

    # 5. Apply a real source delta — add a brand-new function so the current
    #    extraction differs from the baseline structure.
    (tmp_path / "mod_a.py").write_text(
        "def hello():\n    return 'new'\n\n\ndef goodbye():\n    return 'b'\n",
        encoding="utf-8",
    )

    # 6. Run the incremental pipeline to completion.
    result = CliRunner().invoke(
        main, ["update", "--from-snapshot", "v1.0.0", str(tmp_path)]
    )
    assert result.exit_code == 0, (
        f"exit={result.exit_code}\nstdout={result.output}\nstderr={result.stderr or ''}"
    )


def test_update_from_snapshot_unresolvable_ref_emits_baseline_not_found(tmp_path):
    """--from-snapshot with non-existent ref → baseline_not_found remediation."""
    from the_door.cli.main import main

    project = tmp_path / "proj"
    project.mkdir()
    # Ensure .the-door dir exists but no matching snapshot.
    (project / ".the-door" / "snapshots").mkdir(parents=True)

    result = CliRunner().invoke(
        main, ["update", "--from-snapshot", "nonexistent-ref", str(project)]
    )
    assert result.exit_code != 0
    output = (result.output or "") + (result.stderr or "")
    assert (
        "baseline_not_found" in output
        or "baseline" in output.lower()
        or "Cannot resolve" in output
    )
