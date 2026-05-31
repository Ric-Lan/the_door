# Task 06 — B 路：建立新版本指示頁（snapshot_write）+ rail 階段

**內容分類：** B 分支「當版本」第一站。出**會寫快照**的指令（非純結構 diff），按下一步進偵測頁。順帶補 rail 階段對應。

**設計來源：** spec §4.6、§3.2、§10.9。

**Files:**
- Modify: `docs/frontend-local-version-viewer/viewer/js/ui-wizard.js`（`transition` 加 `NEXT_FROM_VERSION_GUIDE`；`renderPage` 加 `PAGE_VERSION_GUIDE`；`STAGE` map 補新頁）
- Test: `docs/frontend-local-version-viewer/viewer/tests/wizard-update-flow.test.js`（append）

---

- [ ] **Step 1: 寫 reducer 失敗測試**

append：

```javascript
describe('version guide reducer', () => {
  it('NEXT_FROM_VERSION_GUIDE advances to PAGE_VERSION_DETECT', () => {
    const s = transition(
      { ...getInitialState(), page: 'PAGE_VERSION_GUIDE', updateFlow: 'new_data',
        newDataPath: '/d/v2', baselineRef: 'v1.2.2' },
      { type: 'NEXT_FROM_VERSION_GUIDE' });
    expect(s.page).toBe('PAGE_VERSION_DETECT');
  });
});
```

- [ ] **Step 2: 跑測試確認失敗**

```bash
cd docs/frontend-local-version-viewer/viewer
./node_modules/.bin/vitest.cmd run tests/wizard-update-flow.test.js -t "version guide reducer" --reporter=verbose 2>&1 | tail -12
```
Expected: FAIL。

- [ ] **Step 3: 加 reducer case**

`transition` 內，`DECIDE_NEWPROJECT` case 後加：

```javascript
    case 'NEXT_FROM_VERSION_GUIDE':
      return { ...state, page: 'PAGE_VERSION_DETECT' };
```

- [ ] **Step 4: 寫版本指示頁 render 失敗測試**

append：

```javascript
describe('PAGE_VERSION_GUIDE render', () => {
  function render(state, dispatch = () => {}) {
    const c = document.createElement('div');
    renderPage(c, state, dispatch, () => {}, {});
    return c;
  }
  it('shows a snapshot_write command embedding baseline and new path', () => {
    const c = render({ ...getInitialState(), page: 'PAGE_VERSION_GUIDE',
      updateFlow: 'new_data', newDataPath: '/d/v2', baselineRef: 'v1.2.2' });
    const cmd = c.querySelector('[data-version-cmd]');
    expect(cmd).not.toBeNull();
    expect(cmd.textContent).toContain('snapshot_write');
    expect(cmd.textContent).toContain('inherit_from="v1.2.2"');
    expect(cmd.textContent).toContain('/d/v2');
  });
  it('typing a new label updates the command text live', () => {
    const c = render({ ...getInitialState(), page: 'PAGE_VERSION_GUIDE',
      updateFlow: 'new_data', newDataPath: '/d/v2', baselineRef: 'v1.2.2' });
    const input = c.querySelector('[data-version-label]');
    input.value = 'v1.3.0';
    input.dispatchEvent(new Event('input'));
    expect(c.querySelector('[data-version-cmd]').textContent).toContain('label="v1.3.0"');
  });
  it('next button dispatches NEXT_FROM_VERSION_GUIDE', () => {
    const calls = [];
    const c = render({ ...getInitialState(), page: 'PAGE_VERSION_GUIDE',
      updateFlow: 'new_data', newDataPath: '/d/v2', baselineRef: 'v1.2.2' },
      a => calls.push(a.type));
    c.querySelector('[data-version-next]').click();
    expect(calls).toContain('NEXT_FROM_VERSION_GUIDE');
  });
});
```

- [ ] **Step 5: 跑測試確認失敗**

```bash
./node_modules/.bin/vitest.cmd run tests/wizard-update-flow.test.js -t "PAGE_VERSION_GUIDE render" --reporter=verbose 2>&1 | tail -15
```
Expected: FAIL。

- [ ] **Step 6: 實作 `PAGE_VERSION_GUIDE` render case**

在 `renderPage` switch（`PAGE_SIMILARITY_DECISION` case 之後）插入：

```javascript
    case 'PAGE_VERSION_GUIDE': {
      const buildCmd = (label) => {
        const labelPart = label ? `, label="${label}"` : '';
        return `extract_structure(codebase_path="${state.newDataPath}")  ` +
          `# 把 nodes 分組成 L1 功能後：\n` +
          `snapshot_write(codebase_path="${state.newDataPath}", l1_features=[...]` +
          `${labelPart}, inherit_from="${state.baselineRef}")`;
      };
      wrap.innerHTML = `
        <p class="wizard-eyebrow eyebrow">步驟 / 建立新版本</p>
        <h2>把新資料寫成新版本快照</h2>
        <p class="wizard-subtitle lede">交給 agent 跑下面指令，會在 store 裡建立一個繼承自基準版本的新快照。這是後面看差異的前提。可選填新版本標籤。</p>
        <div class="wizard-field field">
          <label>新版本標籤（選填）</label>
          <input type="text" data-version-label placeholder="v1.3.0">
        </div>
        <div class="wizard-field field">
          <label>交給 agent 執行的指令</label>
          <pre data-version-cmd>${buildCmd('')}</pre>
        </div>
        <div class="actions">
          <button class="wizard-btn-ghost btn btn-ghost" data-back="PAGE_SIMILARITY_DECISION">← 上一步</button>
          <span class="spacer"></span>
          <button class="wizard-btn-primary btn btn-primary" data-version-next>已建立快照，下一步 ${I.arrow}</button>
        </div>
      `;
      const labelInput = wrap.querySelector('[data-version-label]');
      const cmdPre = wrap.querySelector('[data-version-cmd]');
      labelInput.addEventListener('input', e => { cmdPre.textContent = buildCmd(e.target.value.trim()); });
      wrap.querySelector('[data-version-next]').addEventListener('click',
        () => dispatch({ type: 'NEXT_FROM_VERSION_GUIDE' }));
      bindBack(wrap);
      break;
    }
```

> 指令刻意用 `snapshot_write(inherit_from=...)`（會寫快照），**不是** `update --from-snapshot`
> （那只回傳結構 diff、不寫快照，後面偵測會掃不到）。見 spec §3.2 / §10.9。

- [ ] **Step 7: 跑測試確認通過**

```bash
./node_modules/.bin/vitest.cmd run tests/wizard-update-flow.test.js -t "PAGE_VERSION_GUIDE" --reporter=verbose 2>&1 | tail -12
```
Expected: PASS。

- [ ] **Step 8: 寫 rail 階段失敗測試**

append：

```javascript
import { railStage } from '../js/ui-wizard.js';

describe('railStage for update-flow pages', () => {
  const mk = (page) => ({ ...getInitialState(), page });
  it('maps new pages to non-negative stages', () => {
    expect(railStage(mk('PAGE_UPDATE_MODE'))).toBe(0);
    expect(railStage(mk('PAGE_NEW_DATA'))).toBe(1);
    expect(railStage(mk('PAGE_SIMILARITY_GUIDE'))).toBe(2);
    expect(railStage(mk('PAGE_SIMILARITY_DECISION'))).toBe(3);
    expect(railStage(mk('PAGE_VERSION_GUIDE'))).toBe(4);
    expect(railStage(mk('PAGE_VERSION_DETECT'))).toBe(4);
    expect(railStage(mk('PAGE_TRANSLATE_CHOICE'))).toBe(4);
  });
});
```

- [ ] **Step 9: 跑測試確認失敗**

```bash
./node_modules/.bin/vitest.cmd run tests/wizard-update-flow.test.js -t "railStage for update-flow" --reporter=verbose 2>&1 | tail -12
```
Expected: FAIL — 新頁不在 `STAGE` map，回退 0。

- [ ] **Step 10: 補 `STAGE` map**

把 `js/ui-wizard.js` 的 `const STAGE = {...}` 改成（沿用既有 6 個 label slot，不新增 label）：

```javascript
const STAGE = {
  LOADING: 0, PAGE_ACTION: 0, PAGE_UPDATE_MODE: 0, PAGE_REGEN_GUIDE: 0,
  PAGE_SETUP: 1, PAGE_NEW_DATA: 1,
  PAGE_LABEL: 2, PAGE_SIMILARITY_GUIDE: 2,
  PAGE_CONFIRM: 3, PAGE_SIMILARITY_DECISION: 3,
  SUBMITTING: 4, PROGRESS: 4,
  PAGE_VERSION_GUIDE: 4, PAGE_VERSION_DETECT: 4, PAGE_TRANSLATE_CHOICE: 4,
};
```

> `STAGE_LABELS` 不動——YAGNI。

- [ ] **Step 11: 跑測試確認通過 + 全套不退步**

```bash
./node_modules/.bin/vitest.cmd run tests/wizard-update-flow.test.js --reporter=verbose 2>&1 | tail -15
./node_modules/.bin/vitest.cmd run 2>&1 | tail -6
```
Expected: 新檔全綠；全套 853 passed 不退步。

- [ ] **Step 12: Commit**

```bash
git add docs/frontend-local-version-viewer/viewer/js/ui-wizard.js docs/frontend-local-version-viewer/viewer/tests/wizard-update-flow.test.js
git commit -m "feat(wizard): new-version snapshot_write guide + rail stage mapping"
```

## Done when
- [ ] 版本指示頁出 `snapshot_write(inherit_from=...)` 指令、label 即時更新、下一步進 `PAGE_VERSION_DETECT`
- [ ] 新頁 rail 階段對應正確
- [ ] 全套不退步
