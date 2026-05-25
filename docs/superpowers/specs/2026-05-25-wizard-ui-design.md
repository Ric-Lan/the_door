# Wizard UI — 結構化問卷入口

**日期：** 2026-05-25
**狀態：** 已核准，待實作

---

## 1. 問題陳述

The Door 目前的入口是 CLI 指令（`the-door analyze`、`the-door wizard`）。
非技術使用者看 README 後啟動伺服器，面對的第一頁是 Viewer 的分析畫面，
沒有任何引導。這造成兩個問題：

1. **使用者不知道下一步要做什麼**（首次使用無 snapshot 時尤其明顯）
2. **LLM agent 發散**：在 MCP 模式下，agent 沒有固定輸入模板，容易自行決策偏離預期

解法：`wizard.html` — 一個獨立的多頁問卷頁面，伺服器啟動後作為第一個入口，
引導使用者（或 agent）填答結構化問題，再送出執行。

---

## 2. 範圍（In / Out）

**In scope：**
- `wizard.html`：多頁問卷，在 `docs/frontend-local-version-viewer/viewer/` 內
- `js/ui-wizard.js`：問卷狀態機邏輯
- `cli/ui_cmd.py`：啟動時預設開啟 `wizard.html` 而非 `index.html`
- Agent 模式：無 API key 時顯示結構化參數供複製

**Out of scope：**
- 在 web UI 裡切換/選擇不同專案（伺服器是 path-scoped，留給 CLI picker）
- 修改 `index.html` 或任何現有 Viewer JS 檔案

**說明：** 現有 `/api/update` 要求 `old_path`/`new_path`（版本 diff 用），無法用於首次分析。
因此需新增一個 `/api/analyze` endpoint 供 wizard 觸發分析工作。

---

## 3. 架構

```
the-door ui <path>
    │
    └─► UIServer 啟動（path-scoped，不變）
            │
            └─► 瀏覽器開啟 /wizard.html（取代原本的 /index.html）
                    │
                    ├─► GET /api/status  ← 判斷目前狀態
                    │
                    ├─► [問卷流程]
                    │
                    ├─► POST /api/update  ← 送出執行
                    │
                    ├─► GET /api/update/status/<job_id>  ← 進度輪詢（已有）
                    │
                    └─► redirect /index.html  ← 完成後進 Viewer
```

**檔案職責：**

| 檔案 | 職責 | 依賴 |
|---|---|---|
| `wizard.html` | 問卷入口頁，link `styles.css`，載入 `ui-wizard.js` | `styles.css`（共用） |
| `js/ui-wizard.js` | 頁面狀態機、API 呼叫、進度輪詢 | `/api/status`、`/api/update`、`/api/update/status/` |
| `cli/ui_cmd.py` | 啟動時改開 `/wizard.html` | 不變動 server.py |
| `core/ui/api_handlers.py` | 新增 `handle_post_analyze` | SnapshotStore、pipeline |
| `core/ui/server.py` | 註冊 `/api/analyze` POST 路由 | api_handlers |

**不動的檔案：** `index.html`、所有現有 `js/` 檔

---

## 4. 問卷流程規格

### 4.1 頁面狀態機

```
LOADING
  │ GET /api/status 完成
  ▼
PAGE_ACTION   ← 選擇操作（依 has_snapshots 顯示不同選項）
  │
  ├─ "查看快照" → redirect /index.html（不需問卷）
  │
  ├─ "首次分析" → PAGE_SETUP → PAGE_LABEL → PAGE_CONFIRM
  │
  └─ "更新分析" → PAGE_CONFIRM
          │
          ▼
       SUBMITTING  ← POST /api/update
          │
          ▼
       PROGRESS    ← 輪詢 /api/update/status/<job_id>，每 1500ms
          │
          ├─ status == "running"  → 繼續輪詢，更新步驟顯示
          ├─ status == "done"     → redirect /index.html
          └─ status == "failed"   → PAGE_ERROR
```

### 4.2 各頁面的問題與欄位

**PAGE_ACTION**（依 `has_snapshots` 動態）

- 無快照：選項 A「首次分析此專案」、選項 B「我只想查看（需先有快照）」
- 有快照：選項 A「更新分析（重新跑）」、選項 B「直接查看現有快照」

**PAGE_SETUP**（首次分析才出現）

- 顯示偵測到的檔案數（讀 `/api/status`）
- 欄位：要排除的目錄（逗號分隔，選填）

**PAGE_LABEL**（首次分析才出現）

- 欄位：快照標籤（placeholder `v1.0.0`，選填）

**PAGE_CONFIRM**

- 顯示摘要：專案路徑、操作、排除目錄、標籤、模式（API key / Agent）
- 按鈕：「確認送出」

### 4.3 進度頁（PROGRESS）

顯示固定的步驟列表，目前執行中的步驟高亮：

1. 探索檔案
2. 擷取結構（AST）
3. LLM 分析（Agent 模式：「等待 agent 執行」）
4. 寫入快照

每個步驟有三種狀態：`pending`（灰）、`running`（高亮 + 動畫點）、`done`（綠勾）。

### 4.4 Agent 模式（無 API key）

`PAGE_CONFIRM` 送出後，進入 `PROGRESS` 頁，但不呼叫 `/api/update`。
改顯示「給 agent 的參數區塊」：

```
extract_structure(codebase_path="<路徑>")
snapshot_write(codebase_path="<路徑>", l1_features=[...], label="<標籤>")
```

附「複製」按鈕。使用者把這段貼給 Claude，Claude 按固定格式執行。
頁面底部有「我已讓 agent 執行完畢，進入 Viewer」按鈕 → redirect `/index.html`。

判斷 Agent 模式：呼叫 `/api/status`，若回傳的 `has_api_key === false` 即為 Agent 模式。

---

## 5. API 合約

### GET /api/status（已有，不改）

wizard 使用的欄位（`state` 物件由 `StateInspector.inspect()` 產出）：

```json
{
  "state": {
    "has_snapshots": true,
    "has_api_key": false
  },
  "next_actions": [...]
}
```

`state.has_snapshots`、`state.has_api_key` 均已存在於現有實作。

### POST /api/analyze（新增）

觸發首次分析或重新分析當前專案。

Request body：

```json
{
  "extra_ignore": ["tests/", "docs/"],
  "label": "v1.0.0"
}
```

- `extra_ignore`：選填，字串陣列，附加排除目錄
- `label`：選填，字串，快照標籤

Response（202）：

```json
{ "job_id": "abc123" }
```

### GET /api/update/status/\<job_id\>（已有，不改）

```json
{
  "job_id": "abc123",
  "status": "running",
  "current_step": "LLM 分析",
  "steps": [
    { "step_name": "探索檔案", "status": "done" },
    { "step_name": "LLM 分析", "status": "running" }
  ]
}
```

`status` 值：`"running"` | `"done"` | `"failed"`
`current_step`：目前執行中的步驟名稱（字串），完成時為 `null`

---

## 6. 測試規格（TDD）

所有測試放在 `viewer/tests/ui-wizard.test.js`，使用 Vitest（同現有測試套件）。

### 6.1 狀態機轉換測試

```js
// 有快照 → PAGE_ACTION 顯示「更新」和「查看」選項
test('has_snapshots=true shows update and view options')

// 無快照 → PAGE_ACTION 顯示「首次分析」選項
test('has_snapshots=false shows analyze option')

// 首次分析路徑：PAGE_ACTION → PAGE_SETUP → PAGE_LABEL → PAGE_CONFIRM
test('first analysis navigates through setup and label pages')

// 更新路徑：PAGE_ACTION → PAGE_CONFIRM（跳過 setup/label）
test('update skips setup page and goes directly to confirm')

// 查看路徑：PAGE_ACTION → 立即 redirect
test('view option redirects without wizard pages')
```

### 6.2 欄位驗證測試

```js
// 排除目錄：逗號分隔正確解析
test('excludes parsing: comma-separated strings trimmed correctly')

// 排除目錄：空字串 → 空陣列
test('excludes parsing: empty string returns empty array')

// 標籤：空字串 → undefined（不傳給 API）
test('label: empty string is omitted from request')
```

### 6.3 API 整合測試（mock fetch）

```js
// 送出後取得 job_id
test('submit calls POST /api/update with correct body')

// 進度輪詢：running → 繼續
test('progress: running status continues polling')

// 進度輪詢：done → 停止輪詢，觸發 redirect
test('progress: done status stops polling and redirects')

// 進度輪詢：failed → 顯示錯誤頁
test('progress: failed status shows error page')

// 輪詢間隔 1500ms
test('polling interval is 1500ms')
```

### 6.4 Agent 模式測試

```js
// has_api_key=false → 顯示結構化參數區塊，不呼叫 /api/update
test('agent mode: shows structured params block instead of calling update')

// 參數區塊包含正確的 codebase_path 和 label
test('agent mode: params block contains correct path and label')

// 「已執行完畢」按鈕觸發 redirect
test('agent mode: manual complete button redirects to index.html')
```

### 6.5 進度步驟顯示測試

```js
// stage → 對應步驟高亮
test('stage "ast_extraction" highlights step 2')

// 前面的步驟標記為 done
test('stages before current show as done')
```

---

## 7. 錯誤處理

| 情境 | 行為 |
|---|---|
| GET /api/status 失敗 | 顯示「無法連線到伺服器，請重新整理」，不進入問卷 |
| POST /api/update 失敗 | 顯示錯誤訊息 + 「返回修改」按鈕 |
| 進度輪詢連續 3 次失敗 | 停止輪詢，顯示「分析可能仍在進行，請直接前往 Viewer 確認」+ 連結 |
| 使用者在問卷中途重新整理 | 回到 LOADING → PAGE_ACTION（不保存問卷狀態，重填即可） |

---

## 8. 風格一致性

`wizard.html` 以 `<link rel="stylesheet" href="styles.css">` 引用現有樣式。
使用的 CSS 類別均來自現有 `styles.css`：

- `--accent`、`--bg`、`--surface`、`--text`、`--muted`、`--line`（CSS 變數）
- 進度步驟使用 `--accent`（當前）、`--muted`（待執行）、`--added-fg`（已完成）
- `.onboarding-card` 不存在於 `styles.css`，改用 `--surface` + `--shadow` 自訂 `.wizard-card`

不在 `wizard.html` 內寫任何 inline CSS。wizard 專用樣式（`.wizard-card`、`.wizard-step` 等）
另建 `wizard.css`，由 `wizard.html` 引用，不污染 `styles.css`。

---

## 9. 實作檢查清單（給 writing-plans 使用）

- [ ] `viewer/wizard.html` — 骨架 + link styles.css + link wizard.css + script 引用
- [ ] `viewer/wizard.css` — wizard 專用樣式（`.wizard-card`、`.wizard-step` 等）
- [ ] `viewer/js/ui-wizard.js` — 狀態機 + 各頁面 render 函式 + API 呼叫
- [ ] `viewer/tests/ui-wizard.test.js` — 上述所有測試（TDD：測試先寫）
- [ ] `core/ui/api_handlers.py` — 新增 `handle_post_analyze`
- [ ] `core/ui/server.py` — 註冊 `/api/analyze` POST 路由
- [ ] `cli/ui_cmd.py` — 啟動時改開 `wizard.html`（1 行修改）
- [ ] 驗收：`the-door ui <test-target>` 啟動後，瀏覽器開啟 wizard，走完完整流程進 Viewer
