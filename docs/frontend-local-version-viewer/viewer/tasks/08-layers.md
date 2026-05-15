# 步驟 8 — layers.js

## 概覽

| 模組 | 來源行號（app.js） | 預估行數 | 依賴 |
|---|---|---|---|
| `js/layers.js` | 1434–1812, 2268–2335 | ~390 | `state.js`, `api.js`（僅 `API_BASE`）, `graph.js`, `ui-topbar.js`, `ui-detail.js`, `ui-list.js`, `dom.js` |

**API 呼叫策略：** layers.js 直接使用 `fetch`（不走 api.js 既有 wrapper），因為核心邏輯需要區分 `res.status === 404`、`!res.ok` 與 catch 三條 UX 分流路徑，現有 api.js wrapper 已丟棄 status/ok 資訊。`API_BASE` 從 api.js 匯入以避免 base URL 重複。其他完整流程函式（如 `renderTopBar`、`renderChangeList`、`renderError`、`renderLegend`、`updateLogoMark`、`initGraph`、`changeSymbol`、`renderDetailPanel*`）從各對應模組 import。

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

### loadL1Graph(versionId = null)

1. 組 URL：有 versionId → `${API_BASE}/api/l1?version_id=${encodeURIComponent(versionId)}`；否則 `${API_BASE}/api/l1`
2. `fetch(url, { cache: "no-store" })`
3. `!res.ok` → 嘗試 `res.json().catch(() => null)`，`renderError("無法載入 L1 圖形：" + (body?.error?.message || res.status))`，return
4. 成功 → `state.l1GraphViewModel = await res.json()`、`state.layerState = "L1"`
5. 從 graphViewModel.nodes 建構 `state.l1Model = { features: [{id, label, confidence, description, trigger_description, source: "L1Output.features"}, ...], stats: { feature_count } }`
6. 呼叫 `initGraph("graph-container", state.l1GraphViewModel)`、`renderLegend()`、`renderBreadcrumb()`
7. 若**無** `state.updateModel?.diff_available` → `state.selectedId = state.l1Model.features[0]?.id ?? null`
8. 呼叫 `renderTopBar()`、`renderChangeList()`、`renderDetailPanel()`
9. 若 `state.versionA && state.versionB && state.versionA !== state.versionB` → `await loadDiffOverlay(state.versionA, state.versionB)`
10. catch → `renderError("載入 L1 圖形失敗：" + (err.message || "network error"))`

### loadDiffOverlay(baselineId, currentId)

- `!baselineId || !currentId || baselineId === currentId` → 直接 return
- `fetch(\`${API_BASE}/api/diff?baseline=${encodeURIComponent(baselineId)}&current=${encodeURIComponent(currentId)}\`, { cache: "no-store" })`
- `!res.ok` → 靜默 return（不 throw、不 renderError；與 app.js 一致）
- 成功 → `data = await res.json()`，`state.versionDiff = data`
- 若 `state.cytoscapeInstance` → 對 `cy.nodes()` 中每個節點，從 `data.node_states[node.id()]` 取得 diffState：非 `"unchanged"` 時 `node.data("change_type", diffState)`，否則 `node.removeData("change_type")`
- 更新 `els.summaryText`：取 `s = data.summary || {}`、`total = s.total_changed ?? 0`：
  - total > 0 → `版本比較：${s.added ?? 0} 新增 / ${s.removed ?? 0} 移除 / ${(s.attribute_changed ?? 0) + (s.dependency_changed ?? 0)} 修改`
  - total = 0 → `版本比較：兩版本功能完全相同。`
- 呼叫 `renderTopBar()`、`renderChangeList()`
- catch → `console.warn("Diff overlay failed:", e)`（靜默，與 app.js 一致）

### switchToL2(featureId)

- `state.selectedFeatureId = featureId`，`state.layerState = "L2"`
- 呼叫 `updateLogoMark()`、`renderBreadcrumb()`
- **fire & forget** 觸發 `loadLayerExplanation(featureId, "l2")`（**不** await）
- `fetch(\`${API_BASE}/api/l2/${encodeURIComponent(featureId)}\`, { cache: "no-store" })`
  - `res.status === 404` → `renderL2NotAnalyzed(featureId)`，return
  - `!res.ok` → `renderError("無法載入 L2 圖形：" + (body?.error?.message || res.status))`，return
  - 成功 → `state.l2GraphViewModel = await res.json()`，`initGraph("graph-container", state.l2GraphViewModel)`，`renderFeatureList(state.l2GraphViewModel, state.layerState)`
- catch → `renderError("載入 L2 圖形失敗：" + (err.message || "network error"))`

### switchToL3(moduleId)

**參數：一個 `moduleId`（不是 featureId + moduleId）**

- `state.selectedModuleId = moduleId`，`state.layerState = "L3"`
- 呼叫 `updateLogoMark()`、`renderBreadcrumb()`
- 從 `state.l2GraphViewModel?.nodes || []` 找 `n.id === moduleId`，取 `module?.source_nodes || []`
- `sourceNodeIds.length === 0` → `initGraph("graph-container", { nodes: [], edges: [] })`、`renderFeatureList({ nodes: [], edges: [] }, "L3")`，return
- `fetch(\`${API_BASE}/api/structure\`, { cache: "no-store" })`
  - `res.status === 404` → 取 `container = document.getElementById("graph-container")`，存在則清空 `textContent`，append `<div class="empty-state">結構資料不存在，請重新執行 the-door extract。</div>`，return
  - `!res.ok` → `renderError("無法載入結構資料：" + (body?.error?.message || res.status))`，return
  - 成功 → `structureJson = await res.json()`，`sourceSet = new Set(sourceNodeIds)`
    - `l3Nodes = structureJson.nodes.filter(n => sourceSet.has(n.node_id)).map(n => ({ id: n.node_id, label: n.name, type: n.type, file: n.file }))`
    - `l3Edges = structureJson.edges.filter(e => sourceSet.has(e.from_node) && sourceSet.has(e.to_node)).map(e => ({ source: e.from_node, target: e.to_node }))`
    - `state.l3GraphViewModel = { nodes: l3Nodes, edges: l3Edges }`
    - `initGraph("graph-container", state.l3GraphViewModel)`、`renderFeatureList(state.l3GraphViewModel, state.layerState)`
- catch → `renderError("載入 L3 圖形失敗：" + (err.message || "network error"))`

### switchToL1()

- `state.layerState = "L1"`
- **`state.selectedFeatureId = null`**、**`state.selectedModuleId = null`**（清除 L2/L3 選取）
- `updateLogoMark()`、`renderBreadcrumb()`
- 若 `state.l1GraphViewModel` 存在：
  - `initGraph(..., state.l1GraphViewModel)`、`renderFeatureList(state.l1GraphViewModel, "L1")`
  - 若 `state.cytoscapeInstance && state.selectedId` → 取 `getElementById(state.selectedId)`，存在則 `.select()`（還原 L1 卡片選取狀態）
- 否則 → `loadL1Graph()`

### switchToL2FromL3()

- `state.layerState = "L2"`，`state.selectedModuleId = null`
- `updateLogoMark()`、`renderBreadcrumb()`
- 若 `state.l2GraphViewModel` 存在 → `initGraph(...)`、`renderFeatureList(data, "L2")`（**不**還原 selectedModuleId，因為已清為 null）
- 否則且有 `selectedFeatureId` → `switchToL2(state.selectedFeatureId)`

### loadLayerExplanation(featureId, layer)

**靜默 fetch — 失敗不顯示錯誤訊息（non-fatal）**

- `fetch(\`${API_BASE}/api/layer-explanation/${encodeURIComponent(featureId)}/${layer}\`, { cache: "no-store" })`
- `layerExplanationEl = document.getElementById("layer-explanation")`，無則 return
- `res.status === 404` → `state.layerExplanation = null`、`layerExplanationEl.textContent = ""`，return
- `!res.ok` → return（不清 state、不寫 DOM）
- 成功 → `data = await res.json()`，`state.layerExplanation = data.explanation || null`
  - 若有值 → 清空 layerExplanationEl，append `<p class="layer-explanation-text">{state.layerExplanation}</p>`
- 任何 catch → **靜默忽略**（non-fatal）

### generateL2(featureId)

**無 callbacks 參數**

- `fetch(\`${API_BASE}/api/l2/${encodeURIComponent(featureId)}/generate\`, { method: "POST" })`
- `!res.ok` → `renderError("L2 生成失敗：" + (body?.error?.message || res.status))`，return
- 成功 → `{ job_id } = await res.json()`，`await pollUntilComplete(job_id, async () => { await switchToL2(featureId); })`
- catch → `renderError("L2 生成請求失敗：" + (err.message || "network error"))`

### generateLayerExplanation(featureId, layer)

**無 callbacks 參數**

- `fetch(\`${API_BASE}/api/layer-explanation/${encodeURIComponent(featureId)}/${layer}/generate\`, { method: "POST" })`
- `!res.ok` → `renderError("說明生成失敗：" + (body?.error?.message || res.status))`，return
- 成功 → `{ job_id } = await res.json()`，`await pollUntilComplete(job_id, async () => { await loadLayerExplanation(featureId, layer); })`
- catch → `renderError("說明生成請求失敗：" + (err.message || "network error"))`

### 內部 helper（不 export）

```js
function _getFeatureLabel(featureId) {
  if (!featureId) return "（未知功能）";
  const node = (state.l1GraphViewModel?.nodes || []).find(n => n.id === featureId);
  return node?.label || featureId;
}

function _getModuleLabel(moduleId) {
  if (!moduleId) return "（未知模組）";
  const node = (state.l2GraphViewModel?.nodes || []).find(n => n.id === moduleId);
  return node?.label || moduleId;
}
```

被 `renderBreadcrumb`（L2、L3）與 `renderL2NotAnalyzed` 使用。不 export，透過呼叫端間接驗證覆蓋率。

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

回傳 `Promise`：

- `maxAttempts = 60`，attempts 計數，setInterval 1500ms：
  - 每次先 `attempts++`；若 `attempts > maxAttempts` → clearInterval、`renderError("任務逾時，請稍後重試。")`、resolve、return
  - `fetch(\`${API_BASE}/api/update/status/${jobId}\`, { cache: "no-store" })`
    - `!res.ok` → clearInterval、resolve、return
    - `job = await res.json()`
      - `status === "completed"` → clearInterval、`await onComplete()`、resolve
      - `status === "failed"` → clearInterval、`renderError("任務失敗：" + (job.error_message || "未知錯誤"))`、resolve
      - 其他 status → 繼續 polling
    - catch → clearInterval、resolve

### renderFeatureList(viewModel, layerState)

渲染 `#feature-list`：

1. **取得 `#feature-list` 元素**，無則 return；清空 `list.textContent`
2. `const nodes = viewModel?.nodes || []`
3. **空集合處理**：`nodes.length === 0` → 插入 `<div class="empty-state">此層級沒有節點。</div>`，return
4. **逐節點建構卡片**：每個 node 建立 `<button class="feature-card">`，當 `node.id === state.selectedId` 時加 `active` class，並設 `btn.dataset.nodeId = node.id`

卡片三段結構：
- **Label**：`<span class="feature-card-label">` 顯示 `node.label || node.id`
- **Desc**：`<span class="feature-card-desc">`，按 layerState 顯示不同欄位：

| layerState | 次要文字 |
|---|---|
| L1 | `node.description` |
| L2 | `node.confidence_reason` |
| L3 | `node.file` |
| DIFF | `node.change_type` |

- **Meta**：`<div class="feature-card-meta">`，按 layerState 加入徽章：

| layerState | 徽章 / 標籤 |
|---|---|
| L1 | confidence badge（`confidence-badge confidence-badge-<lowercase confidence>`）+ **若 `state.updateModel?.diff_available`** 顯示 diff-tag（`diff-tag diff-tag-<change_type>`，內容查 `state.updateModel.changes.find(c => c.id === node.id)`，透過 `DIFF_LABELS` 對映文字：`added → "+ 新增"`、`removed → "- 移除"`、`attribute_changed → "~ 屬性變更"`、`dependency_changed → "≠ 依賴變更"`，未知值原樣顯示） |
| L2 | confidence badge |
| L3 | type badge（`confidence-badge`，文字為 `node.type`） |
| DIFF | 在卡片上加 `change-<change_type>` class；徽章 `change-badge change-<change_type>`，文字為 `changeSymbol(node.change_type) + " " + change_type` |

**點擊卡片時**（addEventListener 'click'）：
1. **Cytoscape 程式化選取**（若 `state.cytoscapeInstance` 存在）：
   - `state.cytoscapeInstance.elements().unselect()`
   - 取 `state.cytoscapeInstance.getElementById(node.id)`，存在則 `.select()`，並 `state.cytoscapeInstance.animate({ fit: { eles: cyNode, padding: 50 } })`
2. **呼叫對應 renderDetailPanel\***：
   - L1 → `state.selectedFeatureId = node.id`；`renderDetailPanelL1(node, { onEnterL2: switchToL2 })`
   - L2 → `state.selectedModuleId = node.id`；`renderDetailPanelL2(node, { onEnterL3: switchToL3, onGenerateLayerExplanation: generateLayerExplanation })`
   - L3 → `renderDetailPanelL3(node)`
   - DIFF → `renderDetailPanelDiff(node)`
3. **同步 active class**：移除 `list` 內所有 `.feature-card` 的 `active`，當前 `btn` 加 `active`

**依賴**：`changeSymbol` 從 `ui-list.js` import；`renderDetailPanelL1` / `L2` / `L3` / `Diff` 從 `ui-detail.js` import；`state` 從 `state.js`。

### renderL2NotAnalyzed(featureId)

- 取 `featureLabel = _getFeatureLabel(featureId)`
- 內部工廠 `makeNotAnalyzedBlock(withButton)`：
  - 建立 `<div class="not-analyzed-state">`
  - 加標題 `<p class="not-analyzed-title">「<featureLabel>」的 L2 層尚未分析</p>`
  - 若 `withButton`：
    - 加 `<button class="action-button">生成 L2 分析</button>`，click → 先 `btn.disabled = true`、`btn.textContent = "生成中…"`，再呼叫 `generateL2(featureId)`
    - 加 `<p class="not-analyzed-hint">或使用 CLI：</p>` + `<code class="not-analyzed-cmd">the-door analyze "<專案路徑>"</code>`
- `#feature-list`：清空，append `makeNotAnalyzedBlock(true)`
- `#graph-container`：清空，append `makeNotAnalyzedBlock(false)`（**無**按鈕、**無** CLI 提示）

### switchToMindmap()

- 將 `{ project, nodes, diffNodes, diffAvailable }` 寫入 `sessionStorage["mindmap-data"]`（JSON 序列化）
- `window.open("./mindmap-popup.html", "mindmap", "width=960,height=720,...")`

---

## 測試規格

### tests/layers.test.js

| 測試案例 | 驗證 |
|---|---|
| loadL1Graph — fetch 成功 | state.l1GraphViewModel/l1Model 被設定，layerState="L1" |
| loadL1Graph — !res.ok | renderError 被呼叫，state 不改變 |
| loadL1Graph — catch（網路錯誤） | renderError 被呼叫 |
| loadL1Graph — 已有 updateModel.diff_available | selectedId 不被改寫 |
| loadL1Graph — 無 updateModel.diff_available | selectedId = features[0].id |
| loadL1Graph — 有 versionA & versionB | loadDiffOverlay 被呼叫 |
| loadL1Graph — versionA === versionB | loadDiffOverlay 不被呼叫 |
| loadDiffOverlay(同一 id) | fetch 未呼叫，直接 return |
| loadDiffOverlay(任一 null) | 直接 return |
| loadDiffOverlay — 成功（有變更） | state.versionDiff 被設定，summaryText = "版本比較：x 新增 / y 移除 / z 修改" |
| loadDiffOverlay — 成功（total_changed=0） | summaryText = "版本比較：兩版本功能完全相同。" |
| loadDiffOverlay — 有 cytoscapeInstance | 節點 change_type 被更新（unchanged 移除、其他套用） |
| loadDiffOverlay — !res.ok | 靜默 return，state.versionDiff 不變 |
| switchToL2 — fetch 404 | renderL2NotAnalyzed 被呼叫，loadLayerExplanation 仍被觸發 |
| switchToL2 — 成功 | state.l2GraphViewModel 被設定，layerState="L2"，updateLogoMark + renderBreadcrumb 被呼叫 |
| switchToL2 — !res.ok（非 404） | renderError 被呼叫 |
| switchToL2 — catch | renderError 被呼叫 |
| switchToL3 — sourceNodes 為空 | initGraph 以空 viewModel 呼叫，updateLogoMark + renderBreadcrumb 仍呼叫 |
| switchToL3 — 成功 | l3ViewModel 節點從 structureJson 過濾正確，僅保留兩端均在 sourceSet 內的邊 |
| switchToL3 — structure 404 | #graph-container 顯示 "結構資料不存在..." 說明文字 |
| switchToL3 — structure !ok（非 404） | renderError 被呼叫 |
| switchToL3 — catch | renderError 被呼叫 |
| switchToL3 — module 找不到 | sourceNodeIds 視為空陣列，走空集合路徑 |
| switchToL1 — 有 l1GraphViewModel | layerState="L1"，selectedFeatureId=null，selectedModuleId=null，initGraph + renderFeatureList 以 l1GraphViewModel 呼叫 |
| switchToL1 — 有 l1GraphViewModel + selectedId | 還原 cytoscape 節點選取 |
| switchToL1 — 無 l1GraphViewModel | loadL1Graph() 被呼叫 |
| switchToL2FromL3 — 有 l2GraphViewModel | layerState="L2"，selectedModuleId=null，initGraph + renderFeatureList 以 l2GraphViewModel 呼叫 |
| switchToL2FromL3 — 無 l2GraphViewModel 但有 selectedFeatureId | switchToL2 被呼叫 |
| switchToL2FromL3 — 無 l2GraphViewModel 且無 selectedFeatureId | 不做任何事 |
| renderBreadcrumb — L1 | 1 個 part（span.breadcrumb-current），btnBackL1 hidden=true |
| renderBreadcrumb — L2 | 3 個 parts，含 L1 breadcrumb-link |
| renderBreadcrumb — L3 | 5 個 parts，含 L1/L2 breadcrumb-link |
| renderBreadcrumb — 無 breadcrumb 元素 | 安全 return，不 throw |
| renderBreadcrumb — L2 不存在的 featureId | label fallback 為 "（未知功能）" |
| renderBreadcrumb — L3 不存在的 moduleId | label fallback 為 "（未知模組）" |
| renderFeatureList — viewModel 為 null | 空陣列路徑（empty-state） |
| renderFeatureList — 空 nodes | 顯示 "此層級沒有節點。" |
| renderFeatureList — 無 #feature-list | 安全 return |
| renderFeatureList — L1 node | confidence badge 渲染，desc = node.description |
| renderFeatureList — L1 + diff_available + 對應 change | 顯示 diff-tag with mapped label |
| renderFeatureList — L1 + diff_available + 未知 change_type | tag 文字 fallback 為原始 change_type |
| renderFeatureList — L2 node | confidence badge 渲染，desc = confidence_reason |
| renderFeatureList — L3 node | type badge 渲染（confidence-badge class），desc = node.file |
| renderFeatureList — DIFF node | change-badge + 卡片有 change-<type> class |
| renderFeatureList — selectedId 比對 | 對應 node 卡片有 active class |
| renderFeatureList — L1 節點點擊 | unselect + select + animate，state.selectedFeatureId 被設定，renderDetailPanelL1 以 { onEnterL2: switchToL2 } 呼叫，active class 同步 |
| renderFeatureList — L2 節點點擊 | state.selectedModuleId 被設定，renderDetailPanelL2 以 { onEnterL3, onGenerateLayerExplanation } 呼叫 |
| renderFeatureList — L3 節點點擊 | renderDetailPanelL3 以 node 呼叫 |
| renderFeatureList — DIFF 節點點擊 | renderDetailPanelDiff 以 node 呼叫 |
| renderFeatureList — 無 cytoscapeInstance 點擊 | 不 throw，仍呼叫對應 renderDetailPanel* |
| renderFeatureList — cytoscape getElementById 返回 null | 不 throw |
| renderL2NotAnalyzed | feature-list 含 .not-analyzed-state + 按鈕 + hint + code；graph-container 含標題無按鈕 |
| renderL2NotAnalyzed — 按下按鈕 | disabled=true，文字"生成中…"，generateL2 被呼叫 |
| renderL2NotAnalyzed — 元素不存在 | 安全略過 |
| generateL2 — 成功 | pollUntilComplete 被呼叫，回呼觸發 switchToL2(featureId) |
| generateL2 — !res.ok | renderError 被呼叫，不 poll |
| generateL2 — catch | renderError 被呼叫 |
| generateLayerExplanation — 成功 | pollUntilComplete 被呼叫，回呼觸發 loadLayerExplanation(featureId, layer) |
| generateLayerExplanation — !res.ok | renderError 被呼叫 |
| generateLayerExplanation — catch | renderError 被呼叫 |
| pollUntilComplete — completed | onComplete async function 被 await 呼叫，setInterval 清除 |
| pollUntilComplete — failed | renderError 被呼叫 |
| pollUntilComplete — !res.ok | 靜默清除 interval |
| pollUntilComplete — catch | 靜默清除 interval |
| pollUntilComplete — 超過 maxAttempts | renderError("任務逾時，請稍後重試。") |
| switchToMindmap | sessionStorage["mindmap-data"] 被設定，window.open 被呼叫 |
| switchToMindmap — 無 projectStatus | project = "專案" fallback |
| loadLayerExplanation — 成功有 explanation | state.layerExplanation 被設定，layerExplanationEl 有 `<p class="layer-explanation-text">` |
| loadLayerExplanation — 成功 explanation 為空 | state.layerExplanation = null，不插入 p |
| loadLayerExplanation — 404 | state.layerExplanation = null，layerExplanationEl 清空 |
| loadLayerExplanation — !res.ok（非 404） | 提早 return |
| loadLayerExplanation — 無 layerExplanationEl | 提早 return |
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
