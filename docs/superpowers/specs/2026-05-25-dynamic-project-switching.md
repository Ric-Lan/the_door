# Spec: Dynamic Project Path Switching

**Date:** 2026-05-25  
**Status:** TODO — 待實作  
**Priority:** Backlog

---

## 背景

`UIServer` 目前在初始化時將 `project_root` 寫死進 `self._project_root`，整個 server 生命週期無法更換。使用者若想分析不同專案，必須重啟 server。

本 spec 描述如何讓 server 在執行期接受新的專案路徑，不需要 project registry。

---

## 需求

1. 使用者可在 UI 中輸入/貼上本機路徑，切換 server 當前綁定的專案
2. 切換時若有進行中的 job，前端顯示選擇視窗，由使用者決定行為
3. 舊 job 紀錄在切換後移至 archive，不再被正常輪詢讀到
4. 切換完成後前端強制 reload，確保顯示新專案資料

---

## API 設計

### `POST /api/set-project`

**Request body:**
```json
{ "path": "/absolute/path/to/project" }
```

**Response（成功，無進行中 job）:**
```json
{ "status": "switched", "path": "/absolute/path/to/project" }
```

**Response（有進行中 job）:**
```json
{
  "status": "conflict",
  "active_jobs": ["job-id-1"],
  "message": "有進行中的分析任務，請選擇處理方式"
}
```

**Response（路徑無效）:**
```json
{ "status": "error", "message": "路徑不存在或無法讀取" }
```

### `POST /api/set-project/force`

強制切換，中斷進行中的 job。

**Request body:**
```json
{ "path": "/absolute/path/to/project" }
```

**Response:**
```json
{ "status": "switched", "path": "...", "archived_jobs": ["job-id-1"] }
```

---

## Server 端行為

### 路徑驗證
切換前執行：
- `Path(path).exists()` — 路徑存在
- `Path(path).is_dir()` — 是目錄
- `os.access(path, os.R_OK)` — 有讀取權限

任一失敗 → 回傳 `error`，不切換。

### 並發處理
- `POST /api/set-project`（非強制）：若 JobStore 有 `status=running` 的 job → 回傳 `conflict`，不切換
- `POST /api/set-project/force`：將所有 running job 標記為 `cancelled`，移至 archive，然後切換

### JobStore Archive
- 切換時，現有 JobStore 內容移至 `self._archived_job_stores`（list）
- 建立新的空 JobStore 給新路徑使用
- archived job stores 只供查詢歷史用（不主動輪詢）

### APIHandlers 更新
- `APIHandlers` 從 `server.py` 的 `self._project_root` 讀路徑（不在 init 時固定）
- 或改為每次 request 時從 server instance 取得最新路徑

---

## 前端行為

### 切換入口
- 位置待定（wizard.html Welcome 頁 / viewer header）
- 輸入框接受本機絕對路徑

### 衝突處理視窗
當收到 `status: conflict` 時顯示 modal：

```
目前有進行中的分析任務

[等待完成後切換]   [立即切換（中斷任務）]   [取消]
```

### 切換完成
收到 `status: switched` 後：
- 清空前端所有快取狀態
- `window.location.reload()` 或跳轉至 wizard.html

---

## 不在本 spec 範圍內

- Project registry（記錄曾分析過的所有專案）
- 路徑 picker UI（OS 原生 file dialog）— 瀏覽器安全限制無法實作，使用者手動輸入路徑
- 多專案同時開啟（單一 server 實例只綁定一個專案）

---

## 依賴

- 本 spec 獨立於 wizard UI spec（`2026-05-25-wizard-ui-design.md`）
- 可在 wizard UI 實作完成後再接手，也可平行執行
- 若 wizard UI 先完成，切換入口可整合進 wizard.html；否則獨立頁面

---

## 測試要求

- TDD，100% coverage
- Python unit：`test_api_handlers_set_project.py`、`test_server_set_project.py`
- JS unit：conflict modal 狀態機
- E2E：切換路徑 → reload → 新專案資料顯示正確
