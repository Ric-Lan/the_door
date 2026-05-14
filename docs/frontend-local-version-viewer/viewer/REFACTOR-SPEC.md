# app.js 拆分規格書

## 背景

`app.js` 現況：2654 行、60+ functions、單一全域 state、零模組邊界。
每次 AI 讀取需分段、每次修改都在整份檔案裡定位。

目標：拆成 13 個 ES module，每個檔案單一職責、可獨立讀取與修改。

---

## 技術方案：ES Modules

```html
<!-- index.html 唯一改動 -->
<script src="./lib/cytoscape.min.js"></script>  <!-- 保持不動，必須在 module 之前 -->
<script type="module" src="./js/app.js"></script>
```

`static_handler.py` 已對 `.js` 回傳 `application/javascript; charset=utf-8`，ES module 無需額外設定。
`type="module"` 腳本是 deferred，執行時 cytoscape 已載入完畢，`window.cytoscape` 可用。

目錄結構：

```
viewer/
  js/
    dom.js                  ← DOM element cache（原 els）
    state.js
    api.js
    viewmodel.js
    graph.js
    ui-topbar.js
    ui-list.js
    ui-detail.js
    ui-modal.js
    ui-notes.js
    ui-diff-explanation.js
    layers.js
    app.js                  ← 新的 thin orchestrator
  lib/
    cytoscape.min.js
  assets/
  styles.css
  index.html
  app.js                    ← 舊檔案，拆分完成後刪除
```

---

## 模組清單

### 1. `js/dom.js` — DOM Element Cache
**來源行號**：76–108  
**預估行數**：~35 行  
**依賴**：無

匯出 `els` 物件（原樣搬移）。在模組頂層執行 `getElementById`；由於 `type="module"` 是 deferred，DOM 已 ready。

```js
export const els = {
  btnDiff:          document.getElementById("btn-diff"),
  btnBaseline:      document.getElementById("btn-baseline"),
  btnCurrent:       document.getElementById("btn-current"),
  // ... 其餘 30 個 element（見原 els 物件完整清單）
};
```

其他模組直接 `import { els } from './dom.js'`，不透過 function parameter 傳遞。

---

### 2. `js/state.js` — 全域狀態
**來源行號**：18–70  
**預估行數**：~60 行  
**依賴**：無

```js
export const state = {
  updateModel: null,
  l1Model: null,
  mode: "baseline",
  selectedId: null,
  projectStatus: null,
  pollingJobId: null,
  pollingHandle: null,
  layerState: "L1",
  selectedFeatureId: null,
  selectedModuleId: null,
  l1GraphViewModel: null,
  l2GraphViewModel: null,
  l3GraphViewModel: null,
  diffGraphViewModel: null,
  cytoscapeInstance: null,
  cytoscapeAvailable: false,
  diffSortMode: "risk",
  layerExplanation: null,
  snapshots: [],
  versionA: null,
  versionB: null,
  versionDiff: null,
};
```

---

### 3. `js/api.js` — 所有 fetch 呼叫
**來源行號**：143–528（分散）  
**預估行數**：~235 行  
**依賴**：`state.js`（僅讀取 `state.pollingJobId`）

`API_BASE` 定義在此模組頂部為私有常數：

```js
const API_BASE = "";
```

**規則**：每個 function 只做 fetch + return data，不碰 DOM、不改 state。

```js
export async function fetchProjectStatus()
export async function fetchLatestReport()
export async function fetchSnapshots()
export async function postUpdate(oldPath, newPath, lang)
export async function fetchJobStatus(jobId)
export async function fetchL1Graph(versionId)
export async function fetchDiff(baselineId, currentId)
export async function fetchL2Graph(featureId)
export async function fetchStructure()
export async function fetchLayerExplanation(featureId, layer)
export async function postGenerateL2(featureId)
export async function postGenerateLayerExplanation(featureId, layer)
export async function fetchNotes(params)
export async function postNote(payload)
export async function fetchDiffExplanation(featureId, params)
export async function postGenerateDiffExplanation(featureId, payload)
export async function fetchStaticUpdateViewModel()   // static fallback
export async function fetchStaticL1ViewModel()       // static fallback
```

---

### 4. `js/viewmodel.js` — 資料轉換
**來源行號**：339–418  
**預估行數**：~100 行  
**依賴**：無（純函式）

```js
export function buildViewModelFromReport(report)
export function buildL1ViewModelFromStatic(data)
export function snapshotLabel(snapshot)
```

---

### 5. `js/graph.js` — Cytoscape / Mermaid
**來源行號**：1030–1432  
**預估行數**：~420 行  
**依賴**：`state.js`

`window.cytoscape` 直接讀取（由 `<script>` tag 提供），不 import。

```js
export function initGraph(container, viewModel, options)
export function buildCytoscapeElements(viewModel)
export function buildCytoscapeStyle()
export function bindCytoscapeEvents(cy, callbacks)  // callbacks: { onNodeTap }
export function syncFeatureListSelection(cy, featureId)
export function renderMermaidFallback(container, viewModel)
export function buildMermaidText(viewModel)
export function renderLegend(container, items)
export function initZoomControls(cy)
export function hideZoomControls()
export function openGraphDrawer()
export function closeGraphDrawer()
```

`bindCytoscapeEvents` 透過 callback 通知外部，不直接呼叫其他模組的 render 函式。

---

### 6. `js/ui-topbar.js` — 頂部列渲染
**來源行號**：612–695  
**預估行數**：~90 行  
**依賴**：`state.js`, `dom.js`

```js
export function renderTopBar()
export function updateLogoMark()
```

直接從 `dom.js` import `els`，無需 parameter。

---

### 7. `js/ui-list.js` — 變更清單 / 功能卡片
**來源行號**：698–827  
**預估行數**：~140 行  
**依賴**：`state.js`, `dom.js`

```js
export function renderChangeList(callbacks)   // callbacks: { onSelect }
export function changeListButton(item, isActive, callbacks)
export function featureCard(feature, isActive, callbacks)
export function changeSymbol(changeType)
```

---

### 8. `js/ui-detail.js` — 詳情面板
**來源行號**：830–1029, 1984–2193  
**預估行數**：~360 行  
**依賴**：`state.js`, `dom.js`

```js
export function renderDetailPanel()
export function renderDiffDetailPanel()
export function renderSingleVersionDetailPanel()
export function renderDetailPanelL1(container, feature)
export function renderDetailPanelL2(container, viewModel)
export function renderDetailPanelL3(container, viewModel)
export function renderDetailPanelDiff(container)
export function renderEmpty(container, message)
export function renderError(container, message)
export function toggleDiffSort()
export function applyDiffSort(nodes)
```

---

### 9. `js/ui-modal.js` — Update Modal + Pipeline 進度
**來源行號**：420–553  
**預估行數**：~140 行  
**依賴**：`state.js`, `api.js`, `dom.js`

```js
export function showUpdateModal()
export function hideUpdateModal()
export function showModalError(message)
export function renderPipelineProgress(job)
export function submitUpdate(callbacks)    // callbacks: { onComplete, onError }
export function startPolling(jobId, callbacks)
export function stopPolling()
export function pollJobStatus(callbacks)
```

---

### 10. `js/ui-notes.js` — 使用者備註（RI-3）
**來源行號**：2337–2479  
**預估行數**：~145 行  
**依賴**：`state.js`, `api.js`

```js
export function appendUserNotesSection(container, mode, versionA, versionB, featureId)
```

完全自包含，不依賴其他 UI 模組。

---

### 11. `js/ui-diff-explanation.js` — 差異推論（RI-5）
**來源行號**：2481–2654  
**預估行數**：~175 行  
**依賴**：`state.js`, `api.js`

```js
export function appendDiffExplanationSection(container, featureId)
```

完全自包含。

---

### 12. `js/layers.js` — L1/L2/L3 層級導航
**來源行號**：1434–1812  
**預估行數**：~390 行  
**依賴**：`state.js`, `api.js`, `graph.js`, `ui-topbar.js`, `ui-detail.js`, `ui-list.js`, `dom.js`

```js
export async function loadL1Graph(versionId)
export async function loadDiffOverlay(baselineId, currentId)
export async function switchToL2(featureId)
export async function switchToL3(featureId, moduleId)
export function switchToL1()
export function switchToL2FromL3()
export async function loadLayerExplanation(featureId, layer)
export async function generateL2(featureId, callbacks)
export async function generateLayerExplanation(featureId, layer, callbacks)
export function renderBreadcrumb(container)
export async function pollUntilComplete(jobId, callbacks)
export function renderFeatureList(callbacks)
export function renderL2NotAnalyzed(container, featureId)
```

`loadL1Graph` 和 `loadDiffOverlay` 完成後直接呼叫 `renderTopBar()`（從 `ui-topbar.js` import，`els` 由 `dom.js` 提供，無循環依賴）。

---

### 13. `js/app.js` — Thin Orchestrator（主進入點）
**來源行號**：110–188（boot/event binding/loadProjectStatus/loadFromApi）  
**預估行數**：~160 行  
**依賴**：所有上述模組

職責：事件綁定、頂層 `render()`、`setMode()`、`loadProjectStatus()`、`loadFromApi()`。
不再定義或匯出 `els`（已移至 `dom.js`）。

```js
import { state } from './state.js';
import { els } from './dom.js';
import * as Api from './api.js';
import { buildViewModelFromReport, snapshotLabel } from './viewmodel.js';
import { renderTopBar, updateLogoMark } from './ui-topbar.js';
import { renderChangeList } from './ui-list.js';
import { renderDetailPanel, renderError } from './ui-detail.js';
import { showUpdateModal, hideUpdateModal, submitUpdate, stopPolling } from './ui-modal.js';
import { loadFromApi, switchToL1, switchToMindmap } from './layers.js';
import { openGraphDrawer, closeGraphDrawer } from './graph.js';

export function render() {
  updateLogoMark();
  renderTopBar();
  renderChangeList({ onSelect: selectItem });
  renderDetailPanel();
}

export function setMode(mode) { ... }
function selectItem(id) { ... }
async function loadProjectStatus() { ... }
async function loadFromApi() { ... }

els.btnDiff.addEventListener("click", () => setMode("diff"));
// ... 其餘 event binding
loadProjectStatus();
```

---

## 模組依賴圖

```
dom.js      (無依賴 — DOM element cache)
state.js    (無依賴 — 可變狀態)
                    ↑
api.js      (state)
viewmodel.js(純函式)
graph.js    (state)
ui-topbar.js(state, dom)
ui-list.js  (state, dom)
ui-detail.js(state, dom)
ui-modal.js (state, api, dom)
ui-notes.js (state, api)
ui-diff-explanation.js (state, api)
layers.js   (state, api, graph, ui-topbar, ui-detail, ui-list, dom)
app.js      (全部)
```

無循環依賴。`dom.js` 和 `state.js` 是兩個獨立根節點。

---

## 各模組預估行數

| 模組 | 預估行數 |
|------|---------|
| dom.js | 35 |
| state.js | 60 |
| api.js | 235 |
| viewmodel.js | 100 |
| graph.js | 420 |
| ui-topbar.js | 90 |
| ui-list.js | 140 |
| ui-detail.js | 360 |
| ui-modal.js | 140 |
| ui-notes.js | 145 |
| ui-diff-explanation.js | 175 |
| layers.js | 390 |
| app.js (new) | 160 |
| **合計** | **~2450** |

最大單檔 420 行（graph.js），平均 188 行。

---

## 實作順序

依賴方向由下往上，每步啟動伺服器驗證無 regression：

1. `dom.js` + `state.js`（零依賴，建基礎）
2. `api.js` + `viewmodel.js`（純資料層）
3. `graph.js`（複雜但自包含）
4. `ui-topbar.js` + `ui-list.js`（簡單 UI）
5. `ui-detail.js`（最大 UI 模組）
6. `ui-modal.js`（含 polling 邏輯）
7. `ui-notes.js` + `ui-diff-explanation.js`（RI 功能，自包含）
8. `layers.js`（整合 api + graph + ui）
9. `app.js` 新版（接線）
10. `index.html`：移除 `<script src="./app.js">`，加 `<script type="module" src="./js/app.js">`；確認 cytoscape script tag 在 module tag **之前**
11. 刪除舊 `viewer/app.js`

---

## 注意事項

### `els` 的取用方式
所有需要 DOM element 的模組直接 `import { els } from './dom.js'`，**不透過 function parameter 傳遞**。這樣 function signature 保持乾淨，且 `dom.js` 是無依賴的根節點，不會產生循環。

### Cytoscape 全域 `window.cytoscape`
`graph.js` 直接讀 `window.cytoscape`，不 import。`<script src="./lib/cytoscape.min.js">` 為同步 script，必須放在 `<script type="module">` 之前，執行時序由 HTML 順序保證。

### 舊 `app.js` 的刪除時機
Step 10 完成、伺服器驗證通過後才刪。在此之前兩份檔案同時存在，但 index.html 只載入其中一個。

### `loadStaticFallback` 整合
fetch 進 `api.js`（`fetchStaticUpdateViewModel` / `fetchStaticL1ViewModel`），ViewModel 建構進 `viewmodel.js`，流程協調留在 `app.js`。

### `switchToMindmap`
目前在 app.js 末段（行 2325–2335），搬移至 `layers.js` 或獨立 `mindmap.js`。建議放 `layers.js` 因為它讀取 `state.l1GraphViewModel`。

---

## 不在本次範圍

- `mindmap-popup.html` / `mindmap-preview.html`：獨立頁面，不影響主 viewer
- `styles.css`：不動
- Python 後端：不動
