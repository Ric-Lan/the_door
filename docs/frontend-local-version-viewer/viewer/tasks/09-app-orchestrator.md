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
import * as Api from './api.js';
import { buildViewModelFromReport, buildL1ViewModelFromStatic, snapshotLabel } from './viewmodel.js';
import { renderTopBar, updateLogoMark } from './ui-topbar.js';
import { renderChangeList } from './ui-list.js';
import { renderDetailPanel, renderError } from './ui-detail.js';
import { showUpdateModal, hideUpdateModal, submitUpdate, stopPolling } from './ui-modal.js';
import { loadL1Graph, loadDiffOverlay, switchToL1, switchToMindmap } from './layers.js';
import { openGraphDrawer, closeGraphDrawer } from './graph.js';
```

---

## 匯出介面

```js
export function render()
export function setMode(mode)
```

其餘（`selectItem`, `loadProjectStatus`, `loadFromApi`, `loadStaticFallback`, `populateVersionSelectors`）為模組內私有函式。

---

## 各函式規格

### render()

```js
updateLogoMark();
renderTopBar();
renderChangeList({ onSelect: selectItem });
renderDetailPanel();
document.querySelector('.app-shell')?.classList.toggle('diff-mode', state.mode === 'diff');
const banner = document.getElementById('diff-mode-banner');
if (banner) banner.hidden = state.mode !== 'diff';
```

### setMode(mode)

- `hasDiff` = `state.updateModel?.diff_available === true`
- `hasVersionCompare` = `versionA && versionB && versionA !== versionB`
- `mode === "diff"` 且 `!hasDiff && !hasVersionCompare` → return（不改 state）
- 否則：`state.mode = mode`，`state.selectedId = firstSelectableId()`，呼叫 `render()`
- `hasVersionCompare && !hasDiff`：
  - baseline → `loadL1Graph(state.versionA)`
  - current → `loadL1Graph(state.versionB)`
  - diff → `loadL1Graph(state.versionB)`

### firstSelectableId()（私有）

- `state.mode === "diff"` → `state.updateModel?.changes?.[0]?.id ?? null`
- 其他 → `state.l1Model?.features?.[0]?.id ?? null`

### loadProjectStatus()（私有）

- GET `/api/project`（透過 `Api.fetchProjectStatus()`）
- 成功 → `state.projectStatus = data`，呼叫 `loadFromApi()`
- !ok → `renderError(message)`，不呼叫 loadFromApi
- network error → `loadStaticFallback()`

### loadFromApi()（私有）

- `ps = state.projectStatus`，若 null → return
- `has_latest_report` → `loadReport()`（私有，呼叫 Api.fetchLatestReport，設定 state.updateModel）
- `has_snapshots` → `loadSnapshots()`（私有，呼叫 Api.fetchSnapshots，設定 state.snapshots / versionA / versionB，呼叫 `populateVersionSelectors()`）
- `state.mode = "baseline"`，`state.selectedId = firstSelectableId()`，`render()`
- `has_snapshots` → `loadL1Graph(hasVersionCompare ? state.versionB : null)`

### loadStaticFallback()（私有）

- `Api.fetchStaticUpdateViewModel()` → `state.updateModel = data`
- `Api.fetchStaticL1ViewModel()` → 設定 state.l1GraphViewModel 與 state.l1Model
- `state.mode = state.updateModel?.diff_available ? "diff" : "baseline"`
- `render()`，若有 l1GraphViewModel → `initGraph(...)`、`renderLegend()`

### populateVersionSelectors()（私有）

（來源行號：243–283）

- `selA` = `document.getElementById("select-version-a")`；`selB` = `document.getElementById("select-version-b")`；`selectorBar` = `document.getElementById("version-selector-bar")`
- 任一不存在 → return
- `state.snapshots.length <= 1` → `selectorBar.hidden = true`，return
- `selectorBar.hidden = false`
- 為 selA/selB 各填入 `<option value=version_id>snapshotLabel(s)</option>`，並設定預設值（A = state.versionA，B = state.versionB）
- **使用 `sel.onchange`（賦值型）覆寫，避免多次呼叫累積 handler**
- selA.onchange → `state.versionA = selA.value`，`state.mode = "diff"`，`renderTopBar()`，`loadL1Graph(state.versionB ?? state.versionA)`
- selB.onchange → `state.versionB = selB.value`，`state.mode = "diff"`，`renderTopBar()`，`loadL1Graph(state.versionB)`

---

## 事件綁定（模組頂層）

```js
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
  submitUpdate(oldPath, newPath, { onComplete: () => { loadFromApi(); }, onError: renderError });
});
els.btnGraphToggle?.addEventListener("click", openGraphDrawer);
els.btnDrawerClose?.addEventListener("click", closeGraphDrawer);
els.graphBackdrop?.addEventListener("click",  closeGraphDrawer);
els.btnMindmap?.addEventListener("click",     switchToMindmap);
els.btnBackL1?.addEventListener("click",      switchToL1);
loadProjectStatus();
```

---

## 測試規格

### tests/app.test.js

測試方法：`vi.mock('../js/ui-topbar.js', ...)` mock 所有依賴模組，驗證 orchestration 邏輯。

| 測試案例 | 驗證 |
|---|---|
| render — 呼叫順序 | updateLogoMark → renderTopBar → renderChangeList → renderDetailPanel |
| render — mode=diff | .app-shell 含 diff-mode class，#diff-mode-banner 不 hidden |
| render — mode≠diff | #diff-mode-banner hidden |
| setMode("diff") — 無 diff 可用 | state.mode 不改變，render 未呼叫 |
| setMode("diff") — hasDiff=true | state.mode="diff"，render 呼叫 |
| setMode("baseline") — hasVersionCompare | loadL1Graph(state.versionA) 呼叫 |
| setMode("current") — hasVersionCompare | loadL1Graph(state.versionB) 呼叫 |
| loadProjectStatus — 成功 | state.projectStatus 設定，loadFromApi 呼叫 |
| loadProjectStatus — !ok | renderError 呼叫，loadFromApi 未呼叫 |
| loadProjectStatus — network error | loadStaticFallback 呼叫 |
| loadFromApi — has_latest_report | loadReport 流程觸發 |
| loadFromApi — has_snapshots | loadSnapshots 觸發，loadL1Graph 呼叫 |
| btnDiff click | setMode("diff") 呼叫 |
| btnReanalyze click | showUpdateModal 呼叫 |
| btnModalSubmit click — 路徑空白 | showModalError 呼叫，submitUpdate 未呼叫 |
| btnModalSubmit click — 有路徑 | hideUpdateModal 呼叫，submitUpdate 呼叫 |
| populateVersionSelectors — snapshots ≤ 1 | selectorBar hidden |
| populateVersionSelectors — snapshots > 1 | selectorBar 顯示，selA/selB 有 options |
| populateVersionSelectors — selA.onchange | state.versionA 更新，loadL1Graph 呼叫 |
| populateVersionSelectors — 多次呼叫 | onchange 不重複綁定（賦值覆寫）|

---

## TDD 步驟

1. **RED**：寫 `tests/app.test.js`，確認失敗
2. **GREEN**：建立 `js/app.js`，最小實作
3. **REFACTOR**：整理

## 驗證檢查清單

- [ ] `npm test tests/app.test.js` — 全部通過
- [ ] 此步驟 index.html 仍載入舊 `app.js`，新模組尚未接線（步驟 10 才接）
