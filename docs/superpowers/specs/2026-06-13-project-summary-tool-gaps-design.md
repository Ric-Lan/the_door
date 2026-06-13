# project_summary 工具缺口補完 — Design Spec

**日期：** 2026-06-13  
**版本：** v1.7.4 之後  
**範圍：** 補完三個工具的 `project_summary` 資訊暴露與寫入缺口

---

## 1. 背景與動機

v1.7.4 完成了 snapshot 級 `project_summary` 全鏈（寫入 → 持久化 → viewer 顯示），但兩個工具仍有缺口：

| 工具 | 缺口 |
|---|---|
| `snapshot_patch` | 無 `project_summary` 參數，AI 無法對既有 snapshot 補/改簡介 |
| `snapshot_list` | 回傳不含 `project_summary` 資訊，AI 無法掃描哪些 snapshot 缺少簡介 |
| `snapshot_write` | 回傳 payload 未帶 `project_summary`，寫完無法直接驗證 |

上個 session 的 workaround 是直接改 JSON 檔，此 spec 將其正式化為工具路徑。

---

## 2. 決策摘要

- **`snapshot_list`**：加 `has_project_summary: bool` 而非完整字串。  
  理由：AI 的掃描決策只需要「有/無」；完整文字對補寫決策無用（簡介由 L1 features 重新合成，非改舊文字）。

- **`snapshot_patch`**：覆寫語義（傳入就覆寫、未傳入不動原值）。  
  理由：與 `feature_metadata_by_feature` 的 key-level 覆寫語義一致。

- **`snapshot_write` 回傳**：一致性補齊。兩個寫入工具行為對稱，都在寫完後可直接驗證。

---

## 3. 改動範圍

### 3.1 `snapshot_patch_tool.py`

**TOOL_SCHEMA** 新增可選欄位：
```json
"project_summary": {
  "type": "string",
  "description": "若提供，覆寫此 snapshot 的非技術專案簡介；未提供則不動原有值。"
}
```

**`execute()`**：
- 取 `arguments.get("project_summary")`（`None` = 未傳入，不動原值）
- 傳入 `store.patch_snapshot(..., project_summary=...)`
- 回傳 payload 加入 `"project_summary": snap.project_summary`

### 3.2 `snapshot_store.py` — `patch_snapshot()`

簽名加入：
```python
project_summary: str | None = None,
```

行為：
```python
if project_summary is not None:
    snap_kwargs["project_summary"] = project_summary
```
（`None` = 呼叫端未傳、不觸碰原值；`""` 空字串視為有效覆寫）

### 3.3 `snapshot_list_tool.py`

每個 snapshot entry 加入：
```json
"has_project_summary": true | false
```

實作：`s.project_summary is not None`

### 3.4 `snapshot_write_tool.py`

payload 加入：
```python
"project_summary": snapshot.project_summary,
```

---

## 4. 資料流（patch 路徑）

```
AI 呼叫 snapshot_patch(version_ref, project_summary="...")
  ↓
snapshot_patch_tool.execute()
  ↓
store.patch_snapshot(version_ref, project_summary="...")
  ↓ snap_kwargs["project_summary"] = "..."
dataclasses.replace(snap, project_summary="...")
  ↓
_write_snapshot(snap)  → JSON 持久化
  ↓
回傳 { version_id, label, patched_features, skipped_features, project_summary }
```

---

## 5. 不在範圍內

- `project_summary` 的 C3/C4 gate 驗證（patch 路徑不需要 edge_residue；與既有 `source_nodes` patch 行為一致）
- 清除 `project_summary`（設為 `null`）的機制（需求未出現，YAGNI）
- `snapshot_list` 回傳完整 `project_summary` 字串（已分析為不需要）
- 新增 `snapshot_read` 工具（已分析為不需要）

---

## 6. 測試策略

每個改動點都有對應的 unit test，**不新增 integration test**（改動皆為純 pass-through，無跨層邏輯）。

| 測試檔 | 新增測試案例 |
|---|---|
| `tests/unit/mcp/test_snapshot_patch_tool.py` | patch with project_summary 覆寫；未傳入不動原值 |
| `tests/unit/mcp/tools/test_snapshot_list_tool.py` | has_project_summary=True / False 各一 |
| `tests/unit/mcp/test_snapshot_write_tool.py` | 回傳含 project_summary |
| `tests/unit/core/diff/test_snapshot_patch.py` | patch_snapshot project_summary 參數 |

---

## 7. 改動檔案清單

```
the_door/src/the_door/mcp/tools/snapshot_patch_tool.py
the_door/src/the_door/core/diff/snapshot_store.py
the_door/src/the_door/mcp/tools/snapshot_list_tool.py
the_door/src/the_door/mcp/tools/snapshot_write_tool.py
the_door/tests/unit/mcp/test_snapshot_patch_tool.py
the_door/tests/unit/mcp/tools/test_snapshot_list_tool.py
the_door/tests/unit/mcp/test_snapshot_write_tool.py
```
