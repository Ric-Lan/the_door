# 步驟 6 — ui-modal.js

## 概覽

| 模組 | 來源行號（app.js） | 預估行數 | 依賴 |
|---|---|---|---|
| `js/ui-modal.js` | 420–553 | ~140 | `state.js`, `api.js`, `dom.js` |

---

## 匯出介面

```js
export function showUpdateModal()
export function hideUpdateModal()
export function showModalError(message)
export function renderPipelineProgress(job)
export function submitUpdate(oldPath, newPath, callbacks = {})   // callbacks: { onComplete, onError }
export function startPolling(jobId, callbacks = {})
export function stopPolling()
export function pollJobStatus(jobId, callbacks = {})
```

---

## 各函式規格

### showUpdateModal()

- `els.inputOldPath.value` = `state.projectStatus?.project_path || ""`
- `els.inputNewPath.value` = `""`
- `els.inputLanguage.value` = `"zh-Hant"`（若 element 存在）
- `els.modalError.hidden` = true
- `#modal-project-hint`：有 project_path → 顯示路徑文字；否則 hidden
- `els.updateModal.hidden` = false
- focus `els.inputNewPath`

### hideUpdateModal()

`els.updateModal.hidden` = true

### showModalError(message)

`els.modalError.textContent` = message，`els.modalError.hidden` = false

### renderPipelineProgress(job)

- `els.currentStep.textContent` = job.current_step ? "執行中：" + job.current_step : ""
- 清空 `els.stepsList`，為每個 step 插入 `<li class="step-item step-<status>">`
- 每個 li 含：狀態符號（✓/✗/⊘）+ step_name + duration（若有）
- 有 error_message → 插入 `<span class="step-error">`

### startPolling(jobId, callbacks = {})

- `state.pollingJobId` = jobId
- `els.pipelineProgress.hidden` = false
- `els.stepsList.textContent` = ""
- `els.currentStep.textContent` = "初始化…"
- `state.pollingHandle` = setInterval(() => pollJobStatus(jobId, callbacks), 1500)

### stopPolling()

- `clearInterval(state.pollingHandle)`
- `state.pollingHandle` = null
- `state.pollingJobId` = null

### submitUpdate(oldPath, newPath, callbacks = {})

路徑由呼叫方傳入（外部在呼叫前已驗證非空）：
- 呼叫 `api.postUpdate(oldPath, newPath, language)`（language = `els.inputLanguage?.value || "zh-Hant"`）
- 成功（有 job_id）→ `startPolling(jobId, callbacks)`
- fetch !ok → `callbacks.onError?.(message)` 或 `showModalError(message)`
- network error → `callbacks.onError?.(message)` 或 `showModalError(message)`

### pollJobStatus(jobId, callbacks = {})

- 呼叫 `api.fetchJobStatus(jobId)`
- 呼叫 `renderPipelineProgress(job)`
- status = "completed" → `stopPolling()`，`els.pipelineProgress.hidden = true`，`callbacks.onComplete?.()`
- status = "failed" → `stopPolling()`，`els.pipelineProgress.hidden = true`，`showModalError(job.error_message)`
- fetch 失敗 → `stopPolling()`，`showModalError(...)`

---

## 測試規格

### tests/ui-modal.test.js

| 測試案例 | 驗證 |
|---|---|
| showUpdateModal | updateModal 不 hidden，inputOldPath 有值，inputNewPath 清空 |
| showUpdateModal — 有 project_path | #modal-project-hint 顯示路徑 |
| showUpdateModal — 無 project_path | #modal-project-hint hidden |
| hideUpdateModal | updateModal hidden = true |
| showModalError | modalError 不 hidden，textContent 正確 |
| renderPipelineProgress — current_step | currentStep.textContent 含步驟名稱 |
| renderPipelineProgress — 空 steps | stepsList 為空 |
| renderPipelineProgress — completed step | li 含 "✓"，有 duration 文字 |
| renderPipelineProgress — failed step | li 含 "✗"，有 error_message span |
| stopPolling — 清除 handle | state.pollingHandle = null |
| stopPolling — 清除 jobId | state.pollingJobId = null |
| startPolling | pipelineProgress 顯示，state.pollingHandle 被設定 |
| submitUpdate — fetch 成功 | startPolling 被呼叫，傳入 jobId 與 callbacks |
| submitUpdate — fetch !ok | callbacks.onError 或 showModalError 被呼叫 |
| submitUpdate — network error | callbacks.onError 或 showModalError 被呼叫 |
| pollJobStatus — completed | stopPolling 被呼叫，callbacks.onComplete 被呼叫 |
| pollJobStatus — failed | stopPolling 被呼叫，showModalError 被呼叫 |
| pollJobStatus — fetch 失敗 | stopPolling 被呼叫 |

---

## TDD 步驟

1. **RED**：寫 `tests/ui-modal.test.js`，確認失敗
2. **GREEN**：建立 `js/ui-modal.js`，最小實作
3. **REFACTOR**：整理

## 驗證檢查清單

- [ ] `npm test tests/ui-modal.test.js` — 全部通過
- [ ] 啟動伺服器，重新分析 modal 開關正常，提交後 pipeline progress 顯示
