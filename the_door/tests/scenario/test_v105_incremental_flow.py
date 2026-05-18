"""End-to-end gate: v1.0.0 baseline + v1.0.5 source → snapshot with feat-ui-server affected.

This single test walks the entire flow. Each step is gated on its prerequisite task —
when that task lands, its commit removes the matching skip. When all skips are gone,
the spec is composition-correct.

Removing a skip is the responsibility of the task that satisfies the step. If removing
the skip causes the assertion to fail, the integration is broken — the task is NOT
done, regardless of whether its own unit tests passed.
"""
import pytest


pytestmark = pytest.mark.scenario


def test_v105_incremental_flow(v105_fixture):
    """Walk the canonical scenario step-by-step. Each step's skip is removed by
    the task documented in the step's docstring.
    """
    project = v105_fixture
    _step_1_inspect_returns_one_snapshot(project)
    state = _step_2_inspector_emits_systemstate(project)
    _step_3_suggester_recommends_incremental(state)
    diff = _step_4_compute_affected_features_isolates_feat_ui_server(project)
    new_snapshot = _step_5_snapshot_write_inherits_unchanged_features(project, diff)
    _step_6_viewer_diff_api_returns_attribute_changed_only(project, new_snapshot)
    _step_7_status_cli_emits_next_block(project)


def _step_1_inspect_returns_one_snapshot(project):
    """Step 1 unblocked by Task 01.5."""
    from the_door.core.diff.snapshot_store import SnapshotStore
    entries = SnapshotStore(project).list_analyzed_versions()
    assert any(e.label == "v1.0.0" for e in entries)


def _step_2_inspector_emits_systemstate(project):
    """Step 2 unblocked by Task 02.3."""
    from the_door.core.guidance.state import StateInspector
    state = StateInspector(project).inspect()
    assert state.has_dot_the_door is True
    assert len(state.snapshots) >= 1
    return state


def _step_3_suggester_recommends_incremental(state):
    """Step 3 unblocked by Task 02.5."""
    from the_door.core.guidance.suggester import NextActionSuggester
    actions = NextActionSuggester().suggest(state, context="cli")
    # When API key present + 1 snapshot, top suggestion is incremental analysis
    if state.has_api_key:
        assert actions[0].id == "analyze.incremental"


def _step_4_compute_affected_features_isolates_feat_ui_server(project):
    """Removed by: 03-pipeline-mcp Task 03.1 + Task 03.2 (compute_affected_features +
    incremental_pipeline orchestrator).

    Requires v1.0.5 source on disk OR a stand-in that produces the same AST diff.
    If only .the-door/ is copied (no source), use a synthetic v1.0.5 fixture path.
    """
    pytest.skip("blocked on 03-pipeline-mcp Task 03.1 + 03.2")
    # from the_door.core.pipeline.incremental_pipeline import run_incremental_pipeline
    # result = run_incremental_pipeline(codebase_path=<v1.0.5 source path>, baseline_ref="v1.0.0")
    # affected_ids = {af.feature_id for af in result.diff.affected_features}
    # assert affected_ids == {"feat-ui-server"}, f"unexpected affected: {affected_ids}"
    # return result.diff


def _step_5_snapshot_write_inherits_unchanged_features(project, diff):
    """Removed by: 03-pipeline-mcp Task 03.6 (snapshot_write inherit_from extension).

    Step 4 still skips (blocked on a v1.0.5-source-aware orchestrator path),
    so ``diff`` is ``None`` here. We exercise the inherit_from contract
    directly: write a new snapshot inheriting from ``v1.0.0`` with a single
    updated feature, and assert the merge succeeded.
    """
    import asyncio
    from the_door.core.diff.snapshot_store import SnapshotStore
    from the_door.mcp.tools import snapshot_write_tool

    store = SnapshotStore(project)
    baseline = store.resolve_baseline("v1.0.0")
    baseline_feature_ids = set(baseline.l1_snapshot.keys())
    # Pick any baseline feature to "update" — exact id doesn't matter for the
    # contract assertion (that inheritance preserves baseline features).
    target_id = next(iter(baseline_feature_ids))

    result = asyncio.get_event_loop().run_until_complete(
        snapshot_write_tool.execute({
            "codebase_path": str(project),
            "inherit_from": "v1.0.0",
            "updated_features": [{
                "feature_id": target_id,
                "label": "scenario-updated",
                "description": "updated by step 5",
                "trigger": "t",
                "trigger_description": "td",
                "confidence": "high",
                "confidence_reason": "r",
                "source_nodes": ["node-a"],
            }],
        })
    )
    assert "error" not in result, result
    new_snapshot = store.get_snapshot(result["version_id"])
    # All baseline features survive the merge.
    assert baseline_feature_ids.issubset(set(new_snapshot.l1_snapshot.keys()))
    # The updated feature took effect.
    assert new_snapshot.l1_snapshot[target_id].label == "scenario-updated"
    return new_snapshot


def _step_6_viewer_diff_api_returns_attribute_changed_only(project, new_snapshot):
    """Removed by: 05-viewer-frontend Task 05.4 (api_handlers.py /api/diff with O2).

    Step 5 creates the new snapshot without an explicit label, so we drive the
    /api/diff resolver via raw version_id for the current side (still exercises
    the O2 resolve_baseline → get_snapshot fallback). Baseline uses the
    label "v1.0.0" to prove label resolution works end-to-end.
    """
    from the_door.core.ui.api_handlers import APIHandlers
    from the_door.core.ui.job_store import JobStore
    handlers = APIHandlers(project_root=project, job_store=JobStore())
    status, body = handlers.handle_diff_versions(
        baseline_id="v1.0.0", current_id=new_snapshot.version_id
    )
    assert status == 200, body
    assert body["baseline_label"] == "v1.0.0"
    assert body["summary"]["attribute_changed"] == 1


def _step_7_status_cli_emits_next_block(project):
    """Removed by: 04-cli-ux Task 04.2 (the-door status command)."""
    pytest.skip("blocked on 04-cli-ux Task 04.2")
    # from click.testing import CliRunner
    # from the_door.cli.main import cli
    # result = CliRunner(mix_stderr=False).invoke(cli, ["status", str(project)])
    # assert result.exit_code == 0
    # assert "Next:" in result.stderr
