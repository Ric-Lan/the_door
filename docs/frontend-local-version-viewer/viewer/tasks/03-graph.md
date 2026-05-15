# 步驟 3 — graph.js

## 概覽

| 模組 | 來源行號（app.js） | 預估行數 | 依賴 |
|---|---|---|---|
| `js/graph.js` | 1030–1432, 2192–2265 | ~420 | `state.js`（讀取 state） |

`window.cytoscape` 由 `<script src="./lib/cytoscape.min.js">` 同步載入，**不 import**。

---

## 匯出介面

```js
export function initGraph(containerId, viewModel)
export function buildCytoscapeElements(viewModel)
export function buildCytoscapeStyle(layerState)
export function bindCytoscapeEvents(cy, callbacks)    // callbacks: { onNodeTap }
export function syncFeatureListSelection(cy, featureId)
export function renderMermaidFallback(viewModel, layerState)
export function buildMermaidText(viewModel)
export function renderLegend()
export function initZoomControls(cy)
export function hideZoomControls()
export function openGraphDrawer()
export function closeGraphDrawer()
```

---

## 各函式規格

### buildCytoscapeElements(viewModel)

輸入：`{ nodes: [...], edges: [...] }`  
輸出：Cytoscape elements 陣列

- Nodes → `{ data: { id, label, ...其餘欄位 } }`
- Edges → `{ data: { id: source+"-"+target, source, target, lowestConfidence, ...其餘欄位 } }`
- `lowestConfidence` = 兩端節點 confidence 中較低者（高→低：high=3, medium=2, low=1）
- 任一端節點不存在時，confidence 視為 medium

### buildCytoscapeStyle(layerState)

回傳 Cytoscape style 陣列，含：
- 基礎 node 樣式（字型、顏色 `#607d8b`、圓角方形）
- change_type 顏色：added=`#4caf50`、removed=`#f44336`、attribute_changed=`#ff9800`、dependency_changed=`#ffc107`
- confidence border-style：high=solid, medium=dashed, low=dotted
- 選取狀態：border-color `#2196f3`
- 基礎 edge 樣式、edge confidence（medium=dashed, low=dotted）

### buildMermaidText(viewModel)

- 輸出格式：`flowchart LR\n  nodeId["label"]\n  src --> tgt`
- node label 中的雙引號替換為 `#quot;`（Mermaid 跳脫）

### renderMermaidFallback(viewModel, layerState)

- `#graph-container` style.display = "none"
- `#mermaid-fallback` style.display = "block"
- 插入 `.fallback-indicator`（說明文字含 layerState）
- 插入 `<pre class="mermaid-output">` 含 buildMermaidText 輸出

### openGraphDrawer()

- `#graph-drawer` 加 `.open` class
- 移除 `aria-hidden` 屬性
- `#graph-backdrop` hidden = false

### closeGraphDrawer()

- `#graph-drawer` 移除 `.open` class
- `aria-hidden` = "true"
- `#graph-backdrop` hidden = true

### renderLegend()

在 `#legend-panel` 插入 4 個 `.legend-item`：新增、移除、修改、未變更

### hideZoomControls()

`#zoom-controls` hidden = true

### initGraph(containerId, viewModel)

- viewModel 為 null 或 nodes 空 → container 顯示 `.empty-state`，不 throw
- `window.cytoscape` 未定義 → 呼叫 `renderMermaidFallback`
- Cytoscape 初始化成功 → 設定 state.cytoscapeInstance、state.cytoscapeAvailable = true
- 初始化失敗（throw） → 呼叫 `renderMermaidFallback`

---

## 測試規格

### tests/graph.test.js

| 測試案例 | 驗證項目 |
|---|---|
| buildCytoscapeElements — nodes | 結構正確 `{ data: { id, label } }` |
| buildCytoscapeElements — edges | id 為 src+"-"+tgt，含 lowestConfidence |
| lowestConfidence(high, low) | 結果為 "low" |
| lowestConfidence(medium, medium) | 結果為 "medium" |
| lowestConfidence(節點不存在) | 視為 medium |
| buildCytoscapeElements(空) | 回傳 [] |
| buildCytoscapeStyle | 回傳陣列，長度 ≥ 10 |
| buildCytoscapeStyle — node selector | 含 background-color: "#607d8b" |
| buildCytoscapeStyle — added | background-color: "#4caf50" |
| buildCytoscapeStyle — removed | background-color: "#f44336" |
| buildCytoscapeStyle — medium confidence | border-style: "dashed" |
| buildMermaidText — 基本 | 含 "flowchart LR" |
| buildMermaidText — node label | 節點 label 出現在輸出中 |
| buildMermaidText — 雙引號跳脫 | `"` 被替換為 `#quot;` |
| renderMermaidFallback | #graph-container 隱藏，#mermaid-fallback 顯示，含 pre |
| openGraphDrawer | #graph-drawer 有 .open，aria-hidden 移除，#graph-backdrop 不 hidden |
| closeGraphDrawer | #graph-drawer 無 .open，aria-hidden = "true"，#graph-backdrop hidden |
| hideZoomControls | #zoom-controls hidden = true |
| renderLegend | #legend-panel 含 4 個 .legend-item |
| initGraph(null viewModel) | container 顯示 .empty-state，不 throw |
| initGraph(空 nodes) | container 顯示 .empty-state，不 throw |
| initGraph(window.cytoscape 未定義) | renderMermaidFallback 被呼叫 |

**注意**：jsdom 中 `window.cytoscape` 不存在，`initGraph` 的 Cytoscape 成功路徑透過 mock `window.cytoscape` 測試。

---

## TDD 步驟

1. **RED**：寫 `tests/graph.test.js`，執行確認失敗
2. **GREEN**：建立 `js/graph.js`，最小實作
3. **REFACTOR**：整理

## 驗證檢查清單

- [ ] `npm test tests/graph.test.js` — 全部通過
- [ ] 啟動伺服器，圖形抽屜開關功能正常
