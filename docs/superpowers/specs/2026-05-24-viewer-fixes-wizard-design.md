# Spec: Viewer Fixes + Data Quality + Wizard (2026-05-24)

## Overview

10 改進項目，依架構分層組織，確保每個檔案只在一個 task group 修改。
原則：TDD（測試先行，coverage 100%），Clean Code（單一職責、無重複邏輯、無防禦性空殼）。

---

## Requirements

### R1 — status_cmd.py Unicode 輸出（cp950）
Windows 終端機預設 cp950 編碼，導致含中文的 `sys.stdout.write()` 崩潰。
- 修法：在 `status_cmd()` 進入點設定 `os.environ.setdefault("PYTHONIOENCODING", "utf-8")`，並將所有 `sys.stdout.write()` 呼叫統一改為 `click.echo()`，由 click 處理 encoding 而非直接操作 stdout。
- **不直接替換 `sys.stdout`**（會干擾 click 的 ANSI/color 管理，導致 double-encode）。
- 測試：mock `os.environ` 不含 `PYTHONIOENCODING`，呼叫 `status_cmd()`，確認 `os.environ["PYTHONIOENCODING"]` 被設為 `"utf-8"` 且輸出不拋出 `UnicodeEncodeError`。

### R2 — file_discovery.py 排除 `.claude/` worktrees
- `_DEFAULT_IGNORE_PATTERNS` 加入 `".claude/"`。
- 測試：建立含 `.claude/worktrees/foo/bar.py` 的 fixture，確認 `discover()` 不回傳該檔案。

### R3 — 增量分析流程：source_nodes 填入
- `analyze_changes_tool.py` 回傳的 affected feature 資訊須包含 baseline 的 `source_nodes`，讓 agent 知道要更新哪些 AST node。
- `snapshot_write_tool.py` 的 `updated_features` 處理路徑現有邏輯已正確合併 source_nodes（不靜默丟棄），以測試驗收即可，**不修改** production 程式碼。
- 測試（放在 `tests/test_incremental_source_nodes.py`，屬 B2 task）：寫入含 `source_nodes` 的 baseline snapshot，呼叫 `analyze_changes_tool.execute()`，確認回傳資料含 `source_nodes`；再呼叫 `snapshot_write_tool.execute()` 帶 `updated_features`，確認 result snapshot 保留 source_nodes。

### R4 — FlowGuard CHECKPOINT 端對端驗證
- 新增整合測試：呼叫 `snapshot_write_tool.execute()` 傳入 `inherit_from` + 包含新 `feature_id` 的 `l1_features`（不帶 `choice`），驗證回傳 `_decision`（CHECKPOINT 觸發）。
- 第二次呼叫帶 `choice="A"`，驗證 snapshot 正確寫入且包含新 feature。
- 第二次呼叫帶 `choice="B"`，驗證新 feature 被捨棄、只保留 baseline features。
- 第二次呼叫帶 `choice="C"`，驗證回傳 `aborted: true`，不寫入 snapshot。
- 不修改任何 production 程式碼。

### R5 — snapshot_write：欄位補強
- `models.py`：`FeatureSummary` 加入 `confidence_reason: str | None = None`（frozen dataclass，預設 None，向後相容）。
- `snapshot_write_tool.py`：
  - schema 的 `l1_features.items.properties` 加入 `"confidence_reason": {"type": "string"}`（optional）。
  - `_feature_dict_to_summary()` 讀取並傳入 `confidence_reason`。
  - 若某 feature 的 `source_nodes` 為空陣列，在 response 加入 `warnings` list，提示 agent 補充 source_nodes（不阻擋寫入）。
- 測試：傳入含 `confidence_reason` 的 feature，確認寫入後可從 snapshot store 讀回；傳入空 `source_nodes`，確認 response 含 `warnings`。

### R6 — 篩選器 UI 接線
- `app.js`：讀取 `#filter-conf` 和 `#filter-type` 兩個 `<select>` 元素，監聽 `change` 事件。
- filter 狀態存入 `state.filterConf` / `state.filterType`（`state.js` 加欄位，預設 `null`）。
- 每次 filter 變更後呼叫 `applyCardFilters(features, { conf, type })` 並重新 render 卡片列表。
- 測試：mock `state.l1Model.features`，觸發 `change` 事件，驗證 render 函式以正確 filtered list 被呼叫。

### R7 — 置頂欄版本標示
- `ui-topbar.js`：`renderTopBar()` 單版本模式的 `summaryText` 改為 `"{label} · 共 {N} 個功能"`，使用已有的 `snapshotLabel()` 取得 label。
- 無版本 label 時 fallback 維持原行為（顯示 `共 N 個功能`）。
- 測試：mock `state` 含版本 snapshot，驗證 `summaryText` 包含 label。

### R8 — 心智圖版本標示
- `mindmap-popup.html` JS 段：`init()` 從 `data` 讀取 `data.versionALabel` / `data.versionBLabel`，若存在則在 `#project-name` 後顯示版本資訊（diff 模式：`A · {labelA} → B · {labelB}`；單版本：`{label}`）。
- `app.js`（開啟 mindmap popup 的位置）：將 `versionALabel` / `versionBLabel` 寫入 `sessionStorage` 的 `mindmap-data`。
- 測試（app.js）：驗證 sessionStorage payload 包含 versionALabel / versionBLabel。
- 測試（mindmap-popup）：mock `sessionStorage` 帶 labels，驗證 DOM 渲染正確文字。

### R9 — 關聯圖上下間距加長
- `styles.css`：`.gv-grid` 的 `gap: 20px` 拆為 `column-gap: 20px; row-gap: 48px`，使上下間距至少兩倍。
- 不動 `graph.js` 邏輯。
- 視覺驗收（eyeball）：執行 `the-door ui C:\Users\Ric\Desktop\test-targets\the-door-v105 --no-browser --port 8765`，開啟關聯圖（L1 graph 頁），確認「有邊相連的兩個節點之間，連線不被相鄰節點遮蓋」為 pass 標準。

### R10 — Wizard 新功能
- 新建 `cli/wizard_cmd.py`，新增 `the-door wizard <path>` 指令。
- `cli/main.py` 登記此指令。
- 流程（依序）：
  1. 呼叫 `FileDiscovery.discover(path)`，顯示頂層目錄清單與各目錄檔案數。
  2. 互動詢問排除目錄（可輸入逗號分隔清單，Enter 跳過）；若有排除，以 custom ignore patterns 重跑 discovery。
  3. **Checkpoint 1（總覽確認）**：顯示計畫摘要（檔案數、快照標籤、分析模式），呼叫 `FlowGuard.check("wizard-start-confirmed", ...)`，選項 A 繼續 / B 中止。
  4. 執行分析：以 `ConfigManager(codebase_path).load()` 判斷 API key 是否存在。有 key → 呼叫 `run_analyze_pipeline`；無 key → 印出 MCP 指令提示（`extract_structure` → agent-as-LLM → `snapshot_write`），wizard 本身不執行 MCP。
  5. 若目標路徑已有相同 label 的 snapshot，**Checkpoint 2（覆寫確認）**：選項 A 覆寫 / B 另存新標籤 / C 中止。
  6. 完成後列印 `Next:` block（使用 `render_next_block`）。
- `FileDiscovery.discover()` 須支援額外的 `extra_ignore` 參數（`list[str]`，預設空 list），傳給 `_load_gitignore` 合併至 patterns。此參數修改在 B1 的 `file_discovery.py` 同步完成（R2 task 加入此改動）。
- 測試：
  - `wizard_cmd.py` 單元測試：mock `FileDiscovery`、mock `click.prompt`，驗證各分支（排除目錄、Checkpoint A/B/C）的控制流。
  - `file_discovery.py`：`extra_ignore` 參數測試（傳入 `["vendor/"]`，驗證 vendor/ 被排除）。

---

## Architecture Constraints

- `FileDiscovery.extra_ignore` 的修改屬於 R2 task group（B），wizard 只呼叫不修改。
- R4（FlowGuard e2e）**不修改** `snapshot_write_tool.py`，只新增測試檔。
- R5 修改 `snapshot_write_tool.py`；R4 測試檔在 R5 合併後可直接覆蓋完整 CHECKPOINT 流程。
- 前端 JS 的 filter state（R6）只加欄位到 `state.js`，不改其他 state 邏輯。
- R6（filter 接線）與 R8（mindmap sessionStorage）同屬 task D，`app.js` 在同一 PR 內一次完成，不拆分。

---

## File → Task Mapping（零重疊）

| Task | 檔案 | Requirements |
|---|---|---|
| A1 | `cli/status_cmd.py` | R1 |
| A2 | `cli/wizard_cmd.py`（新） | R10 |
| A2 | `cli/main.py` | R10（登記指令） |
| B1 | `core/extraction/file_discovery.py` | R2 + R10 extra_ignore |
| B2 | `mcp/tools/analyze_changes_tool.py` | R3 |
| B2 | `tests/test_incremental_source_nodes.py`（新） | R3 驗證 |
| C1 | `models.py` | R5（FeatureSummary.confidence_reason） |
| C1 | `mcp/tools/snapshot_write_tool.py` | R5 schema/validation（confidence_reason + source_nodes warning） |
| C2 | `tests/test_snapshot_write_checkpoint_e2e.py`（新） | R4 |
| D | `js/state.js` | R6（filterConf / filterType 欄位） |
| D | `js/app.js` | R6 事件接線 + R8 sessionStorage versionLabel |
| D | `js/ui-topbar.js` | R7 |
| D | `mindmap-popup.html` | R8（JS 段） |
| E1 | `styles.css` | R9 |

---

## TDD Constraints

- 每個 requirement 的實作程式碼在測試通過前不合併。
- Coverage target：每個修改的 Python 模組 100%；JS 模組 ≥ 95%。
- R9（CSS 間距）豁免自動化測試，以 eyeball 驗收（`the-door ui <test-target>`）。
- R4 為純測試任務，本身即為驗證工件。

---

## Implementation Order

依賴關係決定順序：

```
R2 (file_discovery) → R10 (wizard, 依賴 extra_ignore)
R5 (models + snapshot_write) → R4 (e2e tests, 依賴最終 schema)
R3 (analyze_changes + snapshot_write incremental) — 獨立
R1, R6, R7, R8, R9 — 互相獨立，可並行
```

建議執行序：R1 → R2 → R5 → R4 → R3 → R6+R7+R8（並行）→ R9 → R10
