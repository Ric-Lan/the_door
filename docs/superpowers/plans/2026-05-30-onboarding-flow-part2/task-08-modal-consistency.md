# Task 8 — ui-modal.js renderPipelineProgress redesign + remove old chips

**Goal:** `ui-modal.js renderPipelineProgress(job)` 改用 phasebar + steplist + 即時 feed 結構（與精靈 PROGRESS 同樣式）；移除 `viewer/styles.css:846-870` 的 6 條 `.step-*` chips 規則。

**Dependencies:** task 2（shared progress CSS）+ task 6（`progress-view.js` 共用 render module）+ task 1b（progress payload）。

**Files:**
- Modify: `docs/frontend-local-version-viewer/viewer/js/ui-modal.js`（`renderPipelineProgress` + 加 progress feed handling 進 `pollJobStatus`）
- Modify: `docs/frontend-local-version-viewer/viewer/styles.css`（移除 6 條 chips 規則）
- Modify: `docs/frontend-local-version-viewer/viewer/tests/ui-modal.test.js`（改寫 renderPipelineProgress 測試）

---

- [ ] **Step 1: Failing tests for new renderPipelineProgress structure**

Modify `docs/frontend-local-version-viewer/viewer/tests/ui-modal.test.js` — at file top加（與既有 import 並列）：

```js
import { renderPipelineProgress } from '../js/ui-modal.js';
import { readFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
```

然後 locate existing `describe('renderPipelineProgress', ...)` block and replace its contents with:

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

  it('renders 3 phase buckets inside #pipeline-progress', () => {
    renderPipelineProgress({
      status: 'running',
      current_step: 'analyze_new',
      steps: [{ step_name: 'analyze_new', status: 'running' }],
      progress: null,
    });
    expect(document.querySelectorAll('#pipeline-progress .wizard-phasebar .wizard-phase').length).toBe(3);
  });

  it('renders 6 steplist rows', () => {
    renderPipelineProgress({
      status: 'running',
      current_step: null,
      steps: ['analyze_old','analyze_new','diff','scope_verify','timeline','report']
        .map(n => ({ step_name: n, status: 'pending' })),
      progress: null,
    });
    expect(document.querySelectorAll('#pipeline-progress .wizard-steplist .wizard-sl-row').length).toBe(6);
  });

  it('shows .wizard-prog-live when progress dict set', () => {
    renderPipelineProgress({
      status: 'running',
      current_step: 'analyze_new',
      steps: [{ step_name: 'analyze_new', status: 'running' }],
      progress: { files_done: 12, files_total: 100, current_file: 'x.py', current_root: 'new' },
    });
    expect(document.querySelector('.wizard-prog-live')).not.toBeNull();
    expect(document.querySelector('.wizard-pl-count').textContent).toMatch(/12\s*\/\s*100/);
  });

  it('hides .wizard-prog-live when progress is null', () => {
    renderPipelineProgress({
      status: 'running',
      current_step: 'analyze_new',
      steps: [{ step_name: 'analyze_new', status: 'running' }],
      progress: null,
    });
    expect(document.querySelector('.wizard-prog-live')).toBeNull();
  });

  it('failed step shows .wizard-sl-row.failed', () => {
    renderPipelineProgress({
      status: 'failed',
      current_step: null,
      steps: [{ step_name: 'analyze_new', status: 'failed', error_message: 'boom' }],
      progress: null,
    });
    expect(document.querySelector('.wizard-sl-row.failed')).not.toBeNull();
  });

  it('no longer renders old .step-item chips', () => {
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
  it('removes 6 .step-* chips rules', () => {
    const dir = dirname(fileURLToPath(import.meta.url));
    const css = readFileSync(resolve(dir, '../styles.css'), 'utf8');
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

- [ ] **Step 3: Rewrite `renderPipelineProgress` in ui-modal.js using shared `progress-view.js`**

Modify `docs/frontend-local-version-viewer/viewer/js/ui-modal.js`:

At top, add imports:
```js
import { labelFor } from './phase-status.js';
import { renderProgressInnerHTML, appendPlLine } from './progress-view.js';
```

Replace `export function renderPipelineProgress(job)` (line 33) entirely:

```js
export function renderPipelineProgress(job) {
  const container = document.getElementById('pipeline-progress');
  if (!container) return;
  els.currentStep.textContent = job.current_step ? '執行中：' + labelFor(job.current_step) : '';

  els.stepsList.outerHTML = `<div id="steps-list">${renderProgressInnerHTML({
    steps: job.steps,
    currentStep: job.current_step,
    progress: job.progress,
  })}</div>`;
  // Re-grab reference after outerHTML swap (cached els.stepsList stale).
  els.stepsList = document.getElementById('steps-list');
}
```

Patch `pollJobStatus` (line 82) to append live feed via shared helper:

```js
export async function pollJobStatus(jobId, callbacks = {}) {
  try {
    const job = await api.fetchJobStatus(jobId);
    renderPipelineProgress(job);
    if (job.progress && job.progress.current_file) {
      appendPlLine(job.progress.current_file, document.getElementById('pipeline-progress'));
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
