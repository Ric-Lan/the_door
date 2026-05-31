# Task 02 — 更新方式分岔頁 + reducer 改接（移除直跳確認）

**內容分類：** reducer 改接 + 新分岔頁。把「更新分析」從直跳確認改成進分岔頁，並改既有測試斷言。

**設計來源：** spec §3.1、§4.1。

**Files:**
- Modify: `docs/frontend-local-version-viewer/viewer/js/ui-wizard.js`（`getInitialState`、`transition` 的 `SELECT_ACTION`、新增 reducer case、`renderPage` 新增 `PAGE_UPDATE_MODE`）
- Test: `docs/frontend-local-version-viewer/viewer/tests/wizard-update-flow.test.js`（新建）
- Modify test: `docs/frontend-local-version-viewer/viewer/tests/ui-wizard.test.js`（改一條既有斷言）

---

- [ ] **Step 1: 先改既有那條會壞掉的斷言（update 不再直跳 confirm）**

`tests/ui-wizard.test.js` 內既有這條（約在 `describe('transition: SELECT_ACTION')`）：

```javascript
  it('update action (has snapshots) goes to PAGE_CONFIRM', () => {
    const s = transition(stateWithSnapshots(true), { type: 'SELECT_ACTION', action: 'update' });
    expect(s.page).toBe('PAGE_CONFIRM');
    expect(s.action).toBe('update');
  });
```

改成：

```javascript
  it('update action (has snapshots) goes to PAGE_UPDATE_MODE', () => {
    const s = transition(stateWithSnapshots(true), { type: 'SELECT_ACTION', action: 'update' });
    expect(s.page).toBe('PAGE_UPDATE_MODE');
    expect(s.action).toBe('update');
  });
```

- [ ] **Step 2: 在新測試檔寫分岔 reducer 的失敗測試**

新建 `tests/wizard-update-flow.test.js`：

```javascript
import { describe, it, expect } from 'vitest';
import { getInitialState, transition } from '../js/ui-wizard.js';

function atUpdateMode() {
  let s = transition(getInitialState(), {
    type: 'STATUS_LOADED', hasSnapshots: true, hasApiKey: false,
    projectPath: '/p', fileCount: 3,
  });
  return transition(s, { type: 'SELECT_ACTION', action: 'update' });
}

describe('update mode branch', () => {
  it('SELECT_ACTION update lands on PAGE_UPDATE_MODE', () => {
    expect(atUpdateMode().page).toBe('PAGE_UPDATE_MODE');
  });

  it('PICK_REGEN goes to PAGE_REGEN_GUIDE and tags flow=regen', () => {
    const s = transition(atUpdateMode(), { type: 'PICK_REGEN' });
    expect(s.page).toBe('PAGE_REGEN_GUIDE');
    expect(s.updateFlow).toBe('regen');
  });

  it('PICK_NEW_DATA goes to PAGE_NEW_DATA and tags flow=new_data', () => {
    const s = transition(atUpdateMode(), { type: 'PICK_NEW_DATA' });
    expect(s.page).toBe('PAGE_NEW_DATA');
    expect(s.updateFlow).toBe('new_data');
  });
});
```

- [ ] **Step 3: 跑測試確認失敗**

```bash
cd docs/frontend-local-version-viewer/viewer
./node_modules/.bin/vitest.cmd run tests/wizard-update-flow.test.js --reporter=verbose 2>&1 | tail -20
```
Expected: FAIL — 落點仍是 `PAGE_CONFIRM` / `PICK_REGEN` 無對應 case。

- [ ] **Step 4: 改 reducer**

在 `js/ui-wizard.js` 的 `getInitialState` 回傳物件加四個欄位（接在 `errorOriginPage: null,` 後）：

```javascript
    updateFlow: null,
    regenRef: null,
    newDataPath: '',
    baselineRef: null,
```

把 `transition` 的 `SELECT_ACTION` case 改成：

```javascript
    case 'SELECT_ACTION': {
      const nextPage =
        action.action === 'analyze' ? 'PAGE_SETUP' :
        action.action === 'update'  ? 'PAGE_UPDATE_MODE' :
        state.page;
      return { ...state, page: nextPage, action: action.action };
    }
```

在 `SELECT_ACTION` case 後面新增兩個 case：

```javascript
    case 'PICK_REGEN':
      return { ...state, page: 'PAGE_REGEN_GUIDE', updateFlow: 'regen' };

    case 'PICK_NEW_DATA':
      return { ...state, page: 'PAGE_NEW_DATA', updateFlow: 'new_data' };
```

- [ ] **Step 5: 跑測試確認通過**

```bash
./node_modules/.bin/vitest.cmd run tests/wizard-update-flow.test.js tests/ui-wizard.test.js --reporter=verbose 2>&1 | tail -20
```
Expected: PASS（新檔 3 case + 改過的 update 斷言）。

- [ ] **Step 6: 寫分岔頁 render 的失敗測試**

在 `tests/wizard-update-flow.test.js` append：

```javascript
import { renderPage } from '../js/ui-wizard.js';

describe('PAGE_UPDATE_MODE render', () => {
  function render(state) {
    const container = document.createElement('div');
    renderPage(container, state, () => {}, () => {}, {});
    return container;
  }
  it('shows two option buttons: regen and new-data', () => {
    const c = render({ ...getInitialState(), page: 'PAGE_UPDATE_MODE', hasSnapshots: true });
    expect(c.querySelector('[data-pick="regen"]')).not.toBeNull();
    expect(c.querySelector('[data-pick="new-data"]')).not.toBeNull();
  });
});
```

- [ ] **Step 7: 跑測試確認失敗**

```bash
./node_modules/.bin/vitest.cmd run tests/wizard-update-flow.test.js -t "PAGE_UPDATE_MODE render" --reporter=verbose 2>&1 | tail -15
```
Expected: FAIL — 兩個 `[data-pick]` 都找不到（renderPage 無此 case）。

- [ ] **Step 8: 實作 `PAGE_UPDATE_MODE` 的 render case**

在 `renderPage` 的 switch（`case 'PAGE_ACTION':` 之後、`case 'PAGE_SETUP':` 之前）插入：

```javascript
    case 'PAGE_UPDATE_MODE': {
      wrap.innerHTML = `
        <p class="wizard-eyebrow eyebrow">步驟 / 更新方式</p>
        <h2>這次要怎麼更新？</h2>
        <p class="wizard-subtitle lede">選擇要重生既有版本的解析，還是引入一份新版本資料來比對差異。</p>
        <div class="wizard-options opts">
          <button class="wizard-option-btn opt" data-pick="regen">
            <span class="ico">${I.refresh}</span>
            <span class="tx"><strong>重生現有版本的解析</strong><span>不換原始碼，拿既有快照重跑自然語言解析。</span></span>
            ${I.arrow}
          </button>
          <button class="wizard-option-btn opt" data-pick="new-data">
            <span class="ico">${I.scan}</span>
            <span class="tx"><strong>引入新資料</strong><span>指向一份新下載的版本資料夾，比對它跟既有版本的差異。</span></span>
            ${I.arrow}
          </button>
        </div>
      `;
      wrap.querySelector('[data-pick="regen"]').addEventListener('click',
        () => dispatch({ type: 'PICK_REGEN' }));
      wrap.querySelector('[data-pick="new-data"]').addEventListener('click',
        () => dispatch({ type: 'PICK_NEW_DATA' }));
      break;
    }
```

> `I.refresh` / `I.scan` / `I.arrow` 是既有 icon library（檔案上方 `const I = {...}`），已存在，直接用。

- [ ] **Step 9: 跑測試確認通過 + 全套不退步**

```bash
./node_modules/.bin/vitest.cmd run tests/wizard-update-flow.test.js --reporter=verbose 2>&1 | tail -15
./node_modules/.bin/vitest.cmd run 2>&1 | tail -6
```
Expected: 新檔全綠；全套維持 853 passed（改了 1 條既有斷言但數量不變）+ 8 pre-existing failures。

- [ ] **Step 10: Commit**

```bash
git add docs/frontend-local-version-viewer/viewer/js/ui-wizard.js docs/frontend-local-version-viewer/viewer/tests/
git commit -m "feat(wizard): update mode branch page; rewire SELECT_ACTION update"
```

## Done when
- [ ] `update` 進 `PAGE_UPDATE_MODE`（不再直跳 confirm）
- [ ] 分岔頁兩顆按鈕 dispatch `PICK_REGEN` / `PICK_NEW_DATA`
- [ ] 全套不退步
