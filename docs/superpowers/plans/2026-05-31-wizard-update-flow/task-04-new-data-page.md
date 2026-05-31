# Task 04 — B 路：新資料路徑頁 + baseline 選擇

**內容分類：** B 分支入口頁。收新資料資料夾路徑 + 選比較基準版本。

**設計來源：** spec §4.3。

**Files:**
- Modify: `docs/frontend-local-version-viewer/viewer/js/ui-wizard.js`（`transition` 加 `SET_NEW_DATA_PATH` / `SET_BASELINE` / `NEXT_FROM_NEW_DATA`；`renderPage` 加 `PAGE_NEW_DATA`）
- Test: `docs/frontend-local-version-viewer/viewer/tests/wizard-update-flow.test.js`（append）

---

- [ ] **Step 1: 寫 reducer 失敗測試**

append：

```javascript
describe('new-data branch reducer', () => {
  const base = { ...getInitialState(), page: 'PAGE_NEW_DATA', updateFlow: 'new_data' };
  it('SET_NEW_DATA_PATH stores the path', () => {
    const s = transition(base, { type: 'SET_NEW_DATA_PATH', path: '/downloads/v2' });
    expect(s.newDataPath).toBe('/downloads/v2');
  });
  it('SET_BASELINE stores the baseline ref', () => {
    const s = transition(base, { type: 'SET_BASELINE', ref: 'v1.2.2' });
    expect(s.baselineRef).toBe('v1.2.2');
  });
  it('NEXT_FROM_NEW_DATA advances to PAGE_SIMILARITY_GUIDE', () => {
    const s = transition({ ...base, newDataPath: '/d/v2', baselineRef: 'v1.2.2' },
      { type: 'NEXT_FROM_NEW_DATA' });
    expect(s.page).toBe('PAGE_SIMILARITY_GUIDE');
  });
});
```

- [ ] **Step 2: 跑測試確認失敗**

```bash
cd docs/frontend-local-version-viewer/viewer
./node_modules/.bin/vitest.cmd run tests/wizard-update-flow.test.js -t "new-data branch reducer" --reporter=verbose 2>&1 | tail -15
```
Expected: FAIL。

- [ ] **Step 3: 加 reducer cases**

`transition` 內，`PICK_NEW_DATA` case 後加：

```javascript
    case 'SET_NEW_DATA_PATH':
      return { ...state, newDataPath: action.path };

    case 'SET_BASELINE':
      return { ...state, baselineRef: action.ref };

    case 'NEXT_FROM_NEW_DATA':
      return { ...state, page: 'PAGE_SIMILARITY_GUIDE' };
```

> 「已知 version_id 集合」由 Task 02 的 `SNAPSHOTS_LOADED`（載入快照清單時）一併填入 `knownVersionIds`，
> 不在本 task 另設 action——避免重複定義。

- [ ] **Step 4: 跑測試確認通過**

```bash
./node_modules/.bin/vitest.cmd run tests/wizard-update-flow.test.js -t "new-data branch reducer" --reporter=verbose 2>&1 | tail -10
```
Expected: PASS。

- [ ] **Step 5: 寫 render 失敗測試**

append：

```javascript
describe('PAGE_NEW_DATA render', () => {
  function render(state, dispatch = () => {}) {
    const container = document.createElement('div');
    renderPage(container, state, dispatch, () => {}, {});
    return container;
  }
  it('has a path input and a baseline select', () => {
    const c = render({ ...getInitialState(), page: 'PAGE_NEW_DATA', updateFlow: 'new_data' });
    expect(c.querySelector('[data-newdata-path]')).not.toBeNull();
    expect(c.querySelector('[data-baseline-pick]')).not.toBeNull();
  });
  it('next button is disabled until both path and baseline are set', () => {
    const c = render({ ...getInitialState(), page: 'PAGE_NEW_DATA', updateFlow: 'new_data',
      newDataPath: '', baselineRef: null });
    expect(c.querySelector('[data-newdata-next]').disabled).toBe(true);
  });
  it('next button enabled when both set', () => {
    const c = render({ ...getInitialState(), page: 'PAGE_NEW_DATA', updateFlow: 'new_data',
      newDataPath: '/d/v2', baselineRef: 'v1.2.2' });
    expect(c.querySelector('[data-newdata-next]').disabled).toBe(false);
  });
});
```

- [ ] **Step 6: 跑測試確認失敗**

```bash
./node_modules/.bin/vitest.cmd run tests/wizard-update-flow.test.js -t "PAGE_NEW_DATA render" --reporter=verbose 2>&1 | tail -15
```
Expected: FAIL。

- [ ] **Step 7: 實作 `PAGE_NEW_DATA` render case**

在 `renderPage` switch（`PAGE_REGEN_GUIDE` case 之後）插入：

```javascript
    case 'PAGE_NEW_DATA': {
      const ready = Boolean(state.newDataPath && state.baselineRef);
      wrap.innerHTML = `
        <p class="wizard-eyebrow eyebrow">步驟 / 引入新資料</p>
        <h2>指向新版本資料夾</h2>
        <p class="wizard-subtitle lede">輸入新下載版本的原始碼路徑，並選一個既有版本當比較基準。</p>
        <div class="wizard-field field">
          <label>新版本原始碼路徑</label>
          <input type="text" data-newdata-path placeholder="/absolute/path/to/new-version" value="${state.newDataPath}">
        </div>
        <div class="wizard-field field">
          <label>比較基準（既有版本）</label>
          <select data-baseline-pick></select>
        </div>
        <div class="actions">
          <button class="wizard-btn-ghost btn btn-ghost" data-back="PAGE_UPDATE_MODE">← 上一步</button>
          <span class="spacer"></span>
          <button class="wizard-btn-primary btn btn-primary" data-newdata-next ${ready ? '' : 'disabled'}>下一步 ${I.arrow}</button>
        </div>
      `;
      // 路徑用 change（離開欄位/Enter 才 dispatch），不可用 input——否則每字觸發全量重建會失焦。
      const pathInput = wrap.querySelector('[data-newdata-path]');
      pathInput.addEventListener('change', e => dispatch({ type: 'SET_NEW_DATA_PATH', path: e.target.value }));

      // baseline 清單：一次性載入（state.snapshots===null 才打 API），之後從 state 同步重建。
      const sel = wrap.querySelector('[data-baseline-pick]');
      if (state.snapshots === null) {
        if (api && typeof api.getSnapshots === 'function') {
          sel.innerHTML = `<option value="">— 載入中 —</option>`;
          api.getSnapshots()
            .then(({ snapshots }) => dispatch({ type: 'SNAPSHOTS_LOADED', snapshots }))
            .catch(() => { sel.innerHTML = `<option value="">（讀取版本清單失敗）</option>`; });
        }
      } else {
        sel.innerHTML = `<option value="">— 請選擇 —</option>` + state.snapshots.map(s => {
          const r = resolveSnapshotRef(s);
          const selected = r === state.baselineRef ? ' selected' : '';
          return `<option value="${r}"${selected}>${r}</option>`;
        }).join('');
        sel.addEventListener('change', e => dispatch({ type: 'SET_BASELINE', ref: e.target.value || null }));
      }
      wrap.querySelector('[data-newdata-next]').addEventListener('click', () => {
        if (state.newDataPath && state.baselineRef) dispatch({ type: 'NEXT_FROM_NEW_DATA' });
      });
      bindBack(wrap);
      break;
    }
```

- [ ] **Step 8: 跑測試確認通過 + 全套不退步**

```bash
./node_modules/.bin/vitest.cmd run tests/wizard-update-flow.test.js --reporter=verbose 2>&1 | tail -15
./node_modules/.bin/vitest.cmd run 2>&1 | tail -6
```
Expected: 新檔全綠；全套 853 passed 不退步。

- [ ] **Step 9: Commit**

```bash
git add docs/frontend-local-version-viewer/viewer/js/ui-wizard.js docs/frontend-local-version-viewer/viewer/tests/wizard-update-flow.test.js
git commit -m "feat(wizard): new-data path page with baseline picker (B branch entry)"
```

## Done when
- [ ] 路徑 input + baseline select 都在
- [ ] 兩者齊全前「下一步」disabled，齊全後 enabled 且進 `PAGE_SIMILARITY_GUIDE`
- [ ] 全套不退步
