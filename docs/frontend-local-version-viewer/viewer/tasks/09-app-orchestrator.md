# 步驟 9 — 新 js/app.js（Thin Orchestrator）

## 概覽

| 模組 | 來源行號（app.js） | 預估行數 | 依賴 |
|---|---|---|---|
| `js/app.js` | 110–188, 243–283, 568–598 | ~200 | 所有上述模組 |

**職責**：事件綁定、頂層 `render()`、`setMode()`、`loadProjectStatus()`、`loadFromApi()`、`populateVersionSelectors()`。  
不定義 `els`（已移至 dom.js）。不直接操作 DOM 元素。

---

## import 清單

```js
import { state } from './state.js';
import { els } from './dom.js';
import { API_BASE } from './api.js';
import { buildViewModelFromReport, snapshotLabel } from './viewmodel.js';
import { renderTopBar, updateLogoMark } from './ui-topbar.js';
import { renderChangeList } from './ui-list.js';
import { renderDetailPanel, renderError } from './ui-detail.js';
import { showUpdateModal, hideUpdateModal, showModalError, submitUpdate } from './ui-modal.js';
import { loadL1Graph, switchToL1, switchToMindmap } from './layers.js';
import { initGraph, renderLegend, openGraphDrawer, closeGraphDrawer } from './graph.js';
```

**API 呼叫策略**：與 layers.js 相同，使用 `fetch + API_BASE` 直接呼叫，不走 api.js wrapper。原因：`loadProjectStatus` 需區分 `!res.ok` → `renderError` 與 catch（網路錯誤）→ `loadStaticFallback` 兩條路徑，wrapper 已丟棄 status/ok。

---

## 匯出介面

```js
export function render()
export async function setMode(mode)
export function init()
```

其餘（`selectItem`, `firstSelectableId`, `loadProjectStatus`, `loadFromApi`, `loadReport`, `loadSnapshots`, `loadStaticFallback`, `populateVersionSelectors`, `handleApiError`）為模組內私有函式。

**為何 setMode 是 async**：呼叫 `await loadL1Graph(...)`（layers.js 的 async function）以確保 version-compare 模式切換能等到 graph 載入完畢再回到呼叫端。

**為何 boot 用 export init() 而非模組頂層執行**：
- 模組頂層 `loadProjectStatus()` 會導致任何 import app.js 的測試一執行就觸發 fetch，造成 mock 順序敏感性（mock 必須在 import 前完成，否則 fetch 已 fire）→ 測試 flakiness。
- 用 `init()` 把事件綁定 + `loadProjectStatus()` 包成一個 explicit entry point，測試可在 init() 呼叫前完整設定 mocks，可控、可重複測試。
- Step 10 的 HTML 只需 `import { init } from './js/app.js'; init();` 一行接線。

---

## 各函式規格

### render()

呼叫順序（與 app.js 一致，避免視覺 regression）：

```js
renderTopBar();
renderChangeList({ onSelect: selectItem });
renderDetailPanel();
updateLogoMark();
document.querySelector('.app-shell')?.classList.toggle('diff-mode', state.mode === 'diff');
const banner = document.getElementById('diff-mode-banner');
if (banner) banner.hidden = state.mode !== 'diff';
```

### selectItem(id)（私有）

```js
function selectItem(id) {
  state.selectedId = id;
  render();
}
```

傳給 `renderChangeList` 的 `onSelect` callback。

### setMode(mode)（async）

- `hasDiff = state.updateModel?.diff_available === true`
- `hasVersionCompare = !!(state.versionA && state.versionB && state.versionA !== state.versionB)`
- `mode === "diff" && !hasDiff && !hasVersionCompare` → return（不改 state）
- 否則：`state.mode = mode`，`state.selectedId = firstSelectableId()`，呼叫 `render()`
- `hasVersionCompare && !hasDiff`（版本比較切換，重新拉對應版本的 L1 graph）：
  - `mode === "baseline"` → `await loadL1Graph(state.versionA)`
  - `mode === "current"` → `await loadL1Graph(state.versionB)`
  - `mode === "diff"` → `await loadL1Graph(state.versionB)`（diff overlay 在 loadL1Graph 內自動套用）

### firstSelectableId()（私有）

```js
function firstSelectableId() {
  if (state.mode === "diff") return state.updateModel?.changes?.[0]?.id ?? null;
  return state.l1Model?.features?.[0]?.id ?? null;
}
```

### loadProjectStatus()（私有 async）

直接 `fetch`：

- `fetch(\`${API_BASE}/api/project\`, { cache: "no-store" })`
- `!res.ok` → `body = await res.json().catch(() => null)`，`renderError(body?.error?.message || "無法取得專案狀態（" + res.status + "）")`，return（不 fallback）
- 成功 → `state.projectStatus = await res.json()`，`await loadFromApi()`
- catch（網路錯誤）→ `await loadStaticFallback()`

### loadFromApi()（私有 async）

- `ps = state.projectStatus`，若 null → return
- `ad = ps.available_data || {}`
- 若 `ad.has_latest_report` → `await loadReport()`
- 否則 → `state.updateModel = null`、`els.summaryText.textContent = "尚未有分析報告。請執行 the-door update 或點擊「重新分析」。"`
- 若 `ad.has_snapshots` → `await loadSnapshots()`
- `hasVersionCompare = !!(state.versionA && state.versionB && state.versionA !== state.versionB)`
- `state.mode = "baseline"`、`state.selectedId = firstSelectableId()`、`render()`
- 若 `ad.has_snapshots` → `await loadL1Graph(hasVersionCompare ? state.versionB : null)`

### loadReport()（私有 async）

- `fetch(\`${API_BASE}/api/report/latest\`, { cache: "no-store" })`
- `res.status === 404` → `state.updateModel = null`，return
- `!res.ok` → `body = await res.json().catch(() => null)`、`handleApiError(res.status, body)`，return
- 成功 → `report = await res.json()`，`state.updateModel = buildViewModelFromReport(report)`
- catch → `renderError("載入報告失敗：" + (err.message || "network error"))`

### loadSnapshots()（私有 async）

- `fetch(\`${API_BASE}/api/snapshots\`, { cache: "no-store" })`
- `!res.ok` → 靜默 return
- 成功 → `data = await res.json()`，`state.snapshots = data.snapshots || []`
  - `state.versionA = state.snapshots[1]?.version_id ?? null`（baseline = older = index 1）
  - `state.versionB = state.snapshots[0]?.version_id ?? null`（current = newest = index 0）
  - 呼叫 `populateVersionSelectors()`
- catch → 靜默（non-fatal）

### handleApiError(status, body)（私有）

```js
function handleApiError(status, body) {
  const msg = body?.error?.message || "HTTP " + status;
  renderError("API 錯誤：" + msg);
}
```

### loadStaticFallback()（私有 async）

兩段獨立的 fetch：

**第一段 — update-view-model.json**

- `fetch("./data/update-view-model.json", { cache: "no-store" })`
- `!res.ok` → `renderError("./data/update-view-model.json: " + res.status)`，return（不再嘗試第二段）
- 成功 → `state.updateModel = await res.json()`
- catch → `renderError("./data/update-view-model.json: " + (err.message || "network error"))`，return

**第二段 — l1-view-model.json（best-effort，失敗不致命）**

- `fetch("./data/l1-view-model.json", { cache: "no-store" })`
- `res.ok` 且解析成功 →
  - `state.l1GraphViewModel = graphData`
  - `state.l1Model = { features: graphData.nodes.map(...), stats: { feature_count } }`（同 loadL1Graph 的 features 結構）
- catch → `state.l1GraphViewModel = null`、`state.l1Model = null`

**收尾**

- `state.mode = state.updateModel?.diff_available ? "diff" : "baseline"`
- `state.selectedId = firstSelectableId()`
- `render()`
- 若 `state.l1GraphViewModel` 存在 → `state.layerState = "L1"`、`initGraph("graph-container", state.l1GraphViewModel)`、`renderLegend()`

### populateVersionSelectors()（私有）

（來源行號：app.js 243–283）

- `selA = document.getElementById("select-version-a")`、`selB = document.getElementById("select-version-b")`、`selectorBar = document.getElementById("version-selector-bar")`
- 任一不存在 → return
- `state.snapshots.length <= 1` → `selectorBar.hidden = true`，return
- 否則 `selectorBar.hidden = false`
- **以 forEach + idx** 迴圈處理 selA(idx=0) / selB(idx=1)：
  - 清空 `sel.innerHTML = ""`
  - 為每個 snapshot append `<option value="<version_id>">snapshotLabel(s)</option>`
  - 預設值：`sel.value = idx === 0 ? state.versionA : state.versionB`
- **使用 `sel.onchange`（賦值型）覆寫，避免多次呼叫累積 handler**：
  - `selA.onchange = async () => { state.versionA = selA.value; state.mode = "diff"; renderTopBar(); await loadL1Graph(state.versionB ?? state.versionA); }`
  - `selB.onchange = async () => { state.versionB = selB.value; state.mode = "diff"; renderTopBar(); await loadL1Graph(state.versionB); }`

---

## init() — 事件綁定 + 啟動

```js
export function init() {
  els.btnDiff.addEventListener("click",        () => setMode("diff"));
  els.btnBaseline.addEventListener("click",    () => setMode("baseline"));
  els.btnCurrent.addEventListener("click",     () => setMode("current"));
  els.btnReanalyze.addEventListener("click",   () => showUpdateModal());
  els.btnModalCancel.addEventListener("click", () => hideUpdateModal());
  els.btnModalSubmit.addEventListener("click", () => {
    const oldPath = els.inputOldPath.value.trim();
    const newPath = els.inputNewPath.value.trim();
    if (!oldPath || !newPath) { showModalError("請輸入舊版與新版路徑。"); return; }
    hideUpdateModal();
    submitUpdate(oldPath, newPath, {
      onComplete: () => { loadFromApi(); },
      onError: renderError,
    });
  });
  els.btnGraphToggle?.addEventListener("click", openGraphDrawer);
  els.btnDrawerClose?.addEventListener("click", closeGraphDrawer);
  els.graphBackdrop?.addEventListener("click",  closeGraphDrawer);
  els.btnMindmap?.addEventListener("click",     switchToMindmap);
  els.btnBackL1?.addEventListener("click",      switchToL1);
  loadProjectStatus();
}
```

Step 10 的 `js/app.js` HTML 接線：

```html
<script type="module">
  import { init } from './js/app.js';
  init();
</script>
```

---

## 測試規格

### tests/app.test.js

測試方法：`vi.mock('../js/ui-topbar.js', ...)` mock 所有依賴模組，驗證 orchestration 邏輯。

| 測試案例 | 驗證 |
|---|---|
| render — 呼叫順序 | renderTopBar → renderChangeList → renderDetailPanel → updateLogoMark |
| render — mode=diff | .app-shell 含 diff-mode class，#diff-mode-banner 不 hidden |
| render — mode≠diff | .app-shell 移除 diff-mode class，#diff-mode-banner hidden |
| render — 無 .app-shell | 不 throw |
| render — 無 #diff-mode-banner | 不 throw |
| render — onSelect → selectItem | onSelect 觸發後 state.selectedId 更新，render 重新呼叫 |
| selectItem | 設 state.selectedId 並呼叫 render |
| firstSelectableId — diff mode 有 changes | 回傳 changes[0].id |
| firstSelectableId — diff mode 無 changes | 回傳 null |
| firstSelectableId — non-diff 有 features | 回傳 features[0].id |
| firstSelectableId — non-diff 無 l1Model | 回傳 null |
| setMode("diff") — 無 diff 可用 | state.mode 不改變，render 未呼叫 |
| setMode("diff") — hasDiff=true | state.mode="diff"，render 呼叫，loadL1Graph 不呼叫 |
| setMode("diff") — hasVersionCompare 且 !hasDiff | state.mode="diff"，loadL1Graph(versionB) 呼叫 |
| setMode("baseline") — 一般 | state.mode="baseline"，render 呼叫，loadL1Graph 不呼叫 |
| setMode("baseline") — hasVersionCompare | loadL1Graph(state.versionA) 呼叫 |
| setMode("current") — hasVersionCompare | loadL1Graph(state.versionB) 呼叫 |
| setMode("baseline") — hasVersionCompare + hasDiff | loadL1Graph 不呼叫（hasDiff 短路）|
| loadProjectStatus — 成功 | state.projectStatus 設定，loadFromApi 呼叫 |
| loadProjectStatus — !ok 有 message | renderError(message) 呼叫 |
| loadProjectStatus — !ok 無 message | renderError 含 "無法取得專案狀態（<status>）" |
| loadProjectStatus — !ok body 不可解析 | renderError 含 status fallback |
| loadProjectStatus — network error | loadStaticFallback 呼叫 |
| loadFromApi — projectStatus null | 提早 return |
| loadFromApi — has_latest_report | loadReport 觸發 |
| loadFromApi — 無 latest_report | summaryText 顯示空狀態訊息 |
| loadFromApi — has_snapshots | loadSnapshots 觸發，loadL1Graph 以 versionB 呼叫 |
| loadFromApi — has_snapshots 無 version-compare | loadL1Graph(null) 呼叫 |
| loadFromApi — 無 snapshots | loadL1Graph 不呼叫 |
| loadFromApi — 無 available_data | 走「無 latest_report、無 snapshots」路徑 |
| loadReport — 404 | state.updateModel = null |
| loadReport — !ok | handleApiError 呼叫 |
| loadReport — 成功 | state.updateModel 由 buildViewModelFromReport 建構 |
| loadReport — catch | renderError 呼叫 |
| loadReport — catch 無 message | renderError 含 "network error" |
| loadSnapshots — 成功 | state.snapshots 設定，versionA = [1]、versionB = [0]，populateVersionSelectors 呼叫 |
| loadSnapshots — 少於 2 snapshots | versionA = null |
| loadSnapshots — 0 snapshots | versionA = null、versionB = null |
| loadSnapshots — missing snapshots key | 視為空陣列 |
| loadSnapshots — !ok | 靜默 return |
| loadSnapshots — catch | 靜默，不 throw |
| handleApiError — body 有 message | renderError("API 錯誤：" + message) |
| handleApiError — body 無 message | renderError 含 "HTTP " + status |
| loadStaticFallback — update json 成功 + l1 json 成功 | state.updateModel/l1GraphViewModel/l1Model 設定，initGraph + renderLegend 呼叫 |
| loadStaticFallback — update json !ok | renderError 呼叫，第二段不執行 |
| loadStaticFallback — update json catch | renderError 含 message |
| loadStaticFallback — update json catch 無 message | renderError 含 "network error" |
| loadStaticFallback — l1 json !ok | state.l1GraphViewModel 保持 null，仍呼叫 render() |
| loadStaticFallback — l1 json catch | state.l1GraphViewModel = null、l1Model = null |
| loadStaticFallback — l1 json 解析失敗 | state.l1GraphViewModel 保持 null |
| loadStaticFallback — diff_available | state.mode = "diff" |
| loadStaticFallback — 無 diff_available | state.mode = "baseline" |
| btnDiff click | setMode("diff") 觸發 |
| btnBaseline click | setMode("baseline") 觸發 |
| btnCurrent click | setMode("current") 觸發 |
| btnReanalyze click | showUpdateModal 呼叫 |
| btnModalCancel click | hideUpdateModal 呼叫 |
| btnModalSubmit click — 兩路徑空白 | showModalError 呼叫，submitUpdate 未呼叫 |
| btnModalSubmit click — 僅 oldPath 空白 | showModalError 呼叫 |
| btnModalSubmit click — 僅 newPath 空白 | showModalError 呼叫 |
| btnModalSubmit click — 兩路徑都有 | hideUpdateModal + submitUpdate 呼叫，callbacks.onComplete 回觸 loadFromApi、onError = renderError |
| btnModalSubmit — onComplete 回呼能成功觸發 loadFromApi | 模擬完成回呼，fetch /api/project 被呼叫 |
| btnGraphToggle click | openGraphDrawer 呼叫 |
| btnDrawerClose click | closeGraphDrawer 呼叫 |
| graphBackdrop click | closeGraphDrawer 呼叫 |
| btnMindmap click | switchToMindmap 呼叫 |
| btnBackL1 click | switchToL1 呼叫 |
| populateVersionSelectors — selA/selB/selectorBar 任一不存在 | 直接 return |
| populateVersionSelectors — snapshots ≤ 1 | selectorBar hidden |
| populateVersionSelectors — snapshots > 1 | selectorBar 顯示，selA/selB 各有對應 option 數量，預設值對應 versionA/versionB |
| populateVersionSelectors — selA.onchange | state.versionA 更新，state.mode = "diff"，renderTopBar + loadL1Graph 呼叫 |
| populateVersionSelectors — selA.onchange 無 versionB | loadL1Graph 以 versionA（fallback）呼叫 |
| populateVersionSelectors — selB.onchange | state.versionB 更新，loadL1Graph(versionB) 呼叫 |
| populateVersionSelectors — 多次呼叫 | 第一次的 onchange handler 被覆寫，總共只觸發一次 |
| 模組 import 時 | **不**觸發任何 fetch 或事件綁定（init() 未被呼叫）|
| init() 呼叫後 | fetch /api/project 被呼叫，所有按鈕 listener 已綁定 |
| init() 多次呼叫 | listeners 會重複綁定 — 由呼叫端（HTML）負責只呼叫一次（不在此模組防呆，避免過度設計）|

---

## TDD 步驟

1. **RED**：寫 `tests/app.test.js`，確認失敗
2. **GREEN**：建立 `js/app.js`，最小實作
3. **REFACTOR**：整理

## 驗證檢查清單

- [ ] `npm test tests/app.test.js` — 全部通過
- [ ] 此步驟 index.html 仍載入舊 `app.js`，新模組尚未接線（步驟 10 才接）
