# 步驟 4 — ui-topbar.js + ui-list.js

## 概覽

| 模組 | 來源行號（app.js） | 預估行數 | 依賴 |
|---|---|---|---|
| `js/ui-topbar.js` | 612–695 | ~90 | `state.js`, `dom.js` |
| `js/ui-list.js` | 698–827 | ~140 | `state.js`, `dom.js` |

---

## js/ui-topbar.js

### 匯出介面

```js
export function renderTopBar()
export function updateLogoMark()
```

### renderTopBar 規格

**條件：hasDiff** = `state.updateModel?.diff_available === true`  
**條件：hasVersionCompare** = `state.versionA && state.versionB && state.versionA !== state.versionB`

| 場景 | 行為 |
|---|---|
| 無 diff、無 version compare | `.mode-switch` hidden = true |
| 有 diff 或 version compare | `.mode-switch` hidden = false |
| hasDiff | summaryText = updateModel.summary |
| 無 diff，有 l1Model | summaryText = "功能總覽：共 N 個功能。" |
| 無 diff、無 l1Model | summaryText = "（載入中…）" |
| mode = "diff"，hasDiff | count badges 顯示，讀 updateModel.change_counts |
| mode = "diff"，hasVersionCompare（無 updateModel）| count badges 讀 state.versionDiff.summary |
| mode ≠ "diff" | count-removed/modified/risk hidden |
| btnBaseline 文字 | 有 snapshots[versionA] → snapshotLabel，否則 "版本 A" |
| btnCurrent 文字 | 有 snapshots[versionB] → snapshotLabel，否則 "版本 B" |
| btnDiff.disabled | !hasDiff && !hasVersionCompare |

### updateLogoMark 規格

| 條件 | logo src / data-state |
|---|---|
| mode="diff" 且（hasDiff 或 versionDiff） | mark-diff.svg / "diff" |
| layerState="L3" | mark-l3.svg / "l3" |
| layerState="L2" | mark-l2.svg / "l2" |
| 其他 | mark-l1.svg / "l1" |

已是目標 state 時不重設（比對 `img.dataset.state`）。

---

## js/ui-list.js

### 匯出介面

```js
export function renderChangeList(callbacks)    // callbacks: { onSelect }
export function changeListButton(item, isActive, callbacks)
export function featureCard(feature, isActive, callbacks)
export function changeSymbol(changeType)
```

### changeSymbol 規格

| changeType | 符號 |
|---|---|
| added | `"+"` |
| removed | `"-"` |
| attribute_changed | `"~"` |
| dependency_changed | `"!="` |
| 其他 | `"?"` |

### changeListButton 規格

- 回傳 `<button class="feature-card changed [active]">`
- 含 `.feature-card-label`（change.label）
- 含 `.feature-card-desc`（detail.after.description || detail.before.description || ""）
- 含 `.change-badge.change-<type>`（changeSymbol + " " + change_type）
- click → `callbacks.onSelect(change.id)`

### featureCard 規格

- 回傳 `<button class="feature-card [changed] [active]">`
- 有 `change_type` → 加 `.changed`
- 含 `.feature-card-label`、`.feature-card-desc`（description）
- 含 `.confidence-badge.confidence-badge-<level>`（若有 confidence）
- click → `callbacks.onSelect(feature.id)`

### renderChangeList 規格

| 場景 | 行為 |
|---|---|
| mode="diff"，有 updateModel.diff_available | 填入 changeListButton，listTitle="變更清單" |
| mode="diff"，無 updateModel，有 versionDiff | 從 versionDiff.node_states 篩選非 unchanged |
| mode="diff"，無資料 | renderEmpty("無變更項目。") |
| mode="baseline" | listTitle="舊版功能"，填入 featureCard |
| mode="current" | listTitle="新版功能"，填入 featureCard |
| l1Model 為 null | renderEmpty("L1 ViewModel 載入中…") |

---

## 測試規格

### tests/ui-topbar.test.js

| 測試案例 | 驗證 |
|---|---|
| renderTopBar — 無 diff | .mode-switch hidden |
| renderTopBar — hasDiff=true, mode=diff | count badges 顯示，數值正確 |
| renderTopBar — hasVersionCompare, versionDiff | count 從 versionDiff.summary 讀取 |
| renderTopBar — mode=baseline | count-removed/modified/risk hidden |
| renderTopBar — summaryText（hasDiff） | 顯示 summary |
| renderTopBar — summaryText（l1Model） | 顯示功能數 |
| renderTopBar — btnBaseline label | 有 snapshot 時顯示 snapshotLabel |
| updateLogoMark — mode=diff, hasDiff | src = mark-diff.svg |
| updateLogoMark — layerState=L2 | src = mark-l2.svg |
| updateLogoMark — 已是目標 state | 不重設 src |

### tests/ui-list.test.js

| 測試案例 | 驗證 |
|---|---|
| changeSymbol("added") | "+" |
| changeSymbol("removed") | "-" |
| changeSymbol("attribute_changed") | "~" |
| changeSymbol("dependency_changed") | "!=" |
| changeSymbol("unknown") | "?" |
| changeListButton — 結構 | 含 label、badge、change type class |
| changeListButton — isActive | 有 .active class |
| changeListButton — click | onSelect 被呼叫，傳入 change.id |
| featureCard — 無 change_type | 無 .changed |
| featureCard — 有 change_type | 有 .changed |
| featureCard — click | onSelect 被呼叫 |
| renderChangeList(mode=diff, 有 updateModel) | featureList 含 changeListButton |
| renderChangeList(mode=diff, 無資料) | empty-state 訊息 |
| renderChangeList(mode=baseline) | listTitle="舊版功能"，含 featureCard |

---

## TDD 步驟（每個模組）

1. **RED**：寫測試，確認失敗
2. **GREEN**：建立模組，最小實作
3. **REFACTOR**：整理

## 驗證檢查清單

- [ ] `npm test tests/ui-topbar.test.js` — 全部通過
- [ ] `npm test tests/ui-list.test.js` — 全部通過
- [ ] 啟動伺服器，topbar 與 list 顯示正常
