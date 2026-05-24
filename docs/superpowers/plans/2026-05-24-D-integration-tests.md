# Plan D — Backend Integration Tests（Task 04 + Task 05）

> **執行分類 D**：Python 整合測試，無 production 程式碼改動
> **依賴：** Task 03（Plan A）必須已 commit——Task 04/05 依賴 `FeatureSummary.confidence_reason`
> **可並行：** Task 04 與 Task 05 可同時執行
> **Worktree：** `loving-sinoussi-20dcd0`

---

## Task 04 — R4：FlowGuard CHECKPOINT 端對端驗證

**Files:**
- Create: `the_door/tests/integration/test_snapshot_write_checkpoint_e2e.py`

不修改任何 production 程式碼。

- [ ] **Step 1：建立測試檔**

```python
"""E2E tests: snapshot_write CHECKPOINT flow — all three choice branches."""
from __future__ import annotations

import pytest
from the_door.core.diff.snapshot_store import SnapshotStore
from the_door.models import FeatureSummary
from tests._seed_helpers import seed_baseline_snapshot
from the_door.mcp.tools.snapshot_write_tool import execute


def _make_fs(fid: str) -> FeatureSummary:
    return FeatureSummary(
        feature_id=fid,
        label=fid,
        description=f"desc {fid}",
        source_node_count=1,
        confidence="high",
        source_nodes=(f"Node.{fid}",),
    )


@pytest.fixture
def project_with_baseline(tmp_path):
    seed_baseline_snapshot(
        tmp_path,
        label="v1.0.0",
        features={"feat-old": _make_fs("feat-old")},
    )
    return tmp_path


NEW_FEATURE = {
    "feature_id": "feat-new",
    "label": "New",
    "description": "newly added feature",
    "confidence": "high",
    "source_nodes": ["NewModule.run"],
}
OLD_FEATURE = {
    "feature_id": "feat-old",
    "label": "Old",
    "description": "desc feat-old",
    "confidence": "high",
    "source_nodes": ["Node.feat-old"],
}


@pytest.mark.asyncio
async def test_checkpoint_triggers_when_new_feature_detected(project_with_baseline):
    """First call without choice must return checkpoint (result=None)."""
    result = await execute({
        "codebase_path": str(project_with_baseline),
        "inherit_from": "v1.0.0",
        "l1_features": [OLD_FEATURE, NEW_FEATURE],
    })
    assert result.get("result") is None, f"Expected checkpoint, got: {result}"
    assert "checkpoint" in result
    option_keys = {o["key"] for o in result.get("options", [])}
    assert {"A", "B", "C"} == option_keys


@pytest.mark.asyncio
async def test_choice_a_includes_new_feature(project_with_baseline):
    """choice=A must write snapshot containing both old and new features."""
    result = await execute({
        "codebase_path": str(project_with_baseline),
        "inherit_from": "v1.0.0",
        "l1_features": [OLD_FEATURE, NEW_FEATURE],
        "choice": "A",
        "label": "v1.0.1-a",
    })
    assert "error" not in result
    snap = SnapshotStore(project_with_baseline).get_snapshot(result["version_id"])
    assert "feat-new" in snap.l1_snapshot
    assert "feat-old" in snap.l1_snapshot


@pytest.mark.asyncio
async def test_choice_b_drops_new_feature(project_with_baseline):
    """choice=B must write snapshot with only baseline features."""
    result = await execute({
        "codebase_path": str(project_with_baseline),
        "inherit_from": "v1.0.0",
        "l1_features": [OLD_FEATURE, NEW_FEATURE],
        "choice": "B",
        "label": "v1.0.1-b",
    })
    assert "error" not in result
    snap = SnapshotStore(project_with_baseline).get_snapshot(result["version_id"])
    assert "feat-new" not in snap.l1_snapshot
    assert "feat-old" in snap.l1_snapshot


@pytest.mark.asyncio
async def test_choice_c_aborts_no_snapshot_written(project_with_baseline):
    """choice=C must abort and not write any new snapshot."""
    store = SnapshotStore(project_with_baseline)
    count_before = len(store.list_snapshots())
    result = await execute({
        "codebase_path": str(project_with_baseline),
        "inherit_from": "v1.0.0",
        "l1_features": [OLD_FEATURE, NEW_FEATURE],
        "choice": "C",
    })
    assert result.get("aborted") is True
    assert len(store.list_snapshots()) == count_before
```

- [ ] **Step 2：執行測試確認全部通過**

```
cd the_door && pytest tests/integration/test_snapshot_write_checkpoint_e2e.py -v
```

預期：4 tests PASSED

- [ ] **Step 3：Commit**

```
git add the_door/tests/integration/test_snapshot_write_checkpoint_e2e.py
git commit -m "test(mcp): FlowGuard CHECKPOINT e2e — A/B/C all branches verified"
```

---

## Task 05 — R3：增量分析 source_nodes 保留驗證

**Files:**
- Create: `the_door/tests/integration/test_incremental_source_nodes.py`

不修改任何 production 程式碼。

- [ ] **Step 1：建立測試檔**

```python
"""Integration: analyze_changes returns source_nodes; snapshot_write preserves them."""
from __future__ import annotations

import pytest
from the_door.core.diff.snapshot_store import SnapshotStore
from the_door.models import FeatureSummary
from tests._seed_helpers import seed_baseline_snapshot
from the_door.mcp.tools.snapshot_write_tool import execute as snapshot_write
from the_door.mcp.tools.analyze_changes_tool import _feature_to_json


def _make_fs_with_nodes(fid: str, nodes: tuple[str, ...]) -> FeatureSummary:
    return FeatureSummary(
        feature_id=fid,
        label=fid,
        description=f"desc {fid}",
        source_node_count=len(nodes),
        confidence="high",
        source_nodes=nodes,
    )


def test_feature_to_json_includes_source_nodes():
    """_feature_to_json must serialize source_nodes as a list."""
    fs = _make_fs_with_nodes("feat-a", ("Foo.bar", "Baz.qux"))
    result = _feature_to_json(fs)
    assert result["source_nodes"] == ["Foo.bar", "Baz.qux"]
    assert result["source_node_count"] == 2


@pytest.mark.asyncio
async def test_updated_features_preserves_source_nodes(tmp_path):
    """snapshot_write with updated_features must not drop source_nodes from baseline."""
    seed_baseline_snapshot(
        tmp_path,
        label="v1.0.0",
        features={
            "feat-stable": _make_fs_with_nodes("feat-stable", ("StableModule.run",)),
            "feat-changed": _make_fs_with_nodes("feat-changed", ("OldModule.fn",)),
        },
    )

    result = await snapshot_write({
        "codebase_path": str(tmp_path),
        "inherit_from": "v1.0.0",
        "updated_features": [
            {
                "feature_id": "feat-changed",
                "label": "feat-changed updated",
                "description": "updated description",
                "confidence": "high",
                "source_nodes": ["NewModule.fn"],
            }
        ],
        "label": "v1.0.1",
    })
    assert "error" not in result

    snap = SnapshotStore(tmp_path).get_snapshot(result["version_id"])
    assert snap.l1_snapshot["feat-stable"].source_nodes == ("StableModule.run",)
    assert snap.l1_snapshot["feat-changed"].source_nodes == ("NewModule.fn",)
```

- [ ] **Step 2：執行測試確認通過**

```
cd the_door && pytest tests/integration/test_incremental_source_nodes.py -v
```

預期：2 tests PASSED

- [ ] **Step 3：Commit**

```
git add the_door/tests/integration/test_incremental_source_nodes.py
git commit -m "test(mcp): verify source_nodes preserved in incremental update path"
```
