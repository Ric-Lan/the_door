# Task 5 — PAGE_ACTION mode-note + PAGE_CONFIRM badge

**Goal:** PAGE_ACTION 標題下加 `.wizard-mode-note.api` / `.wizard-mode-note.agent`（依 `hasApiKey`）；PAGE_CONFIRM summary 加執行模式 badge（與入口一致）；PAGE_ACTION 前加 `.wizard-eyebrow`「步驟 1 / 開始」。

**Dependencies:** task 4（renderPage shell）+ task 3（mode-note CSS）。

**Files:**
- Modify: `docs/frontend-local-version-viewer/viewer/js/ui-wizard.js`（PAGE_ACTION / PAGE_CONFIRM cases）
- Modify: `docs/frontend-local-version-viewer/viewer/tests/ui-wizard.test.js`（補斷言）

---

- [ ] **Step 1: Failing tests**

Append to `docs/frontend-local-version-viewer/viewer/tests/ui-wizard.test.js`:

```js
describe('PAGE_ACTION mode-note (spec §4.2 ⓐ)', () => {
  function mount(hasApiKey, hasSnapshots) {
    const c = document.createElement('div');
    renderPage(c, { ...getInitialState(), page: 'PAGE_ACTION', hasApiKey, hasSnapshots },
      () => {}, () => {}, { setProject: () => Promise.resolve({}) });
    return c;
  }

  it('renders .wizard-eyebrow with step 1 label', () => {
    const c = mount(true, false);
    const eb = c.querySelector('.wizard-eyebrow');
    expect(eb).not.toBeNull();
    expect(eb.textContent).toMatch(/步驟 1/);
  });

  it('renders .wizard-mode-note.api when hasApiKey=true', () => {
    const c = mount(true, false);
    const n = c.querySelector('.wizard-mode-note');
    expect(n).not.toBeNull();
    expect(n.classList.contains('api')).toBe(true);
    expect(n.classList.contains('agent')).toBe(false);
    expect(n.querySelector('.mn-badge').textContent).toMatch(/API/);
  });

  it('renders .wizard-mode-note.agent when hasApiKey=false', () => {
    const c = mount(false, false);
    const n = c.querySelector('.wizard-mode-note');
    expect(n.classList.contains('agent')).toBe(true);
    expect(n.classList.contains('api')).toBe(false);
    expect(n.querySelector('.mn-badge').textContent).toMatch(/Agent/);
  });

  it('mode-note appears in both has_snapshots=true and =false branches', () => {
    expect(mount(true, true).querySelector('.wizard-mode-note')).not.toBeNull();
    expect(mount(true, false).querySelector('.wizard-mode-note')).not.toBeNull();
  });
});

describe('PAGE_CONFIRM mode badge (spec §4.2 ⓓ)', () => {
  function mount(hasApiKey) {
    const c = document.createElement('div');
    renderPage(c, { ...getInitialState(), page: 'PAGE_CONFIRM', hasApiKey, action: 'analyze' },
      () => {}, () => {}, {});
    return c;
  }
  it('badge has .wizard-mode-badge.api when hasApiKey=true', () => {
    const c = mount(true);
    const b = c.querySelector('.wizard-mode-badge');
    expect(b).not.toBeNull();
    expect(b.classList.contains('api')).toBe(true);
    expect(b.textContent).toMatch(/API/);
  });
  it('badge has .wizard-mode-badge.agent when hasApiKey=false', () => {
    const c = mount(false);
    const b = c.querySelector('.wizard-mode-badge');
    expect(b.classList.contains('agent')).toBe(true);
    expect(b.textContent).toMatch(/Agent/);
  });
});
```

- [ ] **Step 2: Run, verify FAIL**

```bash
cd docs/frontend-local-version-viewer/viewer
npm test -- tests/ui-wizard.test.js -t "mode-note|mode badge"
```

- [ ] **Step 3: Patch PAGE_ACTION case in ui-wizard.js**

In `renderPage` `case 'PAGE_ACTION':` block — locate the two `wrap.innerHTML = \`...\`` template literals (one for `!state.hasSnapshots`, one for `state.hasSnapshots`). Inside each template, prepend the eyebrow + mode-note BEFORE the existing `<h2>` line:

```js
const modeNoteCls = state.hasApiKey ? 'api' : 'agent';
const modeBadge   = state.hasApiKey ? '● API key 模式' : '◐ Agent 模式';
const modeText    = state.hasApiKey
  ? '偵測到 API key — 分析會在本機自動執行，完成後直接進入 Viewer。'
  : '未偵測到 API key — 將以 Agent 模式產生 MCP 指令，交由你的 coding agent 執行。';
const eyebrowAndNote = `
  <p class="wizard-eyebrow">步驟 1 / 開始</p>
  <div class="wizard-mode-note ${modeNoteCls}">
    <span class="mn-badge">${modeBadge}</span>
    <span>${modeText}</span>
  </div>
`;
```

Then in each branch's `wrap.innerHTML = \`...\``, insert `${eyebrowAndNote}` right after the opening backtick / before `<h2>`. Keep all other existing content (options, switch-section) intact.

- [ ] **Step 4: Patch PAGE_CONFIRM case**

In `case 'PAGE_CONFIRM': {` block, replace the existing `wrap.innerHTML = \`...\`` with:

```js
const apiOn = state.hasApiKey;
const badgeCls = apiOn ? 'api' : 'agent';
const badgeText = apiOn ? '● API key 模式' : '◐ Agent 模式（無 API key）';
wrap.innerHTML = `
  <h2>確認送出</h2>
  <dl class="wizard-summary">
    <dt>操作</dt><dd>${state.action}</dd>
    <dt>執行模式</dt><dd><span class="wizard-mode-badge ${badgeCls}">${badgeText}</span></dd>
  </dl>
  <button class="wizard-btn-primary" data-submit>確認送出</button>
`;
```

(Existing `data-submit` listener wiring stays the same — `wrap.querySelector('[data-submit]').addEventListener(...)`.)

- [ ] **Step 5: Add `.wizard-mode-badge` CSS to wizard.css**

Append to `docs/frontend-local-version-viewer/viewer/wizard.css`:

```css
.wizard-mode-badge {
  display: inline-flex; align-items: center; gap: 6px;
  font-size: 12px; font-weight: 600;
  padding: 3px 10px;
  border-radius: 999px;
}
.wizard-mode-badge.api { background: var(--accent-soft); color: var(--accent-press); }
.wizard-mode-badge.agent { background: var(--warn-bg); color: var(--warn); }
```

- [ ] **Step 6: Run tests, verify PASS**

```bash
npm test -- tests/ui-wizard.test.js
```
Expected: all original + 6 new pass.

- [ ] **Step 7: Coverage check on `renderPage` cases**

```bash
npm run test:coverage -- tests/ui-wizard.test.js
```
Expected: `ui-wizard.js` PAGE_ACTION / PAGE_CONFIRM branches 100% covered (incl. both hasApiKey true/false + both hasSnapshots branches).

- [ ] **Step 8: Commit**

```bash
git add docs/frontend-local-version-viewer/viewer/js/ui-wizard.js \
        docs/frontend-local-version-viewer/viewer/wizard.css \
        docs/frontend-local-version-viewer/viewer/tests/ui-wizard.test.js
git commit -m "feat(wizard): PAGE_ACTION eyebrow + mode-note, PAGE_CONFIRM mode badge

PAGE_ACTION 加 .wizard-eyebrow「步驟 1 / 開始」+ .wizard-mode-note 依 hasApiKey
顯示 api (teal) / agent (warn) 變體。PAGE_CONFIRM summary 加 .wizard-mode-badge
與入口一致。新 .wizard-mode-badge CSS 進 wizard.css。spec §4.2 ⓐ/ⓓ。

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```
