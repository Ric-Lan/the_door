# Task 6 — PROGRESS phasebar + steplist + 即時 feed

**Goal:** PROGRESS（API 模式）case 改為 phasebar + 完整 6-step steplist + 即時 feed；新增 `phaseStatus` 純函式；polling 回呼裡實作 `appendPlLine` 與 `updateCount`；消費 §1b 後端 `progress.*` payload。

**Dependencies:** task 4（shell + state）+ task 1b（payload contract）+ task 2（shared CSS）。

**Files:**
- Create: `docs/frontend-local-version-viewer/viewer/js/phase-status.js`（純函式：phaseStatus / labelFor / PHASE_BUCKETS / STEP_LABELS）
- Create: `docs/frontend-local-version-viewer/viewer/js/progress-view.js`（共用 DOM render：`renderProgressInnerHTML` + `appendPlLine` + `updateProgressCount`；task 8 也 import 使用）
- Modify: `docs/frontend-local-version-viewer/viewer/js/ui-wizard.js`（PROGRESS case 呼叫 progress-view.js + startPolling 內 appendPlLine）
- Create: `docs/frontend-local-version-viewer/viewer/tests/wizard-phasebar.test.js`
- Create: `docs/frontend-local-version-viewer/viewer/tests/wizard-progress-render.test.js`（ui-wizard 整合 smoke；feed/render 細節覆蓋已在 progress-view.test.js）
- Create: `docs/frontend-local-version-viewer/viewer/tests/progress-view.test.js`

---

- [ ] **Step 1: Failing test for phaseStatus pure function**

Path: `docs/frontend-local-version-viewer/viewer/tests/wizard-phasebar.test.js`

```js
import { describe, it, expect } from 'vitest';
import { phaseStatus, PHASE_BUCKETS, STEP_LABELS } from '../js/phase-status.js';

const EXPLORE = PHASE_BUCKETS.find(b => b.id === 'explore');
const ANALYZE = PHASE_BUCKETS.find(b => b.id === 'analyze');
const REPORT  = PHASE_BUCKETS.find(b => b.id === 'report');

describe('PHASE_BUCKETS shape (spec §5.3)', () => {
  it('has 3 buckets explore/analyze/report', () => {
    expect(PHASE_BUCKETS.map(b => b.id)).toEqual(['explore', 'analyze', 'report']);
  });
  it('explore owns analyze_old + analyze_new', () => {
    expect(EXPLORE.steps).toEqual(['analyze_old', 'analyze_new']);
  });
  it('analyze owns diff + scope_verify', () => {
    expect(ANALYZE.steps).toEqual(['diff', 'scope_verify']);
  });
  it('report owns timeline + report', () => {
    expect(REPORT.steps).toEqual(['timeline', 'report']);
  });
});

describe('phaseStatus()', () => {
  it('returns pending when no owned step in list', () => {
    expect(phaseStatus(EXPLORE, [], null)).toBe('pending');
  });

  it('returns active when any owned step is running', () => {
    expect(phaseStatus(EXPLORE,
      [{ step_name: 'analyze_new', status: 'running' }], null)).toBe('active');
  });

  it('returns active when currentStep is in bucket (even if no running)', () => {
    expect(phaseStatus(EXPLORE,
      [{ step_name: 'analyze_new', status: 'pending' }], 'analyze_new')).toBe('active');
  });

  it('returns done when all owned steps completed', () => {
    expect(phaseStatus(REPORT, [
      { step_name: 'timeline', status: 'completed' },
      { step_name: 'report',   status: 'completed' },
    ], null)).toBe('done');
  });

  it('returns done when all owned steps skipped (首次分析 explore bucket)', () => {
    expect(phaseStatus(ANALYZE, [
      { step_name: 'diff',         status: 'skipped' },
      { step_name: 'scope_verify', status: 'skipped' },
    ], null)).toBe('done');
  });

  it('returns done when mix of completed + skipped (首次 explore bucket)', () => {
    expect(phaseStatus(EXPLORE, [
      { step_name: 'analyze_old', status: 'skipped' },
      { step_name: 'analyze_new', status: 'completed' },
    ], null)).toBe('done');
  });

  it('returns failed when any owned step failed (overrides done/active)', () => {
    expect(phaseStatus(REPORT, [
      { step_name: 'timeline', status: 'completed' },
      { step_name: 'report',   status: 'failed' },
    ], null)).toBe('failed');
  });

  it('failed beats running (active) — design原則 1 不可造假進度', () => {
    expect(phaseStatus(EXPLORE, [
      { step_name: 'analyze_old', status: 'failed' },
      { step_name: 'analyze_new', status: 'running' },
    ], 'analyze_new')).toBe('failed');
  });

  it('returns pending when partial completion (missing owned step)', () => {
    expect(phaseStatus(EXPLORE,
      [{ step_name: 'analyze_old', status: 'completed' }], null)).toBe('pending');
  });
});

describe('STEP_LABELS map', () => {
  it('has all 6 canonical step labels', () => {
    expect(Object.keys(STEP_LABELS).sort()).toEqual([
      'analyze_new', 'analyze_old', 'diff', 'report', 'scope_verify', 'timeline',
    ]);
  });
  it('falls back to raw step_name for unknown keys (via labelFor)', () => {
    // labelFor exported alongside
    const { labelFor } = require('../js/phase-status.js'); // eslint-disable-line
    expect(labelFor('mystery_step')).toBe('mystery_step');
  });
});
```

(If `require` not supported in vitest config, use dynamic `import()` or restructure to top-level import.)

- [ ] **Step 2: Run, verify FAIL (module not found)**

```bash
cd docs/frontend-local-version-viewer/viewer
npm test -- tests/wizard-phasebar.test.js
```

- [ ] **Step 3: Implement `phase-status.js`**

Path: `docs/frontend-local-version-viewer/viewer/js/phase-status.js`

```js
// Pure helpers for PROGRESS phasebar (spec §5.3).
// No DOM access — safe for unit tests under jsdom or node.

export const PHASE_BUCKETS = [
  { id: 'explore', label: '探索結構', steps: ['analyze_old', 'analyze_new'] },
  { id: 'analyze', label: '比對與驗核', steps: ['diff', 'scope_verify'] },
  { id: 'report',  label: '產出快照',   steps: ['timeline', 'report'] },
];

export const STEP_LABELS = {
  analyze_old:  '分析舊版',
  analyze_new:  '分析新版',
  diff:         '比對差異',
  scope_verify: '範圍驗核',
  timeline:     '時間軸',
  report:       '產生報告',
};

export function labelFor(step_name) {
  return STEP_LABELS[step_name] ?? step_name;
}

/**
 * Returns 'done' | 'active' | 'pending' | 'failed' for a bucket.
 * 'failed' has highest priority (spec §0.4 第 1 條：不可造假進度).
 */
export function phaseStatus(bucket, steps, currentStep) {
  const owned = steps.filter(s => bucket.steps.includes(s.step_name));
  if (owned.length === 0) return 'pending';
  if (owned.some(s => s.status === 'failed')) return 'failed';
  const hasRunning = owned.some(s => s.status === 'running');
  const currentInBucket = currentStep && bucket.steps.includes(currentStep);
  if (hasRunning || currentInBucket) return 'active';
  const allEnded = bucket.steps.every(name => {
    const s = owned.find(x => x.step_name === name);
    return s && (s.status === 'completed' || s.status === 'skipped');
  });
  return allEnded ? 'done' : 'pending';
}
```

- [ ] **Step 4: Run phasebar tests, verify PASS**

```bash
npm test -- tests/wizard-phasebar.test.js
```
Expected: 14 pass.

- [ ] **Step 5: Failing test — ui-wizard PROGRESS integration smoke**

Path: `docs/frontend-local-version-viewer/viewer/tests/wizard-progress-render.test.js`

Detailed DOM-structure assertions live in `progress-view.test.js` (Step 6). 此檔只測 ui-wizard `renderPage('PROGRESS')` 是否確實呼叫共用 render module 並把產出塞進 `.wizard-card`：

```js
import { describe, it, expect, beforeEach } from 'vitest';
import { renderPage, getInitialState } from '../js/ui-wizard.js';

function mountProgress(stateOverrides = {}) {
  const c = document.createElement('div');
  document.body.appendChild(c);
  renderPage(c, {
    ...getInitialState(),
    page: 'PROGRESS',
    hasApiKey: true,
    ...stateOverrides,
  }, () => {}, () => {}, {});
  return c;
}

describe('renderPage PROGRESS integration (spec §4.2 ⓕ)', () => {
  beforeEach(() => { document.body.innerHTML = ''; });

  it('mounts shared progress view inside .wizard-card', () => {
    const c = mountProgress({ steps: [], currentStep: null, progress: null });
    const card = c.querySelector('.wizard-card');
    expect(card).not.toBeNull();
    // smoke: shared module produced the phasebar shell
    expect(card.querySelector('.wizard-phasebar')).not.toBeNull();
    expect(card.querySelector('.wizard-steplist')).not.toBeNull();
  });

  it('agent mode (!hasApiKey) does NOT mount phasebar (terminal block instead)', () => {
    const c = mountProgress({ hasApiKey: false, projectPath: '/x', label: 'v1' });
    expect(c.querySelector('.wizard-phasebar')).toBeNull();
    expect(c.querySelector('.wizard-agent-params')).not.toBeNull();
  });
});
```
```

- [ ] **Step 6: Create `progress-view.js` shared module + tests**

Path: `docs/frontend-local-version-viewer/viewer/js/progress-view.js`

```js
// Shared DOM render for phasebar + steplist + prog-live.
// Consumed by ui-wizard.js (精靈 PROGRESS) and ui-modal.js (Viewer 重新分析 modal).
// Spec §5.3 / §5.4 / §7.

import { PHASE_BUCKETS, phaseStatus, labelFor } from './phase-status.js';

const STEPS_CANONICAL = ['analyze_old', 'analyze_new', 'diff', 'scope_verify', 'timeline', 'report'];

/**
 * Returns innerHTML string for the phasebar + steplist + (optional) prog-live.
 * Pure function — no DOM mutation; caller decides where to mount.
 */
export function renderProgressInnerHTML({ steps, currentStep, progress }) {
  const stepsByName = new Map((steps || []).map(s => [s.step_name, s]));
  const fullSteps = STEPS_CANONICAL.map(name =>
    stepsByName.get(name) || { step_name: name, status: 'pending' });

  const phasebarHTML = PHASE_BUCKETS.map(bucket => {
    const st = phaseStatus(bucket, fullSteps, currentStep);
    const icon = st === 'done' ? '✓ ' : st === 'failed' ? '✗ ' : '';
    return `<div class="wizard-phase ${st}"><div class="track"><div class="fill"></div></div><div class="pl">${icon}${bucket.label}</div></div>`;
  }).join('');

  const rowsHTML = fullSteps.map(s => {
    const icon = s.status === 'completed' ? '✓'
      : s.status === 'failed'  ? '✗'
      : s.status === 'skipped' ? '⊘'
      : s.status === 'running' ? '<span class="wizard-spin"></span>'
      : '○';
    const dur = s.duration_ms != null ? `${(s.duration_ms / 1000).toFixed(1)}s` : '';
    const err = s.error_message ? `<span class="wizard-sl-err">${s.error_message}</span>` : '';
    return `<div class="wizard-sl-row ${s.status}" data-step-status="${s.status}">`
         + `<span class="si">${icon}</span><span class="sn">${labelFor(s.step_name)}</span>${err}<span class="dur">${dur}</span></div>`;
  }).join('');

  const progLiveHTML = progress ? `
    <div class="wizard-prog-live">
      <div class="wizard-pl-head">
        <span class="wizard-pl-dot"></span>
        正在分析 <span class="wizard-pl-count">${progress.files_done} / ${progress.files_total}</span> 個檔案
      </div>
      <div class="wizard-pl-feed"></div>
    </div>` : '';

  return `
    <div class="wizard-phasebar">${phasebarHTML}</div>
    <div class="wizard-steplist">${rowsHTML}</div>
    ${progLiveHTML}
  `;
}

/**
 * Append a file path line into the most recent .wizard-pl-feed within `scope`
 * (defaults to document). No-op if no feed exists. Trims to ≤20 lines.
 */
export function appendPlLine(filePath, scope = document) {
  const feed = scope.querySelector('.wizard-pl-feed');
  if (!feed) return;
  const line = document.createElement('div');
  line.className = 'wizard-pl-line';
  line.textContent = filePath;
  feed.appendChild(line);
  while (feed.children.length > 20) feed.removeChild(feed.firstChild);
}

/**
 * Update the .wizard-pl-count text within `scope`. No-op if absent.
 */
export function updateProgressCount(done, total, scope = document) {
  const cnt = scope.querySelector('.wizard-pl-count');
  if (cnt) cnt.textContent = `${done} / ${total}`;
}
```

Path: `docs/frontend-local-version-viewer/viewer/tests/progress-view.test.js`

```js
import { describe, it, expect, beforeEach } from 'vitest';
import {
  renderProgressInnerHTML,
  appendPlLine,
  updateProgressCount,
} from '../js/progress-view.js';

describe('renderProgressInnerHTML', () => {
  it('returns 3 phase + 6 steplist row + no prog-live when progress=null', () => {
    const html = renderProgressInnerHTML({ steps: [], currentStep: null, progress: null });
    const c = document.createElement('div'); c.innerHTML = html;
    expect(c.querySelectorAll('.wizard-phase').length).toBe(3);
    expect(c.querySelectorAll('.wizard-sl-row').length).toBe(6);
    expect(c.querySelector('.wizard-prog-live')).toBeNull();
  });

  it('renders prog-live with count when progress set', () => {
    const html = renderProgressInnerHTML({
      steps: [], currentStep: null,
      progress: { files_done: 5, files_total: 10, current_file: 'a.py', current_root: 'new' },
    });
    const c = document.createElement('div'); c.innerHTML = html;
    expect(c.querySelector('.wizard-prog-live')).not.toBeNull();
    expect(c.querySelector('.wizard-pl-count').textContent).toMatch(/5\s*\/\s*10/);
  });

  it('step status drives data-step-status attr + icon', () => {
    const html = renderProgressInnerHTML({
      steps: [{ step_name: 'analyze_new', status: 'running' }],
      currentStep: 'analyze_new', progress: null,
    });
    const c = document.createElement('div'); c.innerHTML = html;
    const newRow = [...c.querySelectorAll('.wizard-sl-row')].find(r => r.textContent.includes('分析新版'));
    expect(newRow.getAttribute('data-step-status')).toBe('running');
    expect(newRow.querySelector('.wizard-spin')).not.toBeNull();
  });

  it('failed step renders error_message span', () => {
    const html = renderProgressInnerHTML({
      steps: [{ step_name: 'analyze_new', status: 'failed', error_message: 'boom' }],
      currentStep: null, progress: null,
    });
    const c = document.createElement('div'); c.innerHTML = html;
    expect(c.querySelector('.wizard-sl-err').textContent).toBe('boom');
  });
});

describe('appendPlLine', () => {
  beforeEach(() => { document.body.innerHTML = '<div class="wizard-pl-feed"></div>'; });

  it('appends a .wizard-pl-line with file path text', () => {
    appendPlLine('foo/bar.py');
    expect(document.querySelector('.wizard-pl-feed .wizard-pl-line').textContent).toBe('foo/bar.py');
  });

  it('trims feed to ≤20 lines (FIFO)', () => {
    for (let i = 0; i < 25; i++) appendPlLine(`f${i}.py`);
    const lines = document.querySelectorAll('.wizard-pl-feed .wizard-pl-line');
    expect(lines.length).toBe(20);
    expect(lines[0].textContent).toBe('f5.py');
    expect(lines[19].textContent).toBe('f24.py');
  });

  it('is no-op when scope has no feed', () => {
    document.body.innerHTML = '';
    expect(() => appendPlLine('x.py')).not.toThrow();
  });

  it('respects scope arg', () => {
    document.body.innerHTML = '<div id="A"><div class="wizard-pl-feed"></div></div><div id="B"><div class="wizard-pl-feed"></div></div>';
    const a = document.getElementById('A');
    appendPlLine('only-a.py', a);
    expect(a.querySelector('.wizard-pl-line').textContent).toBe('only-a.py');
    expect(document.getElementById('B').querySelector('.wizard-pl-line')).toBeNull();
  });
});

describe('updateProgressCount', () => {
  beforeEach(() => { document.body.innerHTML = '<span class="wizard-pl-count"></span>'; });
  it('sets text to "done / total"', () => {
    updateProgressCount(3, 10);
    expect(document.querySelector('.wizard-pl-count').textContent).toBe('3 / 10');
  });
  it('no-op when count element absent', () => {
    document.body.innerHTML = '';
    expect(() => updateProgressCount(1, 2)).not.toThrow();
  });
});
```

Run + verify (must pass before continuing):
```bash
npm test -- tests/progress-view.test.js
```

- [ ] **Step 7: Patch ui-wizard.js PROGRESS case to use shared `renderProgressInnerHTML`**

Add import at top of `docs/frontend-local-version-viewer/viewer/js/ui-wizard.js`:

```js
import { PHASE_BUCKETS, phaseStatus, labelFor } from './phase-status.js';
import { renderProgressInnerHTML, appendPlLine, updateProgressCount } from './progress-view.js';
```

In `renderPage` `case 'PROGRESS':` block — replace the existing `else { ... }` (API-mode) branch with:

```js
} else {
  // API mode: shared progress view (spec §4.2 ⓕ, §5.3, §5.4)
  wrap.innerHTML = `<h2>分析進行中</h2>${renderProgressInnerHTML({
    steps: state.steps,
    currentStep: state.currentStep,
    progress: state.progress,
  })}`;
}
```

- [ ] **Step 8: Wire polling to consume `data.progress` (uses progress-view helpers)**

In `startPolling` (inside `initWizard`), patch the inner `setInterval` callback:

```js
const data = await api.getJobStatus(jobId);
dispatch({ type: 'POLL_UPDATE', status: data.status,
           currentStep: data.current_step, steps: data.steps || [],
           errorMessage: data.error_message, progress: data.progress });
// Live feed (bypass full rerender for stutter-free append).
// appendPlLine / updateProgressCount imported from progress-view.js (Step 7).
if (data.progress && data.progress.current_file) {
  appendPlLine(data.progress.current_file);
  updateProgressCount(data.progress.files_done, data.progress.files_total);
}
```

Also extend `POLL_UPDATE` case in `transition`:

```js
case 'POLL_UPDATE': {
  if (action.status === 'failed') { /* existing */ }
  return {
    ...state,
    jobStatus: action.status,
    currentStep: action.currentStep,
    steps: action.steps,
    progress: action.progress ?? state.progress,  // NEW
  };
}
```

And `getInitialState()` add `progress: null,`.

- [ ] **Step 9: Run all task 6 tests, verify PASS**

```bash
npm test -- tests/wizard-phasebar.test.js tests/wizard-progress-render.test.js
```
Expected: all pass.

- [ ] **Step 10: Run full JS suite + coverage**

```bash
npm test
npm run test:coverage -- js/phase-status.js
```
Expected: all pass; `phase-status.js` 100% line + branch.

- [ ] **Step 11: Commit**

```bash
git add docs/frontend-local-version-viewer/viewer/js/phase-status.js \
        docs/frontend-local-version-viewer/viewer/js/progress-view.js \
        docs/frontend-local-version-viewer/viewer/js/ui-wizard.js \
        docs/frontend-local-version-viewer/viewer/tests/wizard-phasebar.test.js \
        docs/frontend-local-version-viewer/viewer/tests/wizard-progress-render.test.js \
        docs/frontend-local-version-viewer/viewer/tests/progress-view.test.js
git commit -m "feat(wizard): PROGRESS phasebar + steplist + 即時 feed

新增 js/phase-status.js（PHASE_BUCKETS / STEP_LABELS / phaseStatus / labelFor 純函式）。
ui-wizard.js PROGRESS API 模式 case 改 phasebar + 完整 6-step steplist + 即時 feed
（消費後端 progress.* payload）。failed step 優先於 active/done，符合不可造假進度原則。
新增 appendPlLine / updateProgressCount + POLL_UPDATE state 加 progress 欄位。

spec §4.2 ⓕ / §5.3 / §5.4。

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```
