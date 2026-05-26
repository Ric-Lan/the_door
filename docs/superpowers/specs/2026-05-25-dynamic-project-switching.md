# Spec: Dynamic Project Path Switching

**Date:** 2026-05-25 (revised 2026-05-26)
**Status:** TODO — 待實作  
**Priority:** Backlog

---

## 背景

`UIServer` 目前在初始化時將 `project_root` 寫死進 `self._project_root`，整個 server 生命週期無法更換。使用者若想分析不同專案，必須重啟 server。

本 spec 描述如何讓 server 在執行期接受新的專案路徑，不需要 project registry。

---

## 需求

1. 使用者可在 wizard.html 頁尾的路徑輸入框輸入本機絕對路徑，切換 server 當前綁定的專案
2. 切換時若有進行中的 job，前端顯示選擇視窗，由使用者決定行為
3. 切換完成後前端強制 reload 至 wizard.html，確保顯示新專案資料

---

## API 設計

### `POST /api/set-project`

合併非強制與強制為單一端點，以 `force` 參數區分。

**Request body:**
```json
{ "path": "/absolute/path/to/project", "force": false }
```

**Response（成功）:**
```json
{ "status": "switched", "path": "/absolute/path/to/project" }
```

**Response（有進行中 job 且 force=false）:**
```json
{
  "status": "conflict",
  "active_job_id": "job-id-1",
  "message": "有進行中的分析任務，請選擇處理方式"
}
```

**Response（路徑無效）:**
```json
{ "status": "error", "message": "路徑不存在或無法讀取" }
```

**force=true 行為：** 將 running job 標記為 `failed`（`error_message="switched away"`），建立全新空 `JobStore`，然後切換路徑。不保留舊 JobStore。

---

## Server 端行為

### 路徑驗證
切換前執行：
- `Path(path).exists()` — 路徑存在
- `Path(path).is_dir()` — 是目錄
- `os.access(path, os.R_OK)` — 有讀取權限

任一失敗 → 回傳 `error`，不切換。

### 並發安全

`UIServer` 新增 `threading.Lock` 保護 `_project_root` 和 `_job_store` 的讀寫：

```python
self._switch_lock = threading.Lock()
```

所有讀取 `_project_root`、`_job_store` 的操作都在 `_switch_lock` 保護下進行。`APIHandlers` 不持有 `project_root` 的副本，每次 request 透過 `server` 引用（見下方）。

### APIHandlers 存取 project_root

**修改方式：** `APIHandlers.__init__` 接受一個 callable `project_root_fn: Callable[[], Path]`（而非 Path 本身）。每次需要 `project_root` 時呼叫此 fn，即可即時取得最新路徑，不需要 lock。

```python
# UIServer.__init__ 中：
self._api_handlers = APIHandlers(
    project_root_fn=lambda: self._project_root,
    job_store_fn=lambda: self._job_store,
)
```

`lambda` 在 GIL 保護下是原子讀取，搭配 `_switch_lock` 在切換時保護寫入即可。

### 切換流程（非強制）

1. 驗證路徑
2. 取得 `_switch_lock`
3. 若 `_job_store.has_running_job` → 釋放 lock，回傳 `conflict`
4. 更新 `self._project_root = new_path`
5. 建立 `self._job_store = JobStore()`（舊 JobStore 自然 GC）
6. 釋放 lock，回傳 `switched`

### 切換流程（force=true）

1. 驗證路徑
2. 取得 `_switch_lock`
3. 若有 running job → 呼叫 `self._job_store.fail_job(job_id, "switched away")`
4. 更新 `self._project_root = new_path`
5. 建立 `self._job_store = JobStore()`
6. 釋放 lock，回傳 `switched`

---

## 前端行為

### 切換入口

位置：**wizard.html 頁尾**（PAGE_ACTION 頁面底部加一個收合式文字輸入區）。

```
──────────────────────────────────
切換至其他專案
[路徑輸入框                    ] [切換]
```

JS 模組：新增 `switchProject(path, force=false)` 函式至 `ui-wizard.js`，呼叫 `POST /api/set-project`。

### 衝突處理視窗

當收到 `status: conflict` 時顯示 inline 確認區（不用 modal，避免瀏覽器 modal 被 blocker）：

```
目前有進行中的分析任務
[立即切換（中斷任務）]   [取消]
```

「等待完成後切換」**不實作**（需要後端 push 通知機制，超出本 spec 範圍）。前端只提供立即切換和取消。

### 切換完成

收到 `status: switched` 後：
- `window.location.href = '/wizard.html'`（強制重新載入，清空所有前端狀態）

---

## 不在本 spec 範圍內

- Project registry（記錄曾分析過的所有專案）
- 路徑 picker UI（OS 原生 file dialog）— 瀏覽器安全限制無法實作，使用者手動輸入路徑
- 多專案同時開啟（單一 server 實例只綁定一個專案）
- 「等待完成後切換」（需要後端 push 通知，超出範圍）
- Job archive（舊 JobStore 切換後直接 GC）

---

## 依賴

- 本 spec 依賴 wizard UI spec（`2026-05-25-wizard-ui-design.md`）已完成（切換入口整合進 wizard.html）
- wizard UI 已 merge main（`63352eb`），可直接接手

---

## 測試要求

- TDD，100% coverage
- Python unit：
  - `test_api_handlers_set_project.py` — 路徑驗證、非強制 conflict、force 切換
  - `test_server_set_project.py` — 路由、lock 正確性
  - `test_server_switch_concurrency.py` — 切換中有 request 進來不 crash
- JS unit（`ui-wizard.test.js` 新增 describe block）：
  - `switchProject` 呼叫正確 API
  - conflict inline 確認區顯示與消失
  - 成功後 redirect 被呼叫

---

## 架構異動摘要（最小）

| 檔案 | 異動 |
|---|---|
| `job_store.py` | 無異動（`fail_job` 已存在，`"switched away"` 只是 error_message 字串）|
| `api_handlers.py` | `__init__` 改接受 `project_root_fn` + `job_store_fn` callable；新增 `handle_post_set_project` |
| `server.py` | 新增 `_switch_lock`；`APIHandlers` 用 lambda 傳入；新增 `/api/set-project` 路由 |
| `ui-wizard.js` | 新增 `switchProject()`；PAGE_ACTION 加切換入口 UI |
| `ui-wizard.test.js` | 新增對應 describe block |
