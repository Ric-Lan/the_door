# 步驟 8 — layers.js

## 概覽

| 模組 | 來源行號（app.js） | 預估行數 | 依賴 |
|---|---|---|---|
| `js/layers.js` | 1434–1812, 2268–2335 | ~390 | `state.js`, `api.js`, `graph.js`, `ui-topbar.js`, `ui-detail.js`, `ui-list.js`, `dom.js` |

---

## 匯出介面

```js
export async function loadL1Graph(versionId)
export async function loadDiffOverlay(baselineId, currentId)
export async function switchToL2(featureId)
export async function switchToL3(moduleId)
export function switchToL1()
export function switchToL2FromL3()
export async function loadLayerExplanation(featureId, layer)
export async function generateL2(featureId)
export async function generateLayerExplanation(featureId, layer)
export function renderBreadcrumb()
export async function pollUntilComplete(jobId, onComplete)
export function renderFeatureList(viewModel, layerState)
export function renderL2NotAnalyzed(featureId)
export function switchToMindmap()
```

---

## 各函式規格

### loadL1Graph(versionId)

1. 呼叫 `api.fetchL1Graph(versionId)`
2. 設定 `state.l1GraphViewModel`，`state.layerState = "L1"`
3. 從 graphViewModel.nodes 建構 `state.l1Model`（`{ features: [...], stats: { feature_count } }`）
4. 呼叫 `initGraph("graph-container", state.l1GraphViewModel)`
5. 呼叫 `renderLegend()`、`renderBreadcrumb()`
6. 若無 updateModel.diff_available → `state.selectedId` = 第一個 feature.id
7. 呼叫 `renderTopBar()`、`renderChangeList()`、`renderDetailPanel()`
8. 若 `state.versionA && state.versionB && versionA !== versionB` → `loadDiffOverlay(versionA, versionB)`
9. fetch 失敗 → `renderError(...)`，不改 state

### loadDiffOverlay(baselineId, currentId)

- `baselineId === currentId` 或任一為 null → 直接 return
- 呼叫 `api.fetchDiff(baselineId, currentId)`
- `state.versionDiff` = data
- 若 `state.cytoscapeInstance` → 對各節點套用 change_type
- 更新 `els.summaryText`（有變更 → 統計文字；無變更 → "兩版本功能完全相同。"）
- 呼叫 `renderTopBar()`、`renderChangeList()`

### switchToL2(featureId)

- `state.selectedFeatureId` = featureId，`state.layerState = "L2"`
- 非同步觸發 `loadLayerExplanation(featureId, "l2")`（fire & forget）
- `api.fetchL2Graph(featureId)`
  - 404 → `renderL2NotAnalyzed(featureId)`
  - 成功 → `state.l2GraphViewModel` = data，`initGraph(...)`，`renderFeatureList(data, "L2")`

### switchToL3(moduleId)

**參數：一個 `moduleId`（不是 featureId + moduleId）**

- 從 `state.l2GraphViewModel.nodes` 找 `moduleId`，取 `source_nodes`
- source_nodes 為空 → `initGraph("graph-container", { nodes: [], edges: [] })`，`renderFeatureList({ nodes: [], edges: [] }, "L3")`
- `api.fetchStructure()` 取得 structureJson
  - 404 → `#graph-container` 清空，插入說明文字（"結構資料不存在，請重新執行 the-door extract。"）
  - 成功 → 過濾 structureJson.nodes/edges（僅保留 source_nodes 中的節點與兩端均在集合內的邊），建構 l3ViewModel，`state.l3GraphViewModel` = l3ViewModel，`initGraph(..., l3ViewModel)`，`renderFeatureList(l3ViewModel, "L3")`

### switchToL1()

- `state.layerState = "L1"`
- **`state.selectedFeatureId = null`**、**`state.selectedModuleId = null`**（清除 L2/L3 選取）
- `updateLogoMark()`、`renderBreadcrumb()`
- 若 `state.l1GraphViewModel` 存在 → `initGraph(..., state.l1GraphViewModel)`，`renderFeatureList(state.l1GraphViewModel, "L1")`
- 否則 → `loadL1Graph()`

### switchToL2FromL3()

- `state.layerState = "L2"`，`state.selectedModuleId = null`
- `updateLogoMark()`、`renderBreadcrumb()`
- 若 `state.l2GraphViewModel` 存在 → `initGraph(...)`，`renderFeatureList(data, "L2")`
- 否則且有 `selectedFeatureId` → `switchToL2(state.selectedFeatureId)`

### loadLayerExplanation(featureId, layer)

- GET `/api/layer-explanation/<featureId>/<layer>`
- `layerExplanationEl` = `document.getElementById("layer-explanation")`（若無則 return）
- 404 → `state.layerExplanation = null`，清空 layerExplanationEl
- ok → `state.layerExplanation` = data.explanation，若有值則插入 `<p class="layer-explanation-text">`
- 任何 catch → **靜默忽略**（non-fatal）

### generateL2(featureId)

**無 callbacks 參數**

- POST `/api/l2/<featureId>/generate`
- !ok → `renderError(...)`，return
- 成功 → 取 `job_id`，呼叫 `await pollUntilComplete(job_id, async () => { await switchToL2(featureId); })`
- catch → `renderError(...)`

### generateLayerExplanation(featureId, layer)

**無 callbacks 參數**

- POST `/api/layer-explanation/<featureId>/<layer>/generate`
- !ok → `renderError(...)`，return
- 成功 → `await pollUntilComplete(job_id, async () => { await loadLayerExplanation(featureId, layer); })`
- catch → `renderError(...)`

### renderBreadcrumb()

**無參數**，讀 `document.getElementById("breadcrumb")`。

| layerState | 麵包屑 parts 數 | 結構 |
|---|---|---|
| L1 | 1 | `<span>L1</span>`（current） |
| L2 | 3 | `[L1 btn] > featureLabel > [L2 span]` |
| L3 | 5 | `[L1 btn] > [featureLabel btn] > [L2 btn] > moduleLabel > [L3 span]` |

- parts 間以 `<span class="breadcrumb-sep"> > </span>` 分隔
- 有 action 的項目回傳 `<button class="breadcrumb-link">`，無 action 的回傳 `<span class="breadcrumb-current">`
- `els.btnBackL1.hidden = (state.layerState === "L1")`

### pollUntilComplete(jobId, onComplete)

**`onComplete` 是 async function，不是 callbacks 物件。**

- setInterval 1500ms，最多 60 次（maxAttempts）
- 呼叫 `api.fetchJobStatus(jobId)`
- status = "completed" → clearInterval，`await onComplete()`
- status = "failed" → clearInterval，`renderError("任務失敗：" + job.error_message)`
- fetch !ok → clearInterval，return
- 超過 maxAttempts → clearInterval，`renderError("任務逾時，請稍後重試。")`

### renderFeatureList(viewModel, layerState)

渲染 `#feature-list`；按 layerState 顯示不同欄位：

| layerState | 卡片次要文字 | 徽章 |
|---|---|---|
| L1 | node.description | confidence badge |
| L2 | node.confidence_reason | confidence badge |
| L3 | node.file | type badge |
| DIFF | node.change_type | change-badge（changeSymbol） |

點擊卡片時：
- Cytoscape 節點被程式化選取（`cytoscapeInstance.getElementById(node.id).select()`）
- 呼叫對應 `renderDetailPanel*`：
  - L1 → `state.selectedFeatureId = node.id`；`renderDetailPanelL1(node, { onEnterL2: switchToL2 })`
  - L2 → `state.selectedModuleId = node.id`；`renderDetailPanelL2(node, { onEnterL3: switchToL3, onGenerateLayerExplanation: generateLayerExplanation })`
  - L3 → `renderDetailPanelL3(node)`
  - DIFF → `renderDetailPanelDiff(node)`

### renderL2NotAnalyzed(featureId)

- `#feature-list`：清空，插入 `.not-analyzed-state`（含標題 + "生成 L2 分析" 按鈕（click → `generateL2(featureId)`）+ CLI 提示文字）
- `#graph-container`：清空，插入 `.not-analyzed-state`（僅含標題，**無**按鈕）

### switchToMindmap()

- 將 `{ project, nodes, diffNodes, diffAvailable }` 寫入 `sessionStorage["mindmap-data"]`（JSON 序列化）
- `window.open("./mindmap-popup.html", "mindmap", "width=960,height=720,...")`

---

## 測試規格

### tests/layers.test.js

| 測試案例 | 驗證 |
|---|---|
| loadL1Graph — fetch 成功 | state.l1GraphViewModel/l1Model 被設定，layerState="L1" |
| loadL1Graph — fetch 失敗 | renderError 被呼叫，state 不改變 |
| loadL1Graph — 有 versionA & versionB | loadDiffOverlay 被呼叫 |
| loadDiffOverlay(同一 id) | fetch 未呼叫，直接 return |
| loadDiffOverlay — 成功 | state.versionDiff 被設定，summaryText 更新 |
| loadDiffOverlay — 有 cytoscapeInstance | 節點 change_type 被更新 |
| switchToL2 — fetch 404 | renderL2NotAnalyzed 被呼叫 |
| switchToL2 — 成功 | state.l2GraphViewModel 被設定，layerState="L2" |
| switchToL3 — sourceNodes 為空 | initGraph 以空 viewModel 呼叫 |
| switchToL3 — 成功 | l3ViewModel 節點從 structureJson 過濾正確 |
| switchToL3 — structure 404 | #graph-container 顯示說明文字 |
| switchToL1 | layerState="L1"，selectedFeatureId=null，selectedModuleId=null，initGraph 以 l1GraphViewModel 呼叫 |
| renderBreadcrumb — L1 | 1 個 part（span.breadcrumb-current），btnBackL1 hidden=true |
| renderBreadcrumb — L2 | 3 個 parts，含 L1 breadcrumb-link |
| renderBreadcrumb — L3 | 5 個 parts，含 L1/L2 breadcrumb-link |
| renderFeatureList — L1 節點點擊 | renderDetailPanelL1 以 node + callbacks.onEnterL2 呼叫 |
| renderFeatureList — L2 節點點擊 | renderDetailPanelL2 以 node + callbacks 呼叫 |
| renderL2NotAnalyzed | feature-list 含 .not-analyzed-state + 按鈕；graph-container 含標題無按鈕 |
| pollUntilComplete — completed | onComplete async function 被 await 呼叫 |
| pollUntilComplete — failed | renderError 被呼叫 |
| pollUntilComplete — 超過 maxAttempts | renderError("任務逾時") |
| switchToMindmap | sessionStorage["mindmap-data"] 被設定 |
| loadLayerExplanation — 成功 | state.layerExplanation 被設定，layerExplanationEl 有 p 元素 |
| loadLayerExplanation — 404 | state.layerExplanation = null，layerExplanationEl 清空 |
| loadLayerExplanation — catch | 靜默，不 throw |

**注意**：需 mock `api.*`、`initGraph`、`renderLegend`、`renderTopBar`、`renderChangeList`、`renderDetailPanel`、`renderDetailPanelL1`、`renderDetailPanelL2`、`renderDetailPanelL3`、`renderDetailPanelDiff` 等依賴。

---

## TDD 步驟

1. **RED**：寫 `tests/layers.test.js`，確認失敗
2. **GREEN**：建立 `js/layers.js`，最小實作
3. **REFACTOR**：整理

## 驗證檢查清單

- [ ] `npm test tests/layers.test.js` — 全部通過
- [ ] 啟動伺服器，L1→L2→L3 切換正常，麵包屑顯示正確
