from pathlib import Path

import pytest

from the_door.core.diff.snapshot_store import SnapshotEntry
from the_door.core.guidance.state import StateWarning, SystemState
from the_door.core.guidance.suggester import NextActionSuggester


def test_suggester_empty_state_suggests_first_extract():
    state = SystemState(
        project_path=Path("/x"),
        has_dot_the_door=False,
        has_structure_json=False,
        snapshots=(),
        l2_features_analyzed=frozenset(),
        warnings=(),
    )
    actions = NextActionSuggester().suggest(state, context="cli")
    assert len(actions) >= 1
    # Zero-key terminal state (T5-A): the single first-time path is agent-as-LLM.
    assert actions[0].id == "extract.first_time"
    assert actions[0].mcp_tool == "extract_structure"


def test_suggester_one_snapshot_suggests_incremental():
    state = SystemState(
        project_path=Path("/x"),
        has_dot_the_door=True,
        has_structure_json=True,
        snapshots=(SnapshotEntry("v1", "v1.0.0", (), None, "2026-01-01T00:00:00Z", True),),
        l2_features_analyzed=frozenset(),
        warnings=(),
    )
    top = NextActionSuggester().suggest(state, context="cli")[0]
    # Incremental path collapses to agent-as-LLM analyze_changes (no key path).
    assert top.id == "analyze_changes.incremental"
    assert top.mcp_tool == "analyze_changes"
    assert top.mcp_arguments["baseline"] == "v1.0.0"


def test_suggester_two_snapshots_viewer_context():
    state = SystemState(
        project_path=Path("/x"),
        has_dot_the_door=True,
        has_structure_json=True,
        snapshots=(
            SnapshotEntry("v2", "v1.0.5", (), None, "2026-02-01T00:00:00Z", True),
            SnapshotEntry("v1", "v1.0.0", (), None, "2026-01-01T00:00:00Z", True),
        ),
        l2_features_analyzed=frozenset(),
        warnings=(),
    )
    actions = NextActionSuggester().suggest(state, context="viewer")
    assert any(a.id == "viewer.open" for a in actions)


def test_suggester_incremental_present_in_cli_context():
    # The collapsed single path surfaces on both cli and mcp (no key-gated split).
    state = SystemState(
        project_path=Path("/x"),
        has_dot_the_door=True,
        has_structure_json=True,
        snapshots=(SnapshotEntry("v1", "v1.0.0", (), None, "2026-01-01T00:00:00Z", True),),
        l2_features_analyzed=frozenset(),
        warnings=(),
    )
    cli_actions = NextActionSuggester().suggest(state, context="cli")
    assert any(a.id == "analyze_changes.incremental" for a in cli_actions)


def test_suggester_drift_warning_suggests_repair():
    state = SystemState(
        project_path=Path("/x"),
        has_dot_the_door=True,
        has_structure_json=True,
        snapshots=(SnapshotEntry("v1", "v1.0.0", (), None, "2026-01-01T00:00:00Z", True),),
        l2_features_analyzed=frozenset(),
        warnings=(
            StateWarning(
                code="source_nodes_drift",
                location="snapshot/v1/feat-x",
                message="...",
                remediation_code=None,
            ),
        ),
    )
    actions = NextActionSuggester().suggest(state, context="cli")
    assert any(a.id == "extract.repair_drift" for a in actions)


def test_h9_repair_drift_rationale_mentions_edge_residue():
    """水平推廣 H-9：repair_drift rationale 含 edge_residue（與 snapshot_patch gate 一致）。"""
    state = SystemState(
        project_path=Path("/x"), has_dot_the_door=True, has_structure_json=True,
        snapshots=(SnapshotEntry("v1", "v1.0.0", (), None, "2026-01-01T00:00:00Z", True),),
        l2_features_analyzed=frozenset(),
        warnings=(StateWarning(code="source_nodes_drift", location="snapshot/v1/feat-x",
                               message="...", remediation_code=None),),
    )
    actions = NextActionSuggester().suggest(state, context="cli")
    repair = next(a for a in actions if a.id == "extract.repair_drift")
    assert "edge_residue" in repair.rationale


def test_c5_2_unstamped_suggests_edge_residue_not_snapshot_write():
    """C5-2：有 structure、無 snapshot、未蓋章 → top edge_residue.run；snapshot.write_first 不在列。"""
    state = SystemState(
        project_path=Path("/x"),
        has_dot_the_door=True, has_structure_json=True,
        snapshots=(),
        l2_features_analyzed=frozenset(), warnings=(),
        edge_residue_stamped=False,
    )
    # agent surface = mcp (snapshot_write/edge_residue are MCP tools the agent runs).
    actions = NextActionSuggester().suggest(state, context="mcp")
    assert actions[0].id == "edge_residue.run"
    assert actions[0].mcp_tool == "edge_residue"
    assert all(a.id != "snapshot.write_first" for a in actions)


def test_c5_3_stamped_suggests_snapshot_write():
    """C5-3：有 structure、無 snapshot、已蓋章 → top snapshot.write_first；edge_residue.run 不在列。"""
    state = SystemState(
        project_path=Path("/x"),
        has_dot_the_door=True, has_structure_json=True,
        snapshots=(),
        l2_features_analyzed=frozenset(), warnings=(),
        edge_residue_stamped=True,
    )
    actions = NextActionSuggester().suggest(state, context="mcp")
    assert actions[0].id == "snapshot.write_first"
    assert actions[0].mcp_tool == "snapshot_write"
    assert all(a.id != "edge_residue.run" for a in actions)


def test_c5_4_chain_rationales_mention_edge_residue():
    """C5-4：first_time / incremental 的 rationale prose 含 edge_residue（與 gate 一致）。"""
    first_time_state = SystemState(
        project_path=Path("/x"), has_dot_the_door=False, has_structure_json=False,
        snapshots=(), l2_features_analyzed=frozenset(), warnings=(),
    )
    ft = NextActionSuggester().suggest(first_time_state, context="cli")
    assert any(a.id == "extract.first_time" and "edge_residue" in a.rationale for a in ft)

    incremental_state = SystemState(
        project_path=Path("/x"), has_dot_the_door=True, has_structure_json=True,
        snapshots=(SnapshotEntry("v1", "v1.0.0", (), None, "2026-01-01T00:00:00Z", True),),
        l2_features_analyzed=frozenset(), warnings=(),
    )
    inc = NextActionSuggester().suggest(incremental_state, context="cli")
    assert any(a.id == "analyze_changes.incremental" and "edge_residue" in a.rationale for a in inc)


def test_c5_3b_inspector_to_suggester_seam(tmp_path):
    """C5-3b：走真實 StateInspector→suggester，釘 producer↔consumer 接縫。"""
    from the_door.core.checklist import STAGE_EDGE_RESIDUE, stamp_stage
    from the_door.core.guidance.state import StateInspector

    # 有 structure.json、無 snapshot、未蓋章 → edge_residue.run
    dot = tmp_path / ".the-door"
    dot.mkdir()
    (dot / "structure.json").write_text("{}", encoding="utf-8")
    state = StateInspector(tmp_path).inspect()
    assert NextActionSuggester().suggest(state, context="mcp")[0].id == "edge_residue.run"

    # 蓋 edge_residue 後 → snapshot.write_first
    stamp_stage(tmp_path, STAGE_EDGE_RESIDUE, covered_nodes=["a"], contract_version="1")
    state2 = StateInspector(tmp_path).inspect()
    assert NextActionSuggester().suggest(state2, context="mcp")[0].id == "snapshot.write_first"


def test_suggester_is_deterministic():
    state = SystemState(
        project_path=Path("/x"),
        has_dot_the_door=False,
        has_structure_json=False,
        snapshots=(),
        l2_features_analyzed=frozenset(),
        warnings=(),
    )
    s = NextActionSuggester()
    assert s.suggest(state, "cli") == s.suggest(state, "cli")


def test_suggester_after_error_boosts_failure_code():
    state = SystemState(
        project_path=Path("/x"),
        has_dot_the_door=True,
        has_structure_json=True,
        snapshots=(SnapshotEntry("v1", "v1.0.0", (), None, "2026-01-01T00:00:00Z", False),),
        l2_features_analyzed=frozenset(),
        warnings=(),
    )
    top = NextActionSuggester().suggest(
        state, context="after_error", failure_code="no_persisted_structure_for_baseline"
    )[0]
    assert top.id == "extract.backfill_structure"


def test_suggester_fallback_always_present():
    state = SystemState(
        project_path=Path("/x"),
        has_dot_the_door=False,
        has_structure_json=False,
        snapshots=(),
        l2_features_analyzed=frozenset(),
        warnings=(),
    )
    actions = NextActionSuggester().suggest(state, context="cli")
    assert any(a.id == "onboarding.read_claude_md" for a in actions)


def test_suggester_after_error_no_snapshot_boost():
    """no_snapshot_for_baseline failure code should boost snapshot.write_first to priority 1."""
    state = SystemState(
        project_path=Path("/x"),
        has_dot_the_door=True, has_structure_json=True,
        snapshots=(),  # no snapshots yet
        l2_features_analyzed=frozenset(),
        warnings=(),
        edge_residue_stamped=True,  # C5: write_first now requires edge_residue done
    )
    top = NextActionSuggester().suggest(
        state, context="after_error",
        failure_code="no_snapshot_for_baseline",
    )[0]
    assert top.id == "snapshot.write_first"


from hypothesis import given, strategies as st


def _state_that_triggers(boost_target_id: str) -> "SystemState":
    """Construct a minimal state whose rule for boost_target_id has predicate True."""
    base_kwargs = dict(
        project_path=Path("/x"),
        has_dot_the_door=True, has_structure_json=True,
        l2_features_analyzed=frozenset(), warnings=(),
        edge_residue_stamped=True,  # C5: write_first now gated on edge_residue done
    )
    if boost_target_id == "extract.backfill_structure":
        return SystemState(
            snapshots=(SnapshotEntry("v1", "v1.0.0", (), None, "2026-01-01T00:00:00Z", False),),
            **base_kwargs,
        )
    if boost_target_id == "snapshot.write_first":
        return SystemState(snapshots=(), **base_kwargs)
    if boost_target_id == "system_status.show":
        # system_status always-true rule — any state works
        return SystemState(snapshots=(), **base_kwargs)
    raise ValueError(f"no state factory for {boost_target_id}")


@given(failure_code=st.sampled_from(list({
    "no_persisted_structure_for_baseline",
    "baseline_not_found",
    "snapshot_not_found",
    "no_snapshot_for_baseline",
})))
def test_property_every_boost_target_reachable_in_after_error_context(failure_code):
    """Invariant: every entry in _AFTER_ERROR_BOOST maps to an action_id that
    the suggester actually emits as the top action when given that failure_code."""
    from the_door.core.guidance.suggester import _AFTER_ERROR_BOOST
    boost_target_id = _AFTER_ERROR_BOOST[failure_code]
    state = _state_that_triggers(boost_target_id)
    actions = NextActionSuggester().suggest(state, context="after_error", failure_code=failure_code)
    assert actions, f"no actions generated for failure_code={failure_code}"
    assert actions[0].id == boost_target_id, (
        f"boost broken: failure_code={failure_code!r} should promote "
        f"{boost_target_id!r} to top, got {actions[0].id!r}"
    )
