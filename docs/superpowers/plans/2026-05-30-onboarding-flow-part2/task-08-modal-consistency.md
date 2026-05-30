# Task 8 — ui-modal.js renderPipelineProgress redesign + remove old chips

**Goal:** `ui-modal.js renderPipelineProgress(job)` 改用 phasebar + steplist + 即時 feed 結構（與精靈 PROGRESS 同樣式）；移除 `viewer/styles.css:846-870` 的 6 條 `.step-*` chips 規則。

**Dependencies:** task 2（shared progress CSS）+ task 6（phaseStatus / PHASE_BUCKETS / appendPlLine helpers）+ task 1b（progress payload）。

**Files:**
- Modify: `docs/frontend-local-version-viewer/viewer/js/ui-modal.js`（`renderPipelineProgress` + 加 progress feed handling 進 `pollJobStatus`）
- Modify: `docs/frontend-local-version-viewer/viewer/styles.css`（移除 6 條 chips 規則）
- Modify: `docs/frontend-local-version-viewer/viewer/tests/ui-modal.test.js`（改寫 renderPipelineProgress 測試）

---

- [ ] **Step 1: Failing tests for new renderPipelineProgress structure**

Modify `docs/frontend-local-version-viewer/viewer/tests/ui-modal.test.js` — locate existing `describe('renderPipelineProgress', ...)` block and replace its contents with:

```js
describe('renderPipelineProgress new design (spec §7)', () => {
  beforeEach(() => {
    document.body.innerHTML = `
      <div id="pipeline-progress" class="pipeline-progress">
        <div class="progress-header">
          <span class="progress-title">正在分析…</span>
          <span id="current-step" class="current-step"></span>
        </div>
        <ul id="steps-list" class="steps-list"></ul>
      </div>
    `;
  });

  it('renders 3 phase buckets inside #pipeline-progress', async () => {
    const { renderPipelineProgress } = await import('../js/ui-modal.js');
    renderPipelineProgress({
      status: 'running',
      current_step: 'analyze_new',
      steps: [{ step_name: 'analyze_new', status: 'running' }],
      progress: null,
    });
    expect(document.querySelectorAll('#pipeline-progress .wizard-phasebar .wizard-phase').length).toBe(3);
  });

  it('renders 6 steplist rows', async () => {
    const { renderPipelineProgress } = await import('../js/ui-modal.js');
    renderPipelineProgress({
      status: 'running',
      current_step: null,
      steps: ['analyze_old','analyze_new','diff','scope_verify','timeline','report']
        .map(n => ({ step_name: n, status: 'pending' })),
      progress: null,
    });
    expect(document.querySelectorAll('#pipeline-progress .wizard-steplist .wizard-sl-row').length).toBe(6);
  });

  it('shows .wizard-prog-live when progress dict set', async () => {
    const { renderPipelineProgress } = await import('../js/ui-modal.js');
    renderPipelineProgress({
      status: 'running',
      current_step: 'analyze_new',
      steps: [{ step_name: 'analyze_new', status: 'running' }],
      progress: { files_done: 12, files_total: 100, current_file: 'x.py', current_root: 'new' },
    });
    expect(document.querySelector('.wizard-prog-live')).not.toBeNull();
    expect(document.querySelector('.wizard-pl-count').textContent).toMatch(/12\s*\/\s*100/);
  });

  it('hides .wizard-prog-live when progress is null', async () => {
    const { renderPipelineProgress } = await import('../js/ui-modal.js');
    renderPipelineProgress({
      status: 'running',
      current_step: 'analyze_new',
      steps: [{ step_name: 'analyze_new', status: 'running' }],
      progress: null,
    });
    expect(document.querySelector('.wizard-prog-live')).toBeNull();
  });

  it('failed step shows .wizard-sl-row.failed', async () => {
    const { renderPipelineProgress } = await import('../js/ui-modal.js');
    renderPipelineProgress({
      status: 'failed',
      current_step: null,
      steps: [{ step_name: 'analyze_new', status: 'failed', error_message: 'boom' }],
      progress: null,
    });
    expect(document.querySelector('.wizard-sl-row.failed')).not.toBeNull();
  });

  it('no longer renders old .step-item chips', async () => {
    const { renderPipelineProgress } = await import('../js/ui-modal.js');
    renderPipelineProgress({
      status: 'running',
      current_step: 'analyze_new',
      steps: [{ step_name: 'analyze_new', status: 'running' }],
      progress: null,
    });
    expect(document.querySelectorAll('.step-item').length).toBe(0);
  });
});

describe('styles.css chips cleanup (spec §7.1)', () => {
  it('removes 6 .step-* chips rules', async () => {
    const fs = await import('node:fs');
    const path = await import('node:path');
    const url = await import('node:url');
    const dir = path.dirname(url.fileURLToPath(import.meta.url));
    const css = fs.readFileSync(path.resolve(dir, '../styles.css'), 'utf8');
    // The class itself is OK as a substring (data-step-status etc.); check rule declarations don't exist.
    expect(css).not.toMatch(/\.step-item\s*{/);
    expect(css).not.toMatch(/\.step-completed\s*{/);
    expect(css).not.toMatch(/\.step-failed\s*{/);
    expect(css).not.toMatch(/\.step-skipped\s*{/);
    expect(css).not.toMatch(/\.step-error\s*{/);
    expect(css).not.toMatch(/\.steps-list\s*{/);
  });
});
```

- [ ] **Step 2: Run, verify FAIL**

```bash
cd docs/frontend-local-version-viewer/viewer
npm test -- tests/ui-modal.test.js
```

- [ ] **Step 3: Rewrite `renderPipelineProgress` in ui-modal.js**

Modify `docs/frontend-local-version-viewer/viewer/js/ui-modal.js`:

At top, add import:
```js
import { PHASE_BUCKETS, phaseStatus, labelFor } from './phase-status.js';
```

Replace `export function renderPipelineProgress(job)` (around line 33) entirely:

```js
export function renderPipelineProgress(job) {
  const container = document.getElementById('pipeline-progress');
  if (!container) return;
  els.currentStep.textContent = job.current_step ? '執行中：' + labelFor(job.current_step) : '';

  const STEPS_CANONICAL = ['analyze_old', 'analyze_new', 'diff', 'scope_verify', 'timeline', 'report'];
  const stepsByName = new Map((job.steps || []).map(s => [s.step_name, s]));
  const fullSteps = STEPS_CANONICAL.map(name => stepsByName.get(name) || { step_name: name, status: 'pending' });

  const phasebarHTML = PHASE_BUCKETS.map(bucket => {
    const st = phaseStatus(bucket, fullSteps, job.current_step);
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
    return `<div class="wizard-sl-row ${s.status}" data-step-status="${s.status}">
      <span class="si">${icon}</span><span class="sn">${labelFor(s.step_name)}</span>${err}<span class="dur">${dur}</span>
    </div>`;
  }).join('');

  const progLiveHTML = job.progress ? `
    <div class="wizard-prog-live">
      <div class="wizard-pl-head">
        <span class="wizard-pl-dot"></span>
        正在分析 <span class="wizard-pl-count">${job.progress.files_done} / ${job.progress.files_total}</span> 個檔案
      </div>
      <div class="wizard-pl-feed"></div>
    </div>` : '';

  els.stepsList.outerHTML = `
    <div id="steps-list" class="wizard-pipeline-redesign">
      <div class="wizard-phasebar">${phasebarHTML}</div>
      <div class="wizard-steplist">${rowsHTML}</div>
      ${progLiveHTML}
    </div>
  `;
  // Re-grab reference after outerHTML swap (els.stepsList stale)
  els.stepsList = document.getElementById('steps-list');
}
```

Note: `els.stepsList` is grabbed via `els` import from `dom.js`. After `outerHTML` swap the cached reference goes stale; refresh it.

Patch `pollJobStatus` (around line 82) to append live feed lines (mirroring task 6 pattern):

```js
export async function pollJobStatus(jobId, callbacks = {}) {
  try {
    const job = await api.fetchJobStatus(jobId);
    renderPipelineProgress(job);
    if (job.progress && job.progress.current_file) {
      const feed = document.querySelector('#pipeline-progress .wizard-pl-feed');
      if (feed) {
        const line = document.createElement('div');
        line.className = 'wizard-pl-line';
        line.textContent = job.progress.current_file;
        feed.appendChild(line);
        while (feed.children.length > 20) feed.removeChild(feed.firstChild);
      }
    }
    /* existing completion / failure handling */
  } catch (err) { /* existing */ }
}
```

- [ ] **Step 4: Remove 6 chips rules from styles.css**

In `docs/frontend-local-version-viewer/viewer/styles.css` — delete lines 846-870 (the `.steps-list` flex-wrap chips block + `.step-item`, `.step-completed`, `.step-failed`, `.step-skipped`, `.step-error` 6 rules). Keep `.pipeline-progress`, `.progress-header`, `.progress-title`, `.current-step` (the container).

Verify removal with `grep -n "\.step-item\|\.step-completed\|\.steps-list {" docs/frontend-local-version-viewer/viewer/styles.css` — should print nothing.

- [ ] **Step 5: Run task 8 tests, verify PASS**

```bash
npm test -- tests/ui-modal.test.js
```
Expected: all new + existing pass.

- [ ] **Step 6: Full JS suite**

```bash
npm test
```
Expected: all pass.

- [ ] **Step 7: Browser smoke — Viewer modal shows phasebar**

```bash
the-door ui "C:\Users\Ric\Desktop\test-targets\the-door-v105" --no-browser --port 8765
```
Open http://localhost:8765/, click「重新分析」, verify modal pipeline progress renders phasebar + steplist (not old chips).

- [ ] **Step 8: Commit**

```bash
git add docs/frontend-local-version-viewer/viewer/js/ui-modal.js \
        docs/frontend-local-version-viewer/viewer/styles.css \
        docs/frontend-local-version-viewer/viewer/tests/ui-modal.test.js
git commit -m "feat(modal): renderPipelineProgress 改用 phasebar/steplist/feed 設計

ui-modal.js renderPipelineProgress 換掉舊 chips DOM 結構，改用 task 2 共用區
phasebar + steplist + 即時 feed（與精靈 PROGRESS 同設計）。styles.css 移除
6 條 .step-* chips 規則（已被 .wizard-phasebar / .wizard-sl-row* 取代）。
pollJobStatus 內 polling 回呼直接 append .wizard-pl-line。spec §7。

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```
