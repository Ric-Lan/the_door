# project_summary 工具缺口補完 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 補完三個工具對 `project_summary` 的缺口：`snapshot_patch` 可寫入、`snapshot_list` 可掃描、`snapshot_write` 回傳可驗證。

**Architecture:** 改動皆為 pass-through，無跨層邏輯：store 層 → MCP tool 層，各自獨立。Task 1 改 store，Task 2-4 改對應 MCP tool，每個 task 均 TDD。

**Tech Stack:** Python 3.11、pytest、dataclasses（`dataclasses.replace`）

---

## 改動檔案一覽

| 檔案 | 動作 |
|---|---|
| `the_door/src/the_door/core/diff/snapshot_store.py` | 修改 `patch_snapshot()` 加 `project_summary` 參數 |
| `the_door/src/the_door/mcp/tools/snapshot_patch_tool.py` | TOOL_SCHEMA 加欄位、execute 傳參、payload 加回傳 |
| `the_door/src/the_door/mcp/tools/snapshot_list_tool.py` | 每筆 entry 加 `has_project_summary: bool` |
| `the_door/src/the_door/mcp/tools/snapshot_write_tool.py` | payload 加 `project_summary` |
| `the_door/tests/unit/core/diff/test_snapshot_patch.py` | 加 3 個測試 |
| `the_door/tests/unit/mcp/test_snapshot_patch_tool.py` | 加 2 個測試 |
| `the_door/tests/unit/mcp/tools/test_snapshot_list_tool.py` | 加 2 個測試 |
| `the_door/tests/unit/mcp/test_snapshot_write_tool.py` | 加 1 個測試 |

---

## Task 1：store 層 — `patch_snapshot` 加 `project_summary` 參數

**Files:**
- Modify: `the_door/src/the_door/core/diff/snapshot_store.py`
- Test: `the_door/tests/unit/core/diff/test_snapshot_patch.py`

- [ ] **Step 1：寫失敗測試**

在 `test_snapshot_patch.py` 檔尾（`TestPatchSnapshotSourceNodes` 之後）新增測試類別：

```python
class TestPatchSnapshotProjectSummary:
    def test_patch_sets_project_summary(self, seeded):
        snap, _ = seeded.patch_snapshot(
            version_ref="v1.0.0",
            project_summary="這個系統提供 CLI 分析。",
        )
        assert snap.project_summary == "這個系統提供 CLI 分析。"

    def test_patch_project_summary_omitted_preserves_existing(self, tmp_path):
        store = SnapshotStore(tmp_path)
        store.create_snapshot(
            l1_snapshot={}, feature_relations=[], analyzed_files=[],
            trigger="manual", label="v1.0.0",
            project_summary="original summary",
        )
        snap, _ = store.patch_snapshot(version_ref="v1.0.0")
        assert snap.project_summary == "original summary"

    def test_patch_project_summary_persisted_to_disk(self, seeded):
        seeded.patch_snapshot(
            version_ref="v1.0.0",
            project_summary="持久化測試。",
        )
        reloaded = seeded.resolve_baseline("v1.0.0")
        assert reloaded.project_summary == "持久化測試。"
```

- [ ] **Step 2：確認測試失敗**

```
cd the_door
PYTHONUTF8=1 python -m pytest tests/unit/core/diff/test_snapshot_patch.py::TestPatchSnapshotProjectSummary -v
```

預期：`TypeError: patch_snapshot() got an unexpected keyword argument 'project_summary'`

- [ ] **Step 3：修改 `patch_snapshot()` 簽名**

在 `snapshot_store.py` 找到 `def patch_snapshot(` 的簽名（約第 201 行），加入參數：

```python
def patch_snapshot(
    self,
    version_ref: str,
    source_nodes_by_feature: dict[str, list[str]] | None = None,
    analyzed_files: list[str] | None = None,
    feature_metadata_by_feature: dict[str, dict] | None = None,
    project_summary: str | None = None,
) -> tuple["VersionSnapshot", list[str]]:
```

- [ ] **Step 4：在 `snap_kwargs` 中加入 `project_summary`**

在 `patch_snapshot()` 的 `snap_kwargs: dict = {"l1_snapshot": new_l1}` 行（約第 249 行）之後，在 `analyzed_files` 判斷的後面加：

```python
        snap_kwargs: dict = {"l1_snapshot": new_l1}
        if analyzed_files is not None:
            snap_kwargs["analyzed_files"] = analyzed_files
        if project_summary is not None:
            snap_kwargs["project_summary"] = project_summary
        snap = dataclasses.replace(snap, **snap_kwargs)
```

- [ ] **Step 5：確認測試通過**

```
cd the_door
PYTHONUTF8=1 python -m pytest tests/unit/core/diff/test_snapshot_patch.py -v
```

預期：全數 PASS（含原有測試）

- [ ] **Step 6：Commit**

```
git add the_door/src/the_door/core/diff/snapshot_store.py the_door/tests/unit/core/diff/test_snapshot_patch.py
git commit -m "feat(store): patch_snapshot 加 project_summary 參數"
```

---

## Task 2：MCP tool 層 — `snapshot_patch_tool` 加 `project_summary`

**Files:**
- Modify: `the_door/src/the_door/mcp/tools/snapshot_patch_tool.py`
- Test: `the_door/tests/unit/mcp/test_snapshot_patch_tool.py`

- [ ] **Step 1：寫失敗測試**

在 `test_snapshot_patch_tool.py` 的 `TestSnapshotPatchToolHappyPath` 類別內新增：

```python
    def test_patch_project_summary_returned_in_response(self, seeded_project):
        import asyncio
        result = asyncio.run(snapshot_patch_tool.execute({
            "codebase_path": str(seeded_project),
            "version_ref": "v1.0.0",
            "project_summary": "這個工具提供 CLI 分析。",
        }))
        assert result["project_summary"] == "這個工具提供 CLI 分析。"

    def test_patch_project_summary_none_when_not_provided(self, seeded_project):
        import asyncio
        result = asyncio.run(snapshot_patch_tool.execute({
            "codebase_path": str(seeded_project),
            "version_ref": "v1.0.0",
            "source_nodes_by_feature": {"feat-cli": ["main"]},
        }))
        assert result["project_summary"] is None
```

- [ ] **Step 2：確認測試失敗**

```
cd the_door
PYTHONUTF8=1 python -m pytest tests/unit/mcp/test_snapshot_patch_tool.py::TestSnapshotPatchToolHappyPath::test_patch_project_summary_returned_in_response tests/unit/mcp/test_snapshot_patch_tool.py::TestSnapshotPatchToolHappyPath::test_patch_project_summary_none_when_not_provided -v
```

預期：`KeyError: 'project_summary'`

- [ ] **Step 3：在 TOOL_SCHEMA 加欄位**

在 `snapshot_patch_tool.py` 的 `TOOL_SCHEMA["properties"]` 中，`analyzed_files` 之後加：

```python
        "project_summary": {
            "type": "string",
            "description": (
                "Optional. 若提供，覆寫此 snapshot 的非技術專案簡介（project_summary）；"
                "未提供則不動原有值。"
            ),
        },
```

- [ ] **Step 4：在 `execute()` 傳入 `project_summary`**

找到 `store.patch_snapshot(` 呼叫（約第 67 行），改為：

```python
        snap, skipped = store.patch_snapshot(
            version_ref=arguments["version_ref"],
            source_nodes_by_feature=arguments.get("source_nodes_by_feature") or {},
            analyzed_files=arguments.get("analyzed_files"),
            feature_metadata_by_feature=arguments.get("feature_metadata_by_feature"),
            project_summary=arguments.get("project_summary"),
        )
```

- [ ] **Step 5：在 payload 加入 `project_summary`**

找到 `payload = {` 區塊（約第 87 行），改為：

```python
    payload = {
        "version_id": snap.version_id,
        "label": snap.label,
        "patched_features": patched,
        "skipped_features": skipped,
        "project_summary": snap.project_summary,
    }
```

- [ ] **Step 6：確認測試通過**

```
cd the_door
PYTHONUTF8=1 python -m pytest tests/unit/mcp/test_snapshot_patch_tool.py -v
```

預期：全數 PASS

- [ ] **Step 7：Commit**

```
git add the_door/src/the_door/mcp/tools/snapshot_patch_tool.py the_door/tests/unit/mcp/test_snapshot_patch_tool.py
git commit -m "feat(mcp): snapshot_patch 加 project_summary 參數與回傳"
```

---

## Task 3：`snapshot_list_tool` 加 `has_project_summary`

**Files:**
- Modify: `the_door/src/the_door/mcp/tools/snapshot_list_tool.py`
- Test: `the_door/tests/unit/mcp/tools/test_snapshot_list_tool.py`

- [ ] **Step 1：寫失敗測試**

在 `test_snapshot_list_tool.py` 檔尾加：

```python
def test_snapshot_list_has_project_summary_false_when_absent(listed_project):
    result = asyncio.run(snapshot_list_tool.execute(
        {"codebase_path": str(listed_project)}
    ))
    for s in result["snapshots"]:
        assert s["has_project_summary"] is False


def test_snapshot_list_has_project_summary_true_when_present(tmp_path):
    store = SnapshotStore(tmp_path)
    store.create_snapshot(
        l1_snapshot={}, feature_relations=[], analyzed_files=[],
        trigger="manual", label="v-with-summary",
        project_summary="這個系統提供 CLI 分析。",
    )
    result = asyncio.run(snapshot_list_tool.execute(
        {"codebase_path": str(tmp_path)}
    ))
    assert result["snapshots"][0]["has_project_summary"] is True
```

（注意：`SnapshotStore` 已在該檔案 import，直接使用即可）

- [ ] **Step 2：確認測試失敗**

```
cd the_door
PYTHONUTF8=1 python -m pytest tests/unit/mcp/tools/test_snapshot_list_tool.py::test_snapshot_list_has_project_summary_false_when_absent tests/unit/mcp/tools/test_snapshot_list_tool.py::test_snapshot_list_has_project_summary_true_when_present -v
```

預期：`KeyError: 'has_project_summary'`

- [ ] **Step 3：修改 `snapshot_list_tool.py`**

找到 `execute()` 內的 snapshot dict，在 `"provenance"` 之後加一行：

```python
    return wrap({
        "snapshots": [
            {
                "version_id": s.version_id,
                "timestamp": s.timestamp,
                "trigger": s.trigger,
                "commit_hash": s.commit_hash,
                "git_tags": s.git_tags,
                "label": s.label,
                "provenance": provenance_element_for(s.contract_version).to_json(),
                "has_project_summary": s.project_summary is not None,
            }
            for s in snapshots
        ]
    }, project_path=project_root, context="mcp")
```

- [ ] **Step 4：確認測試通過**

```
cd the_door
PYTHONUTF8=1 python -m pytest tests/unit/mcp/tools/test_snapshot_list_tool.py -v
```

預期：全數 PASS

- [ ] **Step 5：Commit**

```
git add the_door/src/the_door/mcp/tools/snapshot_list_tool.py the_door/tests/unit/mcp/tools/test_snapshot_list_tool.py
git commit -m "feat(mcp): snapshot_list 每筆加 has_project_summary"
```

---

## Task 4：`snapshot_write_tool` 回傳加 `project_summary`

**Files:**
- Modify: `the_door/src/the_door/mcp/tools/snapshot_write_tool.py`
- Test: `the_door/tests/unit/mcp/test_snapshot_write_tool.py`

- [ ] **Step 1：寫失敗測試**

在 `test_snapshot_write_tool.py` 的 `TestSnapshotWriteTool` 類別內新增（與現有測試風格一致，使用 `@pytest.mark.asyncio`）：

```python
    @pytest.mark.asyncio
    async def test_returns_project_summary_in_payload(self, tmp_project):
        from the_door.mcp.tools.snapshot_write_tool import execute

        result = await execute({
            "codebase_path": str(tmp_project),
            "l1_features": VALID_FEATURES,
            "relations": VALID_RELATIONS,
            "label": "v1.0.0-summary-test",
            "project_summary": "這個工具提供 CLI 分析功能。",
        })
        assert result["project_summary"] == "這個工具提供 CLI 分析功能。"

    @pytest.mark.asyncio
    async def test_returns_project_summary_none_when_not_provided(self, tmp_project):
        from the_door.mcp.tools.snapshot_write_tool import execute

        result = await execute({
            "codebase_path": str(tmp_project),
            "l1_features": VALID_FEATURES,
            "relations": VALID_RELATIONS,
            "label": "v1.0.0-no-summary-test",
        })
        assert result["project_summary"] is None
```

（`VALID_FEATURES` 和 `VALID_RELATIONS` 已在檔案頂部定義，直接使用）

- [ ] **Step 2：確認測試失敗**

```
cd the_door
PYTHONUTF8=1 python -m pytest tests/unit/mcp/test_snapshot_write_tool.py::test_snapshot_write_returns_project_summary tests/unit/mcp/test_snapshot_write_tool.py::test_snapshot_write_returns_project_summary_none_when_not_provided -v
```

預期：`KeyError: 'project_summary'`

- [ ] **Step 3：修改 `snapshot_write_tool.py` payload**

找到 `payload = {` 區塊（約第 338 行）：

```python
    payload = {
        "version_id": snapshot.version_id,
        "label": snapshot.label,
        "timestamp": snapshot.timestamp,
        "relation_count": len(relations),
        "project_summary": snapshot.project_summary,
    }
```

- [ ] **Step 4：確認測試通過**

```
cd the_door
PYTHONUTF8=1 python -m pytest tests/unit/mcp/test_snapshot_write_tool.py -v
```

預期：全數 PASS（含原有測試）

- [ ] **Step 5：Commit**

```
git add the_door/src/the_door/mcp/tools/snapshot_write_tool.py the_door/tests/unit/mcp/test_snapshot_write_tool.py
git commit -m "feat(mcp): snapshot_write 回傳加 project_summary"
```

---

## Task 5：全套測試 + 最終 commit

- [ ] **Step 1：跑全套 tests**

```
cd the_door
PYTHONUTF8=1 python -m pytest -v
```

預期：全數 PASS，0 failed

- [ ] **Step 2：確認 git log 正確**

```
git log --oneline -5
```

預期看到 Task 1-4 各自的 commit

- [ ] **Step 3：（不推送）**

等待使用者明示才 push。
