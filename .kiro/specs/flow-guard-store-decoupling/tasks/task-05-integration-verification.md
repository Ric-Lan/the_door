# Task 05 — Integration & Verification: 端對端驗證

**依賴：** Task 01、02、03、04 全部完成  
**測試覆蓋率目標：** 整合路徑 100%

---

## 產出檔案分類

### 新增
| 檔案 | 說明 |
|---|---|
| `the_door/tests/integration/test_cli_checkpoint.py` | CLI + FlowGuard 整合測試 |
| `the_door/tests/integration/test_store_decoupling.py` | Store 解耦端對端測試 |
| `the_door/tests/contract/test_flow_guard_contract.py` | MCP 回應格式合約測試（task-03 不建立此檔，由本 task 負責） |

### 不修改現有程式碼
本 task 純測試；若測試發現實作問題，回修 task-01~04 對應檔案。

---

## 5.1 CLI + FlowGuard 整合測試

### `tests/integration/test_cli_checkpoint.py`

```python
# 測試清單

# analyze_cmd + 無 API key + 輸入 "A"
#   → stdout 含 "[CHECKPOINT: no-api-key]"
#   → 輸入 "A" 後印出 MCP 指引，exit 0（不拋 ConfigError）

# analyze_cmd + 無 API key + 輸入 "B"
#   → 印出設定說明，exit 0

# analyze_cmd + 無 API key + 輸入非法 "Z" 再輸入 "A"
#   → 第一次印出 "⚠ 無效選項"，第二次正常結束

# diff_cmd + baseline 不存在 + 輸入 "B"（中止）
#   → stdout 含 "[CHECKPOINT: snapshot-missing-for-diff]"
#   → exit 0，不拋 KeyError

# status_cmd + project.id 不存在 + 輸入 "B"
#   → stdout 含 "[CHECKPOINT: project-not-initialized]"
#   → 繼續顯示現有狀態

# extract --as-version + 回填完成
#   → stdout 含 "[CHECKPOINT: backfill-complete]"
#   → options 含 "A"（analyze_changes）和 "B"（viewer）
```

---

## 5.2 Store 解耦端對端測試

### `tests/integration/test_store_decoupling.py`

```python
# 測試清單（使用 tmp_path）

# 新專案初始化流程：
#   1. 建立空 tmp codebase 目錄
#   2. ProjectIdentity.get_or_create(tmp_path) → 建立 project.id
#   3. SnapshotStore(tmp_path) → _snapshots_dir 指向 ~/.the-door/store/<UUID>/snapshots
#   4. _snapshots_dir.parent.mkdir 後建立 snapshot
#   5. SnapshotStore(tmp_path).list_snapshots() 能讀到剛寫入的 snapshot

# source 目錄搬移後仍可找到 store：
#   1. 建立 project.id，記錄 UUID
#   2. 將 project.id 複製到 new_path/.the-door/project.id
#   3. SnapshotStore(new_path) → UUID 相同 → store 路徑相同 → list_snapshots() 正常

# 舊版 store（legacy）：
#   1. 建立 codebase/.the-door/snapshots/（無 project.id）
#   2. ProjectIdentity.resolve_store_root() → status="legacy"
#   3. SnapshotStore(codebase) → _snapshots_dir = codebase/.the-door/snapshots
#   4. list_snapshots() 能讀到舊 snapshot（向下相容）

# store 路徑破損（path_error）：
#   1. 建立 project.id，UUID 指向不存在的 store 目錄
#   2. ProjectIdentity.resolve_store_root() → status="path_error"
#   3. SnapshotStore(codebase) → _snapshots_dir 仍可建構（不拋錯）
#   4. 呼叫端（CLI/MCP）負責 CHECKPOINT 處理

# 23 個現有呼叫端相容性（抽樣驗證）：
#   - SnapshotStore(Path(codebase_path)) 在 legacy 環境下行為不變
#   - list_snapshots() 回傳舊版 snapshot，不含 codebase_path 欄位（None）
```

---

## 5.3 完整流程驗證（Scenario）

以下為手動驗證清單（非自動化，但在 task 完成前需過關）：

```
Scenario A — 新專案 agent-as-LLM 流程（無 API key）：
  1. the-door analyze <path>
     → [CHECKPOINT: no-api-key] 出現
     → 選 "A"（agent 路徑）
     → 印出 extract_structure 指引
  
  2. extract_structure(codebase_path="<path>")（MCP）
     → 回傳 nodes/edges/topology

  3. snapshot_write(codebase_path="<path>", l1_features=[...], label="v1.0.0")（MCP）
     → 回傳 version_id（無 CHECKPOINT，因為無 inherit_from）
     → response["result"]["version_id"] 非 null

Scenario B — 多版本 inherit_from 新 feature：
  1. snapshot_write(inherit_from="v1.0.0", l1_features=[...+新 feature], choice=None)
     → [CHECKPOINT: new-features-detected]
  2. 同上 choice="A"
     → result["version_id"] 非 null
     → 新 feature 出現在 snapshot

Scenario C — source 路徑不存在：
  1. analyze_changes(codebase_path="<path>", baseline="v1.0.0", choice=None)
     （假設 snapshot.codebase_path 已過期）
     → [CHECKPOINT: source-path-broken]
  2. 同上 source_path="<新路徑>", choice="A"
     → 正常執行 analyze_changes
```

---

## 覆蓋率驗收標準

執行以下指令，確認全部通過：

```bash
# 從 the_door/ 目錄執行（pyproject.toml 所在位置）
cd the_door

pytest tests/unit/core/test_flow_guard.py \
  --cov=src/the_door/core/flow_guard --cov-fail-under=100

pytest tests/unit/core/test_project_identity.py \
  --cov=src/the_door/core/project_identity --cov-fail-under=100

pytest tests/unit/cli/test_checkpoint_renderer.py \
  --cov=src/the_door/cli/checkpoint_renderer --cov-fail-under=100

pytest tests/ --cov=src/the_door --cov-fail-under=100 -x
```

注意：`--cov` 接受相對於 cwd 的 **目錄或模組路徑**，不是 `the_door/src/...` 形式。
若 pyproject.toml 的 `testpaths` 已設定，可直接執行 `pytest --cov=src/the_door -x`。

最後一條全量測試不得低於現有通過率（參考：774 passed + 45 skipped）。

---

## 完成條件

- [ ] 所有新增檔案的 coverage = 100%
- [ ] Scenario A / B / C 手動驗證通過
- [ ] 全量測試通過數 ≥ 774（不退步）
- [ ] `pytest tests/ -x` 無 FAILED
