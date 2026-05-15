# 步驟 5 — ui-detail.js

## 概覽

| 模組 | 來源行號（app.js） | 預估行數 | 依賴 |
|---|---|---|---|
| `js/ui-detail.js` | 830–1029, 1984–2193 | ~360 | `state.js`, `dom.js` |

---

## 匯出介面

```js
export function renderDetailPanel()
export function renderDiffDetailPanel()
export function renderSingleVersionDetailPanel()
export function renderDetailPanelL1(node, callbacks = {})   // callbacks: { onEnterL2 }
export function renderDetailPanelL2(node, callbacks = {})   // callbacks: { onEnterL3, onGenerateLayerExplanation }
export function renderDetailPanelL3(node)
export function renderDetailPanelDiff(node)
export function renderEmpty(parent, message)
export function renderError(message)
export function renderNoSelection()
export function toggleDiffSort(mode)
export function applyDiffSort(nodes, mode)
export function detailSection(title, text)
export function listDetailSection(title, items)
export function attributionSection(source)
```

---

## 各函式規格

### renderEmpty(parent, message)

在 `parent` **後面追加**（不清空）`<div class="empty-state">message</div>`。

### renderError(message)

全域錯誤顯示（**無 container 參數**）：
- `els.summaryText.textContent` = `"資料載入失敗。"`
- 清空 `els.featureList`，插入 `<div class="error-box">message</div>`
- `els.btnDiff.disabled` = `els.btnBaseline.disabled` = `els.btnCurrent.disabled` = true

### renderNoSelection()

- `els.detailSource.textContent` = `"尚未選取"`
- `els.detailContent.className` = `"detail-content empty-state"`
- `els.detailContent.textContent` = `"選取左側項目以查看詳情。"`

### detailSection(title, text)

回傳 `<section class="detail-section"><h3>title</h3><p>text</p></section>`。  
若 text 為 null/undefined → `<p class="missing">未提供</p>`。

### listDetailSection(title, items)

回傳 `<section class="detail-section"><h3>title</h3>…</section>`。  
items 空 → `<p class="missing">未提供</p>`；否則 `<ul class="source-list">` 每項一個 `<li>`。

### attributionSection(source)

回傳 `<div class="attribution">資料來源：<code>source || "unknown"</code></div>`。

---

### renderDetailPanel()

依 `state.mode` 分派：
- `state.mode === "diff"` → `renderDiffDetailPanel()`（update-report diff）
- 其他 → `renderSingleVersionDetailPanel()`

**注意**：不依賴 `state.layerState` 分派。

### renderDiffDetailPanel()

（update-report diff；無參數；讀 `state.updateModel`）

- `detail` = `state.updateModel?.details?.[state.selectedId]`
- 無 detail → `renderNoSelection()`，return
- `els.detailSource.textContent` = detail.source
- 清空 `els.detailContent`，依序插入：
  - before/after 區塊（`.before-after > .ba-panel.before / .ba-panel.after`）
  - `detailSection("範圍狀態", detail.scope_state)`
  - `listDetailSection("相關漏洞", detail.related_vulnerabilities ?? [])`
  - `listDetailSection("受影響關係", detail.affected_relations ?? [])`
  - `attributionSection(detail.source)`
  - `_appendDiffExplanationSection(state.selectedId, els.detailContent)` （步驟 7 接線，暫 no-op）
  - `_appendUserNotesSection("diff", state.selectedId, state.versionA, state.versionB, els.detailContent)` （步驟 7 接線，暫 no-op）

### renderSingleVersionDetailPanel()

（單版本；無參數；讀 `state.l1Model` + `state.selectedId`）

- `feature` = `state.l1Model?.features?.find(f => f.id === state.selectedId)`
- 無 feature → `renderNoSelection()`，return
- `els.detailSource.textContent` = feature.source
- 清空 `els.detailContent`，依序插入：
  - `detailSection("功能名稱", feature.label)`
  - `detailSection("描述", feature.description)`
  - `detailSection("觸發方式", feature.trigger_description)`
  - `detailSection("信心等級", feature.confidence)`
  - `detailSection("信心理由", feature.confidence_reason)`
  - `listDetailSection("Source nodes", feature.source_nodes ?? [])`
  - `attributionSection(feature.source)`
  - `_appendUserNotesSection(state.mode, feature.id, versionA, versionB, els.detailContent)` （步驟 7 接線，暫 no-op）

---

### renderDetailPanelL1(node, callbacks = {})

（L1 graph node 被點擊；由 `layers.js` 的 `renderFeatureList` 呼叫）

- `els.detailSource.textContent` = `"L1Output.features[feature_id=<node.id>]"`
- 清空 `els.detailContent`，依序插入：
  - `detailSection("功能名稱", node.label)`
  - `detailSection("描述", node.description)`
  - `detailSection("信心等級", node.confidence)`
  - `detailSection("觸發說明", node.trigger_description)`
  - `<button class="action-button">進入 L2</button>`：click → `callbacks.onEnterL2?.(node.id)`
  - `attributionSection("L1Output.features[feature_id=<node.id>]")`

### renderDetailPanelL2(node, callbacks = {})

（L2 graph node 被點擊；由 `layers.js` 的 `renderFeatureList` 呼叫）

- `els.detailSource.textContent` = `"L2Output.modules[module_id=<node.id>]"`
- 清空 `els.detailContent`，依序插入：
  - `detailSection("模組名稱", node.label)`
  - `detailSection("信心等級", node.confidence)`
  - `listDetailSection("Source Nodes", node.source_nodes || [])`
  - 若 `state.l2GraphViewModel?.anomalies?.length > 0` → 插入 anomaly section（`.detail-section > h3 + div.anomaly-item*`）
  - `<button class="action-button">進入 L3</button>`：click → `callbacks.onEnterL3?.(node.id)`
  - `<button class="action-button">展開說明</button>`：click → 若 `state.layerExplanation` 存在則顯示，否則插入「生成 L2 說明」按鈕呼叫 `callbacks.onGenerateLayerExplanation?.(state.selectedFeatureId, "l2")`
  - `attributionSection("L2Output.modules[module_id=<node.id>]")`

### renderDetailPanelL3(node)

（L3 structure node 被點擊；由 `layers.js` 的 `renderFeatureList` 呼叫）

- `els.detailSource.textContent` = `"StructureJSON.nodes[node_id=<node.id>]"`
- 清空 `els.detailContent`，插入：
  - `detailSection("名稱", node.label)`
  - `detailSection("類型", node.type)`
  - `detailSection("檔案", node.file)`
  - `attributionSection("StructureJSON.nodes[node_id=<node.id>]")`

### renderDetailPanelDiff(node)

（version-compare DIFF graph node 被點擊；由 `layers.js` 的 `renderFeatureList` 呼叫）

- `els.detailSource.textContent` = `"UpdateReport.l1_changes[feature_id=<node.id>]"`
- 清空 `els.detailContent`，插入：
  - `detailSection("變更類型", node.change_type)`
  - `detailSection("現在名稱", node.current_label)`
  - `detailSection("原始名稱", node.baseline_label)`
  - `listDetailSection("風險標記", node.risk_flags || [])`
  - `attributionSection(...)`
  - `_appendDiffExplanationSection` + `_appendUserNotesSection`（暫 no-op）

---

### toggleDiffSort(mode)

- `state.diffSortMode = mode`
- 若 `state.diffGraphViewModel` 存在 → `applyDiffSort(nodes, mode)` 取排序結果，組合新 viewModel，呼叫 `renderFeatureList(sortedVm, "DIFF")`

### applyDiffSort(nodes, mode)

回傳新陣列（不 mutate 原始陣列）：

| mode | 排序規則 |
|---|---|
| `"semantic"` | 依 `_semanticMagnitude`（Levenshtein 近似值）**降序**（變化最大的在前） |
| 其他（預設 risk） | 先依 `RISK_PRIORITY`（`out_of_scope=0, vulnerability=1, semantic_drift=2`）升序；相同時再依 `CHANGE_PRIORITY`（`added=3, attribute_changed=4, dependency_changed=5, removed=6`）升序 |

---

## 測試規格

### tests/ui-detail.test.js

| 測試案例 | 驗證 |
|---|---|
| detailSection — 有值 | 回傳 section 含 h3 + p.textContent |
| detailSection — null | p.className 含 "missing"，textContent = "未提供" |
| listDetailSection — 有 items | 含 ul.source-list，每 item 一 li |
| listDetailSection — 空 items | 含 p.missing |
| attributionSection | 含 code 元素，textContent = source |
| renderEmpty | parent 新增 .empty-state，parent 不被清空 |
| renderError | summaryText 變更，featureList 含 .error-box，按鈕 disabled |
| renderNoSelection | detailSource = "尚未選取"，detailContent class 含 empty-state |
| renderDetailPanel — mode=diff | renderDiffDetailPanel 被呼叫 |
| renderDetailPanel — mode=baseline | renderSingleVersionDetailPanel 被呼叫 |
| renderDiffDetailPanel — 有 detail | detailContent 含 .before-after |
| renderDiffDetailPanel — 無 detail | renderNoSelection 被呼叫 |
| renderSingleVersionDetailPanel — 有 feature | detailContent 含功能名稱 section |
| renderSingleVersionDetailPanel — 無 feature | renderNoSelection 被呼叫 |
| renderDetailPanelL1 — 結構 | detailContent 含 label、description、"進入 L2" 按鈕 |
| renderDetailPanelL1 — 無 trigger_description | detailSection 顯示 "未提供" |
| renderDetailPanelL1 — L2 按鈕 click | callbacks.onEnterL2 被呼叫，傳入 node.id |
| renderDetailPanelL2 — 結構 | 含 source_nodes list，"進入 L3" 按鈕 |
| renderDetailPanelL2 — anomalies | anomaly section 顯示 |
| renderDetailPanelL2 — L3 按鈕 click | callbacks.onEnterL3 被呼叫 |
| renderDetailPanelL3 — 結構 | 含 label、type、file |
| renderDetailPanelDiff — 結構 | 含 change_type、current_label、risk_flags |
| toggleDiffSort — risk → semantic | state.diffSortMode = "semantic" |
| toggleDiffSort — 有 diffGraphViewModel | renderFeatureList 以排序後 viewModel 呼叫 |
| applyDiffSort(risk) | RISK_PRIORITY 升序；相同風險時 CHANGE_PRIORITY 升序 |
| applyDiffSort(semantic) | _semanticMagnitude 大的在前 |
| applyDiffSort — 不 mutate | 原始陣列順序不變 |

---

## TDD 步驟

1. **RED**：寫 `tests/ui-detail.test.js`，確認失敗
2. **GREEN**：建立 `js/ui-detail.js`，最小實作
3. **REFACTOR**：整理

## 驗證檢查清單

- [ ] `npm test tests/ui-detail.test.js` — 全部通過
- [ ] 啟動伺服器，點選功能卡片後 detail panel 顯示正確
