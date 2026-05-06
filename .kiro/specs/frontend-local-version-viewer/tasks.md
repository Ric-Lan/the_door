# Implementation Tasks

## TDD 執行原則

每個 Python 任務遵循：先寫失敗測試 → 確認失敗 → 實作最小邏輯 → 測試通過。
前端任務遵循：先建 HTML 骨架 → 接入 ViewModel → 驗證行為。

---

## Task 1: 修正 `diff_available` 邊界邏輯並補強 unit tests

**對應 Req 1 AC1/AC2、Design §1.1、§2.2**

- [x] 1.1 在 `tests/unit/core/ui/test_view_model.py` 新增失敗測試：
  - `test_diff_available_false_when_l1_changes_empty_list`：輸入 `{"l1_changes": []}` → `diff_available=False`, `changes=[]`
  - `test_diff_available_true_when_l1_changes_nonempty`：輸入含 1 筆 l1_changes → `diff_available=True`
  - 執行測試，確認 `test_diff_available_false_when_l1_changes_empty_list` 失敗（現有邏輯 bug）
- [x] 1.2 修正 `the_door/src/the_door/core/ui/view_model.py` 中 `build_update_report_view_model`，完整替換如下兩行：
  ```python
  # 舊（移除這兩行）
  has_l1_changes = "l1_changes" in report
  changes_raw = _list(report.get("l1_changes")) if has_l1_changes else []

  # 新（替換為這兩行）
  changes_raw = _list(report.get("l1_changes"))   # _list(None) 回傳 []，不需要 key 存在判斷
  diff_available = len(changes_raw) > 0
  ```
  - 同步將 `return` 中的 `"diff_available": has_l1_changes` 改為 `"diff_available": diff_available`
  - 確認函式中不再有 `has_l1_changes` 殘留
- [x] 1.3 執行測試，確認 Task 1.1 的兩個新測試通過，現有測試不退步

**Checkpoint**：`pytest tests/unit/core/ui/test_view_model.py` 全部通過

---

## Task 2: 補強 unit tests — fallback detail、tiebreak 排序、空字串邊界

**對應 Req 1 AC9、Req 2 AC1、Design §2.2**

- [x] 2.1 在 `tests/unit/core/ui/test_view_model.py` 新增：
  - `test_fallback_detail_when_no_l2_entry`：`l2_details=[]`，`l1_changes` 有 1 筆 → `details[id].source="UpdateReport.l1_changes"`, `before.label=MISSING_VALUE`
  - `test_sort_tiebreak_by_feature_id`：2 筆相同 risk_flags + change_type，id="feat-b" 和 "feat-a" → "feat-a" 排第一
  - `test_missing_value_when_current_label_empty_string`：`current_label=""` → `after.label=MISSING_VALUE`
- [x] 2.2 執行測試，確認全部通過（現有邏輯應已正確，這些是補充驗證）

**Checkpoint**：`pytest tests/unit/core/ui/test_view_model.py` 全部通過，測試數量增加 5 個（Task 1 + Task 2）

---

## Task 3: 建立 PBT — `test_view_model_properties.py`

**對應 Req 10、Design §2.3**

- [x] 3.1 建立 `tests/property/test_view_model_properties.py`，定義 ASCII-only Hypothesis strategies：
  - `FEATURE_ID_ST`：`st.from_regex(r"feat-[a-z]{3,10}", fullmatch=True)`
  - `CHANGE_TYPE_ST`、`RISK_FLAG_ST`、`ASCII_LABEL_ST`（`min_codepoint=32, max_codepoint=126`）
  - `L1_CHANGE_ST`、`UPDATE_REPORT_ST`
- [x] 3.2 實作 7 個 PBT 屬性（Task 1 完成後執行，此時 `diff_available` 修正已到位，所有屬性應直接通過）：
  - `prop_change_counts_sum`：`sum(change_counts.values()) == len(l1_changes)`
  - `prop_changes_ids_in_l1`：每個 `changes[i].id` 都在 `l1_changes` 的 `feature_id` 集合中
  - `prop_details_keys_in_changes`：每個 `details` key 都在 `changes` 的 `id` 集合中
  - `prop_diff_available_false_when_empty`：`l1_changes=[]` → `diff_available=False`
  - `prop_missing_value_when_baseline_null`：`baseline_label=null` → `before.label="未提供"`
  - `prop_missing_value_when_current_null`：`current_label=null` → `after.label="未提供"`
  - `prop_changes_length_equals_l1_changes`：`len(changes) == len(l1_changes)`
- [x] 3.3 執行 PBT，確認 7 個屬性全部通過

**Checkpoint**：`pytest tests/property/test_view_model_properties.py` 全部通過

---

## Task 4: 產生 viewer fixture 資料

**對應 Design §4.2**

- [x] 4.1 建立目錄 `docs/frontend-local-version-viewer/viewer/data/`
- [x] 4.2 執行 Python 腳本產生 fixture（在 `the_door/` 子目錄下執行，套件已 editable install）：
  ```python
  # 在 the_door/ 目錄下執行（與 pytest 相同的環境）
  from the_door.core.ui.view_model import export_update_report_view_model, export_l1_view_model
  import pathlib

  root = pathlib.Path(__file__).parent.parent  # workspace 根目錄

  export_update_report_view_model(
      root / "docs/frontend-local-version-viewer/prototype/data/mock-update-report.json",
      root / "docs/frontend-local-version-viewer/viewer/data/update-view-model.json",
  )
  # 使用 workspace 根目錄的 docs/self-analysis-l1-output.json（非 the_door/ 子目錄下的同名檔案）
  export_l1_view_model(
      root / "docs/self-analysis-l1-output.json",
      root / "docs/frontend-local-version-viewer/viewer/data/l1-view-model.json",
  )
  ```
  或直接用 PowerShell 在 `the_door/` 目錄下執行：
  ```powershell
  python -c "
  from the_door.core.ui.view_model import export_update_report_view_model, export_l1_view_model
  export_update_report_view_model('../docs/frontend-local-version-viewer/prototype/data/mock-update-report.json', '../docs/frontend-local-version-viewer/viewer/data/update-view-model.json')
  export_l1_view_model('../docs/self-analysis-l1-output.json', '../docs/frontend-local-version-viewer/viewer/data/l1-view-model.json')
  "
  ```
- [x] 4.3 確認兩個 JSON 檔案存在且可被 `json.loads()` 解析
- [x] 4.4 確認 `update-view-model.json` 的 `diff_available` 為 `true`（mock 資料有 l1_changes）
- [x] 4.5 確認 `l1-view-model.json` 的 `stats.feature_count` 為 13（對齊現有自我分析結果）

**Checkpoint**：兩個 fixture 檔案存在，內容可解析，關鍵欄位正確

---

## Task 5: 建立前端 viewer HTML/CSS 骨架

**對應 Req 4、Design §3.1、§3.2**

- [x] 5.1 建立 `docs/frontend-local-version-viewer/viewer/index.html`：
  - `<header class="topbar">`：含 `<h1>`、mode 切換按鈕（差異/舊版/新版）、狀態計數列
  - `<main class="workspace">`：三欄佈局（`sidebar` / `canvas` / `detail-panel`）
  - `<aside class="sidebar">`：含 `#list-title`、`#list-source`、`#feature-list`
  - `<section class="canvas">`：含 `#summary-band`、`#graph-nodes`、`#relations-list`
  - `<aside class="detail-panel">`：含 `#detail-source`、`#detail-content`
  - 引入 `./styles.css` 和 `./app.js`
  - 不引入任何 CDN 或外部資源
- [x] 5.2 建立 `docs/frontend-local-version-viewer/viewer/styles.css`：
  - 三欄 CSS Grid 佈局（sidebar 固定寬、canvas 彈性、detail-panel 固定寬）
  - mode 按鈕 active 狀態樣式
  - change-type badge 顏色（added=綠、removed=紅、attribute_changed=橙、dependency_changed=橙）
  - empty-state 樣式
  - error-box 樣式
  - 不引入外部字體或 icon

**Checkpoint**：用瀏覽器開啟（透過 `python -m http.server`）可看到三欄骨架，無 console error

---

## Task 6: 實作前端 `app.js` — 資料載入與模式切換

**對應 Req 4 AC4/AC5、Req 8、Req 9、Design §3.3**

- [x] 6.1 建立 `docs/frontend-local-version-viewer/viewer/app.js`，實作：
  - `state` 物件：`{ updateModel, l1Model, mode, selectedId }`
  - `loadViewModels()`：fetch `./data/update-view-model.json`（必要）和 `./data/l1-view-model.json`（可選）
    - fetch 失敗時呼叫 `renderError(path + ": " + status)`
    - JSON parse 失敗時呼叫 `renderError(path + ": parse error")`
    - 載入成功後：若 `diff_available=true` 設 `mode="diff"`，否則設 `mode="baseline"`（舊版為預設單版本模式）
  - `setMode(mode)`：guard diff mode 需 `diff_available`，更新 `state.mode`，呼叫 `render()`
  - mode 按鈕 click 事件綁定
- [x] 6.2 確認：`diff_available=false` 時差異模式按鈕為 disabled 狀態
- [x] 6.3 確認：fetch 失敗時顯示錯誤訊息，不顯示空白畫面

**Checkpoint**：載入 viewer，TopBar 顯示 L0 摘要，模式按鈕可點擊，diff 模式 guard 正確

---

## Task 7: 實作前端差異模式 ChangeList 與 GraphCanvas

**對應 Req 5、Design §3.3**

- [x] 7.1 實作 `renderChangeList()`：
  - 差異模式：遍歷 `state.updateModel.changes`，每筆顯示 change_type symbol + label
  - `changes` 為空時顯示「無變更項目」empty-state
  - 點擊項目呼叫 `selectItem(id)`，active 項目有 active class
- [x] 7.2 實作 `renderGraphCanvas()`：
  - 差異模式：每筆 change 顯示一個節點，含 change_type badge 和 label
  - 節點可點擊，呼叫 `selectItem(id)`
- [x] 7.3 實作 `renderTopBar()`：
  - 顯示 `summary`（來自 ViewModel）
  - 顯示 `change_counts`（added/removed/modified 計數）
  - 顯示非零 `risk_counts`
  - 不自行計算計數，直接讀取 ViewModel 欄位

**Checkpoint**：差異模式下，ChangeList 顯示正確數量的變更項目，符號正確，點擊可選取

---

## Task 8: 實作前端 DetailPanel（差異模式）

**對應 Req 6、Req 11、Design §3.4**

- [x] 8.1 實作 `renderDetailPanel()`（差異模式）：
  - 讀取 `state.updateModel.details[state.selectedId]`
  - 無選取時顯示「選取左側項目以查看詳情」
  - A 類欄位（直接顯示，Python 已填 `"未提供"`）：`before.label`、`before.description`、`after.label`、`after.description`
  - B 類欄位（JS 補值）：`scope_state ?? "未提供"`
  - 列表欄位：`related_vulnerabilities`、`affected_relations`（空陣列顯示「未提供」）
  - 永遠顯示 `detail.source`（防幻覺 attribution）
- [x] 8.2 確認：`before.label` 為 `"未提供"` 時，不顯示 `after.label` 的值
- [x] 8.3 確認：`detail.source` 永遠可見（`"UpdateReport.l2_details"` 或 `"UpdateReport.l1_changes"`）

**Checkpoint**：點選差異模式的變更項目，DetailPanel 顯示 Before/After 和資料來源，無補值行為

---

## Task 9: 實作前端單版本模式（舊版/新版）

**對應 Req 7、Design §3.3**

- [x] 9.1 擴充 `renderChangeList()`（單版本模式）：
  - 讀取 `state.l1Model.features`
  - 無 l1Model 或 features 為空時顯示 empty-state
  - 每筆顯示 feature label（無 change_type symbol）
- [x] 9.2 擴充 `renderGraphCanvas()`（單版本模式）：
  - 顯示 feature 節點，無 change_type badge
- [x] 9.3 擴充 `renderDetailPanel()`（單版本模式）：
  - 讀取 `state.l1Model.features` 中對應 `state.selectedId` 的 feature
  - 顯示 `description`、`trigger_description`、`confidence`、`confidence_reason`
  - `source_nodes` 為空時顯示「未提供」
  - 顯示 `feature.source`（`"L1Output.features"`）

**Checkpoint**：切換到舊版/新版模式，ChangeList 顯示 feature 清單，DetailPanel 顯示 feature 詳情

---

## Task 10: 驗收測試 — 完整流程驗證

**對應 Req 16 驗收標準（spec.md §16）**

- [x] 10.1 執行完整測試套件，確認無退步：
  ```
  pytest tests/unit/core/ui/test_view_model.py
  pytest tests/property/test_view_model_properties.py
  ```
- [x] 10.2 手動瀏覽器驗收（透過 `python -m http.server 8765`，開啟 `http://127.0.0.1:8765/docs/frontend-local-version-viewer/viewer/`）：
  - [ ] 可在無外部網路情況下啟動並讀取本地資料
  - [ ] 顯示 L0 摘要
  - [ ] 差異模式：ChangeList 數量與 `update-view-model.json` 的 `change_counts` 一致
  - [ ] 點選變更可看到 Before/After 與資料來源
  - [ ] 切換到舊版/新版模式，顯示 feature 清單
  - [ ] 差異模式按鈕在 `diff_available=false` 時為 disabled
  - [ ] 無 console error，無空白畫面
- [x] 10.3 確認 `viewer/` 目錄下無 CDN 引用（Windows PowerShell）：
  ```powershell
  Select-String -Path "docs/frontend-local-version-viewer/viewer/*" -Pattern "cdn\.|unpkg\.com|jsdelivr\.net|googleapis\.com" -Recurse
  ```
  無任何輸出即為通過。

**Checkpoint**：所有 Python 測試通過，手動驗收 7 項全部確認
