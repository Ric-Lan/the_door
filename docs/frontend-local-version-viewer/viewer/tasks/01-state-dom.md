# 步驟 1 — state.js + dom.js

## 概覽

| 模組 | 來源行號 | 預估行數 | 依賴 |
|---|---|---|---|
| `js/state.js` | 18–70 | ~60 | 無 |
| `js/dom.js` | 76–108 | ~35 | 無 |

---

## js/state.js

### 匯出介面

```js
export const state = { /* 22 個欄位 */ };
```

### 初始值規格

| 欄位 | 初始值 | 類型 |
|---|---|---|
| updateModel | null | object\|null |
| l1Model | null | object\|null |
| mode | `"baseline"` | string |
| selectedId | null | string\|null |
| projectStatus | null | object\|null |
| pollingJobId | null | string\|null |
| pollingHandle | null | number\|null |
| layerState | `"L1"` | string |
| selectedFeatureId | null | string\|null |
| selectedModuleId | null | string\|null |
| l1GraphViewModel | null | object\|null |
| l2GraphViewModel | null | object\|null |
| l3GraphViewModel | null | object\|null |
| diffGraphViewModel | null | object\|null |
| cytoscapeInstance | null | object\|null |
| cytoscapeAvailable | `false` | boolean |
| diffSortMode | `"risk"` | string |
| layerExplanation | null | string\|null |
| snapshots | `[]` | Array |
| versionA | null | string\|null |
| versionB | null | string\|null |
| versionDiff | null | object\|null |

---

## js/dom.js

### 匯出介面

```js
export const els = {
  btnDiff, btnBaseline, btnCurrent, btnReanalyze,
  summaryText, countAdded, countRemoved, countModified, countRisk,
  listTitle, listSource, featureList,
  detailSource, detailContent,
  pipelineProgress, currentStep, stepsList,
  updateModal, inputOldPath, inputNewPath, modalError, inputLanguage,
  btnModalCancel, btnModalSubmit,
  graphDrawer, graphBackdrop, btnGraphToggle, btnDrawerClose,
  zoomControls, btnBackL1, btnMindmap,
};
```

`type="module"` 保證執行時 DOM 已 ready，可在模組頂層直接呼叫 `getElementById`。

---

## 測試規格

### tests/state.test.js

| 測試案例 | 驗證項目 |
|---|---|
| 所有 22 個 key 存在 | `key in state` 為 true |
| nullable 欄位初始值 | 17 個欄位為 null |
| boolean 初始值 | `cytoscapeAvailable === false` |
| string 初始值 | mode="baseline", layerState="L1", diffSortMode="risk" |
| snapshots 初始值 | 為空陣列 |
| 可變性 | 賦值後值改變，仍是同一物件 |

### tests/dom.test.js

| 測試案例 | 驗證項目 |
|---|---|
| els 存在 | `typeof els === 'object'` |
| 每個 key 對應 DOM element | 31 個 key 各不為 null，instanceof Element |

---

## TDD 步驟

### state.js

1. **RED**：寫 `tests/state.test.js`，執行 `npm test tests/state.test.js` → 因模組不存在而失敗
2. **GREEN**：建立 `js/state.js`，複製初始值規格 → 執行測試全通過
3. **REFACTOR**：確認無多餘程式碼

### dom.js

1. **RED**：寫 `tests/dom.test.js`，執行 `npm test tests/dom.test.js` → 因模組不存在而失敗
2. **GREEN**：建立 `js/dom.js`，所有 `getElementById` 依 els 規格 → 執行測試全通過
3. **REFACTOR**：確認無多餘程式碼

## 驗證檢查清單

- [ ] `npm test tests/state.test.js` — 6 tests passed
- [ ] `npm test tests/dom.test.js` — 32 tests passed
- [ ] 啟動伺服器，頁面仍可正常載入（舊 app.js 仍在 index.html，此步驟不影響）
