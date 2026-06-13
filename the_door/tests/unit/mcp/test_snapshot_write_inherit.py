"""Tests for snapshot_write_tool inherit_from merge logic + CHECKPOINT (#7)."""
from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from the_door.core.diff.snapshot_store import SnapshotStore
from the_door.models import FeatureSummary, RelationSummary, VersionSnapshot


def _make_feature(fid: str) -> dict:
    return {
        "feature_id": fid,
        "label": fid,
        "description": f"desc {fid}",
        "confidence": "high",
    }


def _make_feature_summary(fid: str) -> FeatureSummary:
    return FeatureSummary(
        feature_id=fid,
        label=fid,
        description=f"desc {fid}",
        source_node_count=0,
        confidence="high",
    )


async def _execute(args: dict) -> dict:
    from the_door.mcp.tools import snapshot_write_tool
    return await snapshot_write_tool.execute(args)


@pytest.fixture
def store_with_baseline(tmp_path):
    """Returns (tmp_path, baseline_version_id) with one baseline snapshot having feat-a, feat-b."""
    # Use default store_root so snapshot_write_tool.execute (which also uses default) can find it.
    store = SnapshotStore(tmp_path)
    snap = store.create_snapshot(
        l1_snapshot={
            "feat-a": _make_feature_summary("feat-a"),
            "feat-b": _make_feature_summary("feat-b"),
        },
        feature_relations=[],
        analyzed_files=[],
        label="baseline",
    )
    return tmp_path, snap.version_id


@pytest.fixture
def store_with_summary_baseline(tmp_path):
    """Baseline snapshot carrying a project_summary."""
    store = SnapshotStore(tmp_path)
    snap = store.create_snapshot(
        l1_snapshot={"feat-a": _make_feature_summary("feat-a")},
        feature_relations=[],
        analyzed_files=[],
        label="baseline",
        project_summary="原始簡介：登入系統。",
    )
    return tmp_path, snap.version_id


@pytest.mark.asyncio
async def test_inherit_carries_baseline_summary_when_not_given(store_with_summary_baseline):
    """Inherit + 未給 project_summary → 沿用 baseline 的簡介（組成未由本欄判定變動）。"""
    tmp_path, vid = store_with_summary_baseline
    result = await _execute({
        "codebase_path": str(tmp_path),
        "inherit_from": vid,
        "updated_features": [_make_feature("feat-a")],
        "label": "v2",
    })
    loaded = SnapshotStore(tmp_path).get_snapshot(result["version_id"])
    assert loaded.project_summary == "原始簡介：登入系統。"


@pytest.mark.asyncio
async def test_inherit_overrides_summary_when_given(store_with_summary_baseline):
    """Inherit + 給 project_summary → 覆寫（信任 agent 判斷組成已變）。"""
    tmp_path, vid = store_with_summary_baseline
    result = await _execute({
        "codebase_path": str(tmp_path),
        "inherit_from": vid,
        "updated_features": [_make_feature("feat-a")],
        "project_summary": "更新簡介：登入＋報表。",
        "label": "v2",
    })
    loaded = SnapshotStore(tmp_path).get_snapshot(result["version_id"])
    assert loaded.project_summary == "更新簡介：登入＋報表。"


@pytest.mark.asyncio
async def test_inherit_no_new_features_no_checkpoint(store_with_baseline):
    """When all features in l1_features are already in baseline → no CHECKPOINT, writes directly."""
    tmp_path, vid = store_with_baseline
    result = await _execute({
        "codebase_path": str(tmp_path),
        "inherit_from": vid,
        "l1_features": [_make_feature("feat-a"), _make_feature("feat-b")],
    })
    assert result.get("result") is not None or "version_id" in result
    assert result.get("checkpoint") is None


@pytest.mark.asyncio
async def test_inherit_new_feature_choice_none_triggers_checkpoint(store_with_baseline):
    """New feat-c not in baseline + choice=None → CHECKPOINT new-features-detected."""
    tmp_path, vid = store_with_baseline
    result = await _execute({
        "codebase_path": str(tmp_path),
        "inherit_from": vid,
        "l1_features": [
            _make_feature("feat-a"),
            _make_feature("feat-b"),
            _make_feature("feat-c"),
        ],
    })
    assert result["result"] is None
    assert result["checkpoint"] == "new-features-detected"
    option_keys = {o["key"] for o in result["options"]}
    assert {"A", "B", "C"} == option_keys


@pytest.mark.asyncio
async def test_inherit_new_feature_choice_a_keeps_new(store_with_baseline):
    """choice=A → baseline features + new feat-c all written."""
    tmp_path, vid = store_with_baseline
    result = await _execute({
        "codebase_path": str(tmp_path),
        "inherit_from": vid,
        "l1_features": [
            _make_feature("feat-a"),
            _make_feature("feat-b"),
            _make_feature("feat-c"),
        ],
        "choice": "A",
    })
    assert result.get("result") is not None or "version_id" in result
    assert result.get("feature_count") == 3


@pytest.mark.asyncio
async def test_inherit_new_feature_choice_b_drops_new(store_with_baseline):
    """choice=B → only baseline features kept (feat-c dropped)."""
    tmp_path, vid = store_with_baseline
    result = await _execute({
        "codebase_path": str(tmp_path),
        "inherit_from": vid,
        "l1_features": [
            _make_feature("feat-a"),
            _make_feature("feat-b"),
            _make_feature("feat-c"),
        ],
        "choice": "B",
    })
    assert result.get("result") is not None or "version_id" in result
    assert result.get("feature_count") == 2


@pytest.mark.asyncio
async def test_inherit_new_feature_choice_c_aborts(store_with_baseline):
    """choice=C → aborted, result=None, no snapshot written."""
    tmp_path, vid = store_with_baseline
    store = SnapshotStore(tmp_path)
    count_before = len(store.list_snapshots())
    result = await _execute({
        "codebase_path": str(tmp_path),
        "inherit_from": vid,
        "l1_features": [
            _make_feature("feat-a"),
            _make_feature("feat-b"),
            _make_feature("feat-c"),
        ],
        "choice": "C",
    })
    assert result["result"] is None
    count_after = len(store.list_snapshots())
    assert count_after == count_before  # no new snapshot


@pytest.mark.asyncio
async def test_inherit_invalid_choice_re_triggers_checkpoint(store_with_baseline):
    """Illegal choice key → re-trigger CHECKPOINT (result=None)."""
    tmp_path, vid = store_with_baseline
    result = await _execute({
        "codebase_path": str(tmp_path),
        "inherit_from": vid,
        "l1_features": [
            _make_feature("feat-a"),
            _make_feature("feat-b"),
            _make_feature("feat-c"),
        ],
        "choice": "Z",
    })
    assert result["result"] is None
    assert result["checkpoint"] == "new-features-detected"
