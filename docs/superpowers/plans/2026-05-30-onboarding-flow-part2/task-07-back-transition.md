# Task 7 — 通用化 BACK transition + 上一步 buttons

**Goal:** state machine 新增單一通用化 `BACK` action（`target` 由按鈕傳入）；PAGE_SETUP / PAGE_LABEL / PAGE_CONFIRM 三處加 `.wizard-btn-ghost`「← 上一步」鈕；analyze 與 update 兩條路徑都覆蓋。

**Dependencies:** task 4（state machine + renderPage shell）。

**Files:**
- Modify: `docs/frontend-local-version-viewer/viewer/js/ui-wizard.js`（`transition` 加 BACK case；PAGE_SETUP / PAGE_LABEL / PAGE_CONFIRM 加上一步鈕 + dispatch 綁定）
- Create: `docs/frontend-local-version-viewer/viewer/tests/wizard-back-action.test.js`

---

- [ ] **Step 1: Failing tests for BACK transition**

Path: `docs/frontend-local-version-viewer/viewer/tests/wizard-back-action.test.js`

```js
import { describe, it, expect, beforeEach } from 'vitest';
import { getInitialState, transition, renderPage } from '../js/ui-wizard.js';

describe('BACK transition (spec §4.3)', () => {
  it('returns to target page, preserves other state', () => {
    const before = {
      ...getInitialState(),
      page: 'PAGE_LABEL',
      action: 'analyze',
      excludesRaw: 'tests/',
      label: 'v1.0.0',
      fileCount: 42,
    };
    const after = transition(before, { type: 'BACK', target: 'PAGE_SETUP' });
    expect(after.page).toBe('PAGE_SETUP');
    expect(after.action).toBe('analyze');
    expect(after.excludesRaw).toBe('tests/');
    expect(after.label).toBe('v1.0.0');
    expect(after.fileCount).toBe(42);
  });

  it('BACK to PAGE_ACTION from PAGE_SETUP', () => {
    const s = transition({ ...getInitialState(), page: 'PAGE_SETUP' },
      { type: 'BACK', target: 'PAGE_ACTION' });
    expect(s.page).toBe('PAGE_ACTION');
  });

  it('BACK to PAGE_LABEL from PAGE_CONFIRM (analyze path)', () => {
    const s = transition({ ...getInitialState(), page: 'PAGE_CONFIRM', action: 'analyze' },
      { type: 'BACK', target: 'PAGE_LABEL' });
    expect(s.page).toBe('PAGE_LABEL');
  });

  it('BACK to PAGE_ACTION from PAGE_CONFIRM (update path)', () => {
    const s = transition({ ...getInitialState(), page: 'PAGE_CONFIRM', action: 'update' },
      { type: 'BACK', target: 'PAGE_ACTION' });
    expect(s.page).toBe('PAGE_ACTION');
  });

  it('unknown target still sets page (caller responsibility)', () => {
    // We allow any string target; validation is at button binding time.
    const s = transition(getInitialState(), { type: 'BACK', target: 'FOO' });
    expect(s.page).toBe('FOO');
  });
});

describe('上一步 button bindings (spec §4.2 ⓑ/ⓓ)', () => {
  beforeEach(() => { document.body.innerHTML = ''; });

  function mount(state) {
    const c = document.createElement('div');
    document.body.appendChild(c);
    const actions = [];
    const dispatch = (a) => actions.push(a);
    renderPage(c, { ...getInitialState(), ...state }, dispatch, () => {}, {});
    return { c, actions };
  }

  it('PAGE_SETUP has .wizard-btn-ghost → dispatches BACK target=PAGE_ACTION', () => {
    const { c, actions } = mount({ page: 'PAGE_SETUP' });
    const btn = c.querySelector('.wizard-btn-ghost');
    expect(btn).not.toBeNull();
    btn.click();
    expect(actions).toContainEqual({ type: 'BACK', target: 'PAGE_ACTION' });
  });

  it('PAGE_LABEL has .wizard-btn-ghost → dispatches BACK target=PAGE_SETUP', () => {
    const { c, actions } = mount({ page: 'PAGE_LABEL' });
    c.querySelector('.wizard-btn-ghost').click();
    expect(actions).toContainEqual({ type: 'BACK', target: 'PAGE_SETUP' });
  });

  it('PAGE_CONFIRM analyze path → BACK target=PAGE_LABEL', () => {
    const { c, actions } = mount({ page: 'PAGE_CONFIRM', action: 'analyze' });
    c.querySelector('.wizard-btn-ghost').click();
    expect(actions).toContainEqual({ type: 'BACK', target: 'PAGE_LABEL' });
  });

  it('PAGE_CONFIRM update path → BACK target=PAGE_ACTION', () => {
    const { c, actions } = mount({ page: 'PAGE_CONFIRM', action: 'update' });
    c.querySelector('.wizard-btn-ghost').click();
    expect(actions).toContainEqual({ type: 'BACK', target: 'PAGE_ACTION' });
  });
});
```

- [ ] **Step 2: Run, verify FAIL**

```bash
cd docs/frontend-local-version-viewer/viewer
npm test -- tests/wizard-back-action.test.js
```

- [ ] **Step 3: Add BACK case to `transition`**

Modify `docs/frontend-local-version-viewer/viewer/js/ui-wizard.js` — in `switch (action.type) {` block, add before `default:`:

```js
case 'BACK':
  return { ...state, page: action.target };
```

- [ ] **Step 4: Add 上一步 buttons to PAGE_SETUP / PAGE_LABEL / PAGE_CONFIRM**

In `renderPage`:

**共用 BACK listener wiring**：定義在 `renderPage` 函式內、`switch` 之前（renderer-side 單一定義；下面三 case 都呼叫）：

```js
const bindBack = (root) => {
  const btn = root.querySelector('[data-back]');
  if (!btn) return;
  btn.addEventListener('click', () =>
    dispatch({ type: 'BACK', target: btn.getAttribute('data-back') }));
};
```

**PAGE_SETUP** case — 整個 case block 改為：

```js
case 'PAGE_SETUP': {
  wrap.innerHTML = `
    <h2>設定分析範圍</h2>
    <p class="wizard-subtitle">偵測到 ${state.fileCount} 個源碼檔案。</p>
    <div class="wizard-field">
      <label>排除目錄（逗號分隔，選填）</label>
      <input type="text" data-excludes placeholder="tests/, docs/" value="${state.excludesRaw}">
    </div>
    <div style="display:flex;gap:12px;margin-top:20px;">
      <button class="wizard-btn-ghost" data-back="PAGE_ACTION">← 上一步</button>
      <button class="wizard-btn-primary" data-next="setup">下一步</button>
    </div>
  `;
  wrap.querySelector('[data-next="setup"]').addEventListener('click', () => {
    const raw = wrap.querySelector('[data-excludes]').value;
    dispatch({ type: 'NEXT_FROM_SETUP', excludesRaw: raw });
  });
  bindBack(wrap);
  break;
}
```

**PAGE_LABEL** case — 整個 case block 改為：

```js
case 'PAGE_LABEL': {
  wrap.innerHTML = `
    <h2>快照標籤</h2>
    <div class="wizard-field">
      <label>版本標籤（選填）</label>
      <input type="text" data-label placeholder="v1.0.0" value="${state.label}">
    </div>
    <div style="display:flex;gap:12px;margin-top:20px;">
      <button class="wizard-btn-ghost" data-back="PAGE_SETUP">← 上一步</button>
      <button class="wizard-btn-primary" data-next="label">下一步</button>
    </div>
  `;
  wrap.querySelector('[data-next="label"]').addEventListener('click', () => {
    const lbl = wrap.querySelector('[data-label]').value;
    dispatch({ type: 'NEXT_FROM_LABEL', label: lbl });
  });
  bindBack(wrap);
  break;
}
```

**PAGE_CONFIRM** case — **完整重寫**（含 mode badge 變數定義，覆蓋 task 5 寫的版本；self-contained，不依賴外部 scope）：

```js
case 'PAGE_CONFIRM': {
  const apiOn = state.hasApiKey;
  const badgeCls = apiOn ? 'api' : 'agent';
  const badgeText = apiOn ? '● API key 模式' : '◐ Agent 模式（無 API key）';
  const backTarget = state.action === 'update' ? 'PAGE_ACTION' : 'PAGE_LABEL';
  wrap.innerHTML = `
    <h2>確認送出</h2>
    <dl class="wizard-summary">
      <dt>操作</dt><dd>${state.action}</dd>
      <dt>執行模式</dt><dd><span class="wizard-mode-badge ${badgeCls}">${badgeText}</span></dd>
    </dl>
    <div style="display:flex;gap:12px;margin-top:20px;">
      <button class="wizard-btn-ghost" data-back="${backTarget}">← 上一步</button>
      <button class="wizard-btn-primary" data-submit>確認送出</button>
    </div>
  `;
  wrap.querySelector('[data-submit]').addEventListener('click', () => dispatch({ type: 'SUBMIT' }));
  bindBack(wrap);
  break;
}
```

- [ ] **Step 5: Run task 7 tests, verify PASS**

```bash
npm test -- tests/wizard-back-action.test.js
```
Expected: 9 pass.

- [ ] **Step 6: Run existing ui-wizard.test.js — no regression**

```bash
npm test -- tests/ui-wizard.test.js
```
If any FIX-1 NEXT button test fails because new markup wraps button in extra div, adjust selectors with closer-scoped queries (`querySelector('[data-next]')` still works).

- [ ] **Step 7: Full suite + coverage**

```bash
npm test
npm run test:coverage -- tests/wizard-back-action.test.js
```
Expected: 100% on `transition` BACK case + 3 button binding paths.

- [ ] **Step 8: Commit**

```bash
git add docs/frontend-local-version-viewer/viewer/js/ui-wizard.js \
        docs/frontend-local-version-viewer/viewer/tests/wizard-back-action.test.js
git commit -m "feat(wizard): 通用化 BACK transition + 上一步 buttons

state machine 新增單一 BACK action（{ type, target }）。PAGE_SETUP / PAGE_LABEL
/ PAGE_CONFIRM 三處加 .wizard-btn-ghost「← 上一步」鈕；PAGE_CONFIRM 依
state.action 決定 target（analyze→PAGE_LABEL, update→PAGE_ACTION）。spec §4.3。

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```
