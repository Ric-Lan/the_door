# Task 4 — renderPage dual-pane shell + errorOriginPage state + wizardRailHTML

**Goal:** `ui-wizard.js renderPage` 改為先建 `.wizard-shell`（左 rail 右 content）外殼、再把當前 page 內容塞進 `.wizard-screen`；新增 `errorOriginPage` 到 state；移除 `wizard.html` body 內 `.wizard-root` 包裝。

**Dependencies:** task 3（DOM 依賴 `.wizard-shell` / `.wizard-rail*` CSS）。

**Files:**
- Modify: `docs/frontend-local-version-viewer/viewer/wizard.html`（body 結構）
- Modify: `docs/frontend-local-version-viewer/viewer/styles.css`（加 `html,body,#wizard-mount` 全高規則）
- Modify: `docs/frontend-local-version-viewer/viewer/js/ui-wizard.js`（`getInitialState`、`transition`、`renderPage`、新增 `wizardRailHTML` / `railStage`）
- Create: `docs/frontend-local-version-viewer/viewer/tests/wizard-shell.test.js`
- Create: `docs/frontend-local-version-viewer/viewer/tests/wizard-error-origin.test.js`
- Modify (preserve green): `docs/frontend-local-version-viewer/viewer/tests/ui-wizard.test.js`

---

- [ ] **Step 1: Failing tests for shell structure**

Path: `docs/frontend-local-version-viewer/viewer/tests/wizard-shell.test.js`

```js
import { describe, it, expect, beforeEach } from 'vitest';
import { renderPage, getInitialState } from '../js/ui-wizard.js';

function noopDispatch() {}
function noopRedirect() {}
const stubApi = {
  getStatus: () => Promise.resolve({}),
  postAnalyze: () => Promise.resolve({}),
  getJobStatus: () => Promise.resolve({}),
  setProject: () => Promise.resolve({}),
};

function mount(state) {
  const c = document.createElement('div');
  document.body.appendChild(c);
  renderPage(c, state, noopDispatch, noopRedirect, stubApi);
  return c;
}

describe('renderPage shell (spec §4.1)', () => {
  beforeEach(() => { document.body.innerHTML = ''; });

  it('renders .wizard-shell at root for PAGE_ACTION', () => {
    const c = mount({ ...getInitialState(), page: 'PAGE_ACTION', hasApiKey: true });
    expect(c.querySelector('.wizard-shell')).not.toBeNull();
    expect(c.querySelector('.wizard-shell .wizard-rail')).not.toBeNull();
    expect(c.querySelector('.wizard-shell .wizard-content')).not.toBeNull();
    expect(c.querySelector('.wizard-shell .wizard-content .wizard-screen')).not.toBeNull();
  });

  it('places existing .wizard-card inside .wizard-screen', () => {
    const c = mount({ ...getInitialState(), page: 'PAGE_ACTION', hasApiKey: true });
    expect(c.querySelector('.wizard-screen .wizard-card')).not.toBeNull();
  });

  it('rail stepper has 6 .wizard-step items', () => {
    const c = mount({ ...getInitialState(), page: 'PAGE_SETUP' });
    expect(c.querySelectorAll('.wizard-stepper .wizard-step').length).toBe(6);
  });

  it('rail stage maps: PAGE_ACTION → 0', () => {
    const c = mount({ ...getInitialState(), page: 'PAGE_ACTION', hasApiKey: true });
    const fill = c.querySelector('.wizard-stepper-fill');
    expect(fill).not.toBeNull();
    expect(fill.style.height).toMatch(/0%|calc\(0/);
  });

  it('rail stage maps: PAGE_SETUP → 1 → height = 20%', () => {
    const c = mount({ ...getInitialState(), page: 'PAGE_SETUP' });
    const fill = c.querySelector('.wizard-stepper-fill');
    expect(fill.style.height).toMatch(/20%|calc\(20/);
  });

  it('rail stage maps: PROGRESS → 4 → height = 80%', () => {
    const c = mount({ ...getInitialState(), page: 'PROGRESS', hasApiKey: true });
    const fill = c.querySelector('.wizard-stepper-fill');
    expect(fill.style.height).toMatch(/80%|calc\(80/);
  });

  it('door-light lit only when PROGRESS + status completed', () => {
    const c1 = mount({ ...getInitialState(), page: 'PROGRESS', status: 'running' });
    expect(c1.querySelector('.wizard-door-light').classList.contains('lit')).toBe(false);
    document.body.innerHTML = '';
    const c2 = mount({ ...getInitialState(), page: 'PROGRESS', status: 'completed' });
    expect(c2.querySelector('.wizard-door-light').classList.contains('lit')).toBe(true);
  });

  it('screen has data-page attribute matching current page', () => {
    const c = mount({ ...getInitialState(), page: 'PAGE_CONFIRM', hasApiKey: true, action: 'analyze' });
    expect(c.querySelector('.wizard-screen').getAttribute('data-page')).toBe('PAGE_CONFIRM');
  });
});
```

- [ ] **Step 2: Failing tests for errorOriginPage**

Path: `docs/frontend-local-version-viewer/viewer/tests/wizard-error-origin.test.js`

```js
import { describe, it, expect } from 'vitest';
import { getInitialState, transition } from '../js/ui-wizard.js';

describe('errorOriginPage (spec §4.1)', () => {
  it('getInitialState includes errorOriginPage: null', () => {
    expect(getInitialState().errorOriginPage).toBeNull();
  });

  it('STATUS_ERROR from LOADING records errorOriginPage=LOADING', () => {
    const s = transition({ ...getInitialState(), page: 'LOADING' },
      { type: 'STATUS_ERROR', message: 'boom' });
    expect(s.page).toBe('PAGE_ERROR');
    expect(s.errorOriginPage).toBe('LOADING');
  });

  it('SUBMIT_ERROR from PAGE_CONFIRM records errorOriginPage=PAGE_CONFIRM', () => {
    const s = transition({ ...getInitialState(), page: 'PAGE_CONFIRM' },
      { type: 'SUBMIT_ERROR', message: 'boom' });
    expect(s.errorOriginPage).toBe('PAGE_CONFIRM');
  });

  it('POLL_UPDATE failed from PROGRESS records errorOriginPage=PROGRESS', () => {
    const s = transition({ ...getInitialState(), page: 'PROGRESS' },
      { type: 'POLL_UPDATE', status: 'failed', errorMessage: 'boom' });
    expect(s.errorOriginPage).toBe('PROGRESS');
  });

  it('POLL_FAIL ≥3 from PROGRESS records errorOriginPage=PROGRESS', () => {
    let s = { ...getInitialState(), page: 'PROGRESS', pollFailCount: 2 };
    s = transition(s, { type: 'POLL_FAIL' });
    expect(s.page).toBe('PAGE_ERROR');
    expect(s.errorOriginPage).toBe('PROGRESS');
  });

  it('POLL_FAIL <3 does not change page or errorOriginPage', () => {
    let s = { ...getInitialState(), page: 'PROGRESS', pollFailCount: 0 };
    s = transition(s, { type: 'POLL_FAIL' });
    expect(s.page).toBe('PROGRESS');
    expect(s.errorOriginPage).toBeNull();
  });
});
```

- [ ] **Step 3: Run new tests, verify FAIL**

```bash
cd docs/frontend-local-version-viewer/viewer
npm test -- tests/wizard-shell.test.js tests/wizard-error-origin.test.js
```
Expected: all fail.

- [ ] **Step 4: Add `errorOriginPage` to state machine**

Modify `docs/frontend-local-version-viewer/viewer/js/ui-wizard.js`:

In `getInitialState()` add `errorOriginPage: null,` before closing `}`.

In `transition`:
- `STATUS_ERROR` case: add `errorOriginPage: state.page` to returned object
- `SUBMIT_ERROR` case: same
- `POLL_UPDATE` `failed` branch: same
- `POLL_FAIL` `newCount >= 3` branch: change return to include `errorOriginPage: state.page`

- [ ] **Step 5: Add `wizardRailHTML` + `railStage` + new `renderPage`**

In `ui-wizard.js`, before `export function renderPage(...)`, add:

```js
// ─── Rail HTML (spec §4.1) ────────────────────────────────────────────────
const STAGE = {
  LOADING: 0, PAGE_ACTION: 0,
  PAGE_SETUP: 1, PAGE_LABEL: 2, PAGE_CONFIRM: 3,
  SUBMITTING: 4, PROGRESS: 4,
};
const STAGE_LABELS = ['選擇操作', '設定範圍', '快照標籤', '確認送出', '分析中', '進入 Viewer'];

export function railStage(state) {
  if (state.page === 'PAGE_ERROR') return STAGE[state.errorOriginPage] ?? 0;
  return STAGE[state.page] ?? 0;
}

const DOOR_SVG = `
  <svg class="leaf" viewBox="0 0 100 100" fill="none" aria-label="The Door">
    <rect x="22" y="10" width="56" height="76" fill="#d9f3ef"></rect>
    <path d="M22 10 L22 86 M78 10 L78 86 M22 10 L78 10" stroke="#0f766e" stroke-width="6"></path>
    <line x1="10" y1="90" x2="90" y2="90" stroke="#0f766e" stroke-width="6"></line>
    <circle cx="70" cy="50" r="2.5" fill="#0f766e"></circle>
  </svg>`;

export function wizardRailHTML(stage, lit) {
  const frac = Math.min(stage, 5) / 5;
  const angle = -(78 * frac);
  const fillH = `${frac * 100}%`;
  const steps = STAGE_LABELS.map((label, i) => {
    const cls = i < stage ? 'done' : i === stage ? 'active' : '';
    const icon = i < stage ? '✓' : String(i + 1);
    return `<div class="wizard-step ${cls}"><span class="dot">${icon}</span><span class="lbl">${label}</span></div>`;
  }).join('');
  return `
    <div class="wizard-rail">
      <div class="wizard-rail-brand">${DOOR_SVG}<div><div class="wd">The Door</div><div class="sub">門 · 啟動精靈</div></div></div>
      <div class="wizard-door-wrap">
        <svg class="wizard-door-frame" viewBox="0 0 148 188" fill="none">
          <path d="M12 8 L12 182 M136 8 L136 182 M12 8 L136 8" stroke="rgba(217,243,239,0.6)" stroke-width="3"></path>
          <line x1="4" y1="184" x2="144" y2="184" stroke="rgba(217,243,239,0.6)" stroke-width="3.5"></line>
        </svg>
        <div class="wizard-door-light${lit ? ' lit' : ''}"></div>
        <div class="wizard-door-leaf" style="transform:rotateY(${angle}deg)"><span class="grain"></span><span class="knob"></span></div>
        <div class="wizard-door-pct">${lit ? '已開啟' : '開啟 ' + Math.round(frac * 100) + '%'}</div>
      </div>
      <div class="wizard-stepper">
        <div class="wizard-stepper-line"></div>
        <div class="wizard-stepper-fill" style="height:${fillH}"></div>
        ${steps}
      </div>
      <div class="wizard-rail-foot">CODE → FUNCTIONAL LANGUAGE</div>
    </div>`;
}
```

Now refactor `renderPage` to wrap existing `wrap = wizard-card` inside the shell:

```js
export function renderPage(container, state, dispatch, redirectFn, api) {
  container.innerHTML = '';

  // Build shell
  const shell = document.createElement('div');
  shell.className = 'wizard-shell';
  const lit = state.page === 'PROGRESS' && state.status === 'completed';
  shell.insertAdjacentHTML('beforeend', wizardRailHTML(railStage(state), lit));

  const content = document.createElement('div');
  content.className = 'wizard-content';
  const screen = document.createElement('div');
  screen.className = 'wizard-screen wizard-screen-enter';
  screen.setAttribute('data-page', state.page);
  content.appendChild(screen);
  shell.appendChild(content);
  container.appendChild(shell);

  // Build existing wizard-card and slot into screen
  const wrap = document.createElement('div');
  wrap.setAttribute('data-page', state.page);
  wrap.className = 'wizard-card';

  switch (state.page) {
    /* ── KEEP ALL EXISTING CASES UNCHANGED ── */
    /* The body of each case stays exactly as it is today:
       set wrap.innerHTML = ..., attach listeners, etc.
       Only difference: where current code does container.appendChild(wrap)
       at the end, we now do screen.appendChild(wrap). */
  }

  screen.appendChild(wrap);
}
```

Move the existing `container.appendChild(wrap)` (currently end of function) to `screen.appendChild(wrap)`. All switch cases stay identical to current ui-wizard.js (line 154-335) — DO NOT touch their innerHTML or event bindings in this task. Mode-note / badge / phasebar additions are task 5 / 6.

- [ ] **Step 6: Update wizard.html body — remove `.wizard-root` wrapper**

Modify `docs/frontend-local-version-viewer/viewer/wizard.html` lines 10-20:

```html
<body>
  <div id="wizard-mount"></div>
  <script type="module">
    import { initWizard, createApi } from './js/ui-wizard.js';
    const container = document.getElementById('wizard-mount');
    initWizard(container, createApi());
  </script>
</body>
```

(Keep `<head>` untouched — both stylesheet links remain.)

- [ ] **Step 7: Add full-viewport rules to styles.css**

Append to `docs/frontend-local-version-viewer/viewer/styles.css` (before "Pipeline progress" block or alongside Part 2 shared region added in task 2):

```css
/* Part 2 wizard shell viewport (spec §2) */
html, body { height: 100%; margin: 0; }
#wizard-mount { height: 100vh; }
```

- [ ] **Step 8: Run new tests, verify PASS**

```bash
npm test -- tests/wizard-shell.test.js tests/wizard-error-origin.test.js
```
Expected: all pass.

- [ ] **Step 9: Run existing ui-wizard.test.js — confirm FIX-1 baseline preserved**

```bash
npm test -- tests/ui-wizard.test.js
```
Expected: all 14 FIX-1 className 斷言 + originals pass. If any fail because selector now requires `.wizard-shell` ancestor, prepend `.wizard-shell ` to that selector inline in the test (single-line edit per failing assertion).

- [ ] **Step 10: Run full JS suite**

```bash
npm test
```
Expected: all pass.

- [ ] **Step 11: Smoke test in browser**

```bash
the-door ui "C:\Users\Ric\Desktop\test-targets\the-door-v105" --no-browser --port 8765
```
Open http://localhost:8765/wizard.html — verify dual-pane shell renders (rail visible left, content right), no console errors.

- [ ] **Step 12: Commit**

```bash
git add docs/frontend-local-version-viewer/viewer/wizard.html \
        docs/frontend-local-version-viewer/viewer/styles.css \
        docs/frontend-local-version-viewer/viewer/js/ui-wizard.js \
        docs/frontend-local-version-viewer/viewer/tests/wizard-shell.test.js \
        docs/frontend-local-version-viewer/viewer/tests/wizard-error-origin.test.js \
        docs/frontend-local-version-viewer/viewer/tests/ui-wizard.test.js
git commit -m "feat(wizard): dual-pane shell + errorOriginPage state

renderPage 包進 .wizard-shell（左 .wizard-rail + 右 .wizard-content .wizard-screen），
新增 wizardRailHTML / railStage / STAGE map（PAGE_ERROR 不在表內、由 railStage 用
errorOriginPage 推回）。state machine 在 STATUS_ERROR / SUBMIT_ERROR / POLL_*
進入 PAGE_ERROR 時補記 errorOriginPage。wizard.html 移除 .wizard-root wrapper。

spec §2 / §4.1 / §4.3。FIX-1 既有 className 斷言保留。

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```
