# Plan E — Frontend JavaScript（Task 06 + Task 07 + Task 08）

> **執行分類 E**：前端 JavaScript
> **依賴：** 無（可與 A/C/D 並行；Task 06/07/08 三個之間可並行）
> **前端路徑：** `docs/frontend-local-version-viewer/viewer/`（唯一正式版）
> **Worktree：** `loving-sinoussi-20dcd0`

---

## Task 06 — R6：前端篩選器 UI 接線

**實作策略：** 使用 `state._filteredFeatures` 中介欄位。`renderChangeList` 不改簽名，
`render()` 在呼叫前設值，`ui-list.js` 讀取 `state._filteredFeatures ?? state.l1Model?.features ?? []`。

**Files:**
- Modify: `docs/frontend-local-version-viewer/viewer/js/state.js`
- Modify: `docs/frontend-local-version-viewer/viewer/js/app.js`
- Modify: `docs/frontend-local-version-viewer/viewer/js/ui-list.js`
- Test: `docs/frontend-local-version-viewer/viewer/tests/app.test.js`

- [ ] **Step 1：寫失敗測試**

在 `viewer/tests/app.test.js` 末尾加入：

```javascript
describe('filter wiring — #filter-conf and #filter-type', () => {
  beforeEach(() => {
    state.filterConf = null;
    state.filterType = null;
    state._filteredFeatures = null;
    const confSel = document.getElementById('filter-conf');
    const typeSel = document.getElementById('filter-type');
    if (confSel) confSel.value = '';
    if (typeSel) typeSel.value = '';
  });

  it('state.js has filterConf, filterType, _filteredFeatures defaulting to null', () => {
    expect(state).toHaveProperty('filterConf', null);
    expect(state).toHaveProperty('filterType', null);
    expect(state).toHaveProperty('_filteredFeatures', null);
  });

  it('changing #filter-conf updates state.filterConf', () => {
    const confSel = document.getElementById('filter-conf');
    expect(confSel).not.toBeNull();
    confSel.value = 'high';
    confSel.dispatchEvent(new Event('change'));
    expect(state.filterConf).toBe('high');
  });

  it('changing #filter-type updates state.filterType', () => {
    const typeSel = document.getElementById('filter-type');
    expect(typeSel).not.toBeNull();
    typeSel.value = 'added';
    typeSel.dispatchEvent(new Event('change'));
    expect(state.filterType).toBe('added');
  });
});
```

- [ ] **Step 2：執行測試確認失敗**

```
cd docs/frontend-local-version-viewer/viewer && npx vitest run tests/app.test.js
```

預期：新增的 3 個 tests FAILED（`state` 無這三個欄位；事件未接線）

- [ ] **Step 3：更新 state.js**

在 `viewer/js/state.js` 的 `state` 物件末尾（`versionDiff: null` 後）加入三個欄位：

```javascript
  filterConf: null,
  filterType: null,
  _filteredFeatures: null,
```

- [ ] **Step 4：更新 app.js**

a. `init()` 函式末尾加入事件監聽（在 `loadProjectStatus()` 呼叫前）：

```javascript
  const filterConf = document.getElementById('filter-conf');
  const filterType = document.getElementById('filter-type');
  if (filterConf) {
    filterConf.addEventListener('change', () => {
      state.filterConf = filterConf.value || null;
      render();
    });
  }
  if (filterType) {
    filterType.addEventListener('change', () => {
      state.filterType = filterType.value || null;
      render();
    });
  }
```

b. 在 `app.js` 頂部 import 區，將：

```javascript
import { renderChangeList } from './ui-list.js';
```

改為：

```javascript
import { renderChangeList, applyCardFilters } from './ui-list.js';
```

c. 在 `render()` 函式中，`renderChangeList(...)` 呼叫前加入：

```javascript
  state._filteredFeatures = applyCardFilters(
    state.l1Model?.features ?? [],
    { conf: state.filterConf, type: state.filterType }
  );
```

- [ ] **Step 5：更新 ui-list.js**

找到 `renderChangeList` 非 diff 模式中的（line 158）：

```javascript
const features = state.l1Model?.features ?? [];
```

改為：

```javascript
const features = state._filteredFeatures ?? state.l1Model?.features ?? [];
```

- [ ] **Step 6：執行測試確認通過**

```
cd docs/frontend-local-version-viewer/viewer && npx vitest run tests/app.test.js tests/ui-list.test.js
```

預期：全部 PASSED

- [ ] **Step 7：Commit**

```
git add docs/frontend-local-version-viewer/viewer/js/state.js docs/frontend-local-version-viewer/viewer/js/app.js docs/frontend-local-version-viewer/viewer/js/ui-list.js docs/frontend-local-version-viewer/viewer/tests/app.test.js
git commit -m "feat(viewer): wire filter-conf/filter-type selects to applyCardFilters"
```

---

## Task 07 — R7：置頂欄版本標示

**Files:**
- Modify: `docs/frontend-local-version-viewer/viewer/js/ui-topbar.js`
- Test: `docs/frontend-local-version-viewer/viewer/tests/ui-topbar.test.js`

- [ ] **Step 1：寫失敗測試**

在 `viewer/tests/ui-topbar.test.js` 末尾加入：

```javascript
describe('renderTopBar — summaryText shows version label', () => {
  it('single version mode includes snapshot label in summaryText', () => {
    state.snapshots = [{ version_id: 'v1', label: 'v1.0.5', git_tags: [] }];
    state.versionB = 'v1';
    state.l1Model = { features: Array(7).fill({}), stats: { feature_count: 7 } };
    state.mode = 'current';
    renderTopBar();
    expect(els.summaryText.textContent).toContain('v1.0.5');
    expect(els.summaryText.textContent).toContain('7');
  });

  it('fallback to count-only when no snapshot found', () => {
    state.snapshots = [];
    state.versionB = null;
    state.l1Model = { features: Array(3).fill({}), stats: { feature_count: 3 } };
    state.mode = 'current';
    renderTopBar();
    expect(els.summaryText.textContent).toMatch(/3/);
    expect(els.summaryText.textContent).not.toContain('·');
  });
});
```

- [ ] **Step 2：執行測試確認失敗**

```
cd docs/frontend-local-version-viewer/viewer && npx vitest run tests/ui-topbar.test.js
```

預期：新增的 2 個 tests FAILED（summaryText 不含 label）

- [ ] **Step 3：實作**

在 `viewer/js/ui-topbar.js` 找到：

```javascript
  } else if (state.l1Model) {
    const fc = state.l1Model.stats?.feature_count ?? state.l1Model.features?.length ?? 0;
    els.summaryText.textContent = '功能總覽：共 ' + fc + ' 個功能。';
  }
```

改為：

```javascript
  } else if (state.l1Model) {
    const fc = state.l1Model.stats?.feature_count ?? state.l1Model.features?.length ?? 0;
    const vId = state.mode === 'baseline' ? state.versionA : state.versionB;
    const snap = state.snapshots.find(s => s.version_id === vId);
    const label = snap ? snapshotLabel(snap) : null;
    els.summaryText.textContent = label
      ? `${label} · 共 ${fc} 個功能`
      : `共 ${fc} 個功能`;
  }
```

（`snapshotLabel` 已定義在同檔案 line 4，直接使用）

- [ ] **Step 4：執行測試確認通過**

```
cd docs/frontend-local-version-viewer/viewer && npx vitest run tests/ui-topbar.test.js
```

預期：全部 PASSED

- [ ] **Step 5：Commit**

```
git add docs/frontend-local-version-viewer/viewer/js/ui-topbar.js docs/frontend-local-version-viewer/viewer/tests/ui-topbar.test.js
git commit -m "feat(viewer): topbar summary shows version label"
```

---

## Task 08 — R8：心智圖版本標示

> **實作位置：** sessionStorage 寫入在 `layers.js::buildMindmapData()`，不在 `app.js`。

**Files:**
- Modify: `docs/frontend-local-version-viewer/viewer/js/layers.js`
- Modify: `docs/frontend-local-version-viewer/viewer/mindmap-popup.html`
- Test: `docs/frontend-local-version-viewer/viewer/tests/layers.test.js`

- [ ] **Step 1：寫失敗測試**

在 `viewer/tests/layers.test.js` 末尾加入：

```javascript
describe('buildMindmapData — version labels', () => {
  it('includes versionALabel and versionBLabel when snapshots present', () => {
    state.snapshots = [
      { version_id: 'id-b', label: 'v1.0.5', git_tags: [] },
      { version_id: 'id-a', label: 'v1.0.0', git_tags: [] },
    ];
    state.versionA = 'id-a';
    state.versionB = 'id-b';
    state.l1GraphViewModel = { nodes: [], edges: [] };
    const data = buildMindmapData(state);
    expect(data.versionALabel).toBe('v1.0.0');
    expect(data.versionBLabel).toBe('v1.0.5');
  });

  it('versionALabel and versionBLabel are null when no snapshots', () => {
    state.snapshots = [];
    state.versionA = null;
    state.versionB = null;
    state.l1GraphViewModel = { nodes: [], edges: [] };
    const data = buildMindmapData(state);
    expect(data.versionALabel).toBeNull();
    expect(data.versionBLabel).toBeNull();
  });
});
```

- [ ] **Step 2：執行測試確認失敗**

```
cd docs/frontend-local-version-viewer/viewer && npx vitest run tests/layers.test.js
```

預期：新增的 2 個 tests FAILED（`buildMindmapData` 回傳無 versionALabel）

- [ ] **Step 3：更新 layers.js**

在 `buildMindmapData` 函式內，找到 `return` 語句前加入 helper，並擴充 return：

```javascript
  function _snapLabel(vId) {
    if (!vId) return null;
    const s = state.snapshots?.find(snap => snap.version_id === vId);
    if (!s) return null;
    if (s.git_tags?.length) return s.git_tags[0];
    return s.label ?? null;
  }

  return {
    project: projectName,
    nodes,
    diffNodes,
    diffAvailable,
    versionALabel: _snapLabel(state.versionA),
    versionBLabel: _snapLabel(state.versionB),
  };
```

（替換原本的 `return { project: projectName, nodes, diffNodes, diffAvailable };`）

- [ ] **Step 4：更新 mindmap-popup.html 的 init() 函式**

找到 `init()` 中：

```javascript
  const projectName = (data.project || "").split(/[/\\]/).filter(Boolean).pop() || "專案";
  data.projectName = projectName;
  document.getElementById("project-name").textContent = projectName;
```

改為：

```javascript
  const projectName = (data.project || "").split(/[/\\]/).filter(Boolean).pop() || "專案";
  data.projectName = projectName;
  const vAL = data.versionALabel;
  const vBL = data.versionBLabel;
  let versionLabel = "";
  if (data.diffAvailable && vAL && vBL) {
    versionLabel = ` — A · ${vAL} → B · ${vBL}`;
  } else if (vBL) {
    versionLabel = ` · ${vBL}`;
  } else if (vAL) {
    versionLabel = ` · ${vAL}`;
  }
  document.getElementById("project-name").textContent = projectName + versionLabel;
```

- [ ] **Step 5：執行測試確認通過**

```
cd docs/frontend-local-version-viewer/viewer && npx vitest run tests/layers.test.js
```

預期：全部 PASSED

- [ ] **Step 6：Commit**

```
git add docs/frontend-local-version-viewer/viewer/js/layers.js docs/frontend-local-version-viewer/viewer/mindmap-popup.html docs/frontend-local-version-viewer/viewer/tests/layers.test.js
git commit -m "feat(viewer): mindmap popup shows A/B version labels"
```
