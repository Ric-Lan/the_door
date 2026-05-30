# Task 9 — 跨頁穿門轉場（threshold-out + onboarding-card viewerIn）

**Goal:** 精靈完成 redirect 前對 `.wizard-shell` 套 `.leaving`（`wizardThresholdOut` 動畫），等動畫結束再跳頁；index.html `.onboarding-card` 載入時套 `viewerIn` 動畫（只 scale、無 opacity）。

**Dependencies:** task 3（`.wizard-shell.leaving` CSS）+ task 4（renderPage shell）。

**Files:**
- Modify: `docs/frontend-local-version-viewer/viewer/js/ui-wizard.js`（新增 `redirectWithTransition` + 替換所有 `redirectFn('/index.html')` 呼叫）
- Modify: `docs/frontend-local-version-viewer/viewer/styles.css`（加 `.onboarding-card` `viewerIn` 動畫）
- Create: `docs/frontend-local-version-viewer/viewer/tests/wizard-redirect-transition.test.js`

---

- [ ] **Step 1: Failing tests**

Path: `docs/frontend-local-version-viewer/viewer/tests/wizard-redirect-transition.test.js`

```js
import { describe, it, expect, vi, beforeEach } from 'vitest';

describe('redirectWithTransition (spec §6.2)', () => {
  beforeEach(() => {
    document.body.innerHTML = '<div class="wizard-shell"></div>';
    vi.useFakeTimers();
  });

  it('adds .leaving class to .wizard-shell immediately', async () => {
    const { redirectWithTransition } = await import('../js/ui-wizard.js');
    const setLocation = vi.fn();
    redirectWithTransition('/index.html', setLocation);
    expect(document.querySelector('.wizard-shell').classList.contains('leaving')).toBe(true);
    expect(setLocation).not.toHaveBeenCalled();
  });

  it('delays setLocation by ~620ms (animation duration)', async () => {
    const { redirectWithTransition } = await import('../js/ui-wizard.js');
    const setLocation = vi.fn();
    redirectWithTransition('/index.html', setLocation);
    vi.advanceTimersByTime(619);
    expect(setLocation).not.toHaveBeenCalled();
    vi.advanceTimersByTime(2);
    expect(setLocation).toHaveBeenCalledWith('/index.html');
  });

  it('still redirects if no .wizard-shell present (fallback)', async () => {
    document.body.innerHTML = '';
    const { redirectWithTransition } = await import('../js/ui-wizard.js');
    const setLocation = vi.fn();
    redirectWithTransition('/index.html', setLocation);
    vi.advanceTimersByTime(700);
    expect(setLocation).toHaveBeenCalledWith('/index.html');
  });
});

describe('styles.css .onboarding-card viewerIn', () => {
  it('defines viewerIn keyframe without opacity:0 starter', async () => {
    const fs = await import('node:fs');
    const path = await import('node:path');
    const url = await import('node:url');
    const dir = path.dirname(url.fileURLToPath(import.meta.url));
    const css = fs.readFileSync(path.resolve(dir, '../styles.css'), 'utf8');
    expect(css).toMatch(/@keyframes\s+viewerIn\s*{/);
    const m = css.match(/@keyframes\s+viewerIn\s*{([^}]+)}/);
    expect(m[1]).not.toMatch(/opacity\s*:\s*0\b/);
  });

  it('.onboarding-card has viewerIn animation', async () => {
    const fs = await import('node:fs');
    const path = await import('node:path');
    const url = await import('node:url');
    const dir = path.dirname(url.fileURLToPath(import.meta.url));
    const css = fs.readFileSync(path.resolve(dir, '../styles.css'), 'utf8');
    // Match within .onboarding-card { ... animation: viewerIn ... }
    const block = css.match(/\.onboarding-card\s*{[^}]*animation\s*:\s*viewerIn/);
    expect(block).not.toBeNull();
  });
});
```

- [ ] **Step 2: Run, verify FAIL**

```bash
cd docs/frontend-local-version-viewer/viewer
npm test -- tests/wizard-redirect-transition.test.js
```

- [ ] **Step 3: Add `redirectWithTransition` to ui-wizard.js**

Modify `docs/frontend-local-version-viewer/viewer/js/ui-wizard.js`. Add and export:

```js
export function redirectWithTransition(url, setLocation = (u) => { window.location.href = u; }) {
  const shell = document.querySelector('.wizard-shell');
  if (shell) shell.classList.add('leaving');
  setTimeout(() => setLocation(url), 620);
}
```

In `initWizard`, replace every `redirectFn('/index.html')` call with `redirectWithTransition('/index.html')`:
- `view` action handler in PAGE_ACTION (existing `redirectFn('/index.html')` inside SELECT_ACTION-like click handler)
- `data-done` click handler in PROGRESS Agent mode
- `startPolling` `data.status === 'done'` branch (`redirectFn('/index.html')`)
- PAGE_ERROR primary button (if it uses redirectFn vs anchor href)

Where `redirectFn` is the default parameter `(url) => { window.location.href = url; }`, route via `redirectWithTransition(url, redirectFn)` so tests can still inject.

Specifically locate these 4 call sites with:
```bash
grep -n "redirectFn(\|window.location.href" docs/frontend-local-version-viewer/viewer/js/ui-wizard.js
```

For each, swap to `redirectWithTransition('/index.html', redirectFn)`.

- [ ] **Step 4: Add `.onboarding-card` viewerIn CSS**

Append to `docs/frontend-local-version-viewer/viewer/styles.css` (near existing `.onboarding-card` rule, around line 1825):

```css
/* Part 2 viewerIn landing animation (spec §6.2) — only scale, no opacity starter */
.onboarding-card { animation: viewerIn 0.6s cubic-bezier(0.2, 0.7, 0.2, 1) both; }
@keyframes viewerIn { from { transform: scale(0.99); } to { transform: scale(1); } }
```

(`both` keeps final state; basesty opacity already 1 by default.)

- [ ] **Step 5: Run task 9 tests, verify PASS**

```bash
npm test -- tests/wizard-redirect-transition.test.js
```
Expected: 5 pass.

- [ ] **Step 6: Re-run §3.1 grep hygiene tests (no new opacity:0 keyframes)**

```bash
npm test -- tests/wizard-css-shared-progress.test.js tests/wizard-shell-css.test.js
```
Expected: still all pass (viewerIn doesn't violate `@keyframes opacity:0` rule).

- [ ] **Step 7: Full suite + coverage**

```bash
npm test
npm run test:coverage -- tests/wizard-redirect-transition.test.js
```
Expected: `redirectWithTransition` 100% covered (3 test cases hit all branches).

- [ ] **Step 8: Browser smoke — visual confirmation**

```bash
the-door ui "C:\Users\Ric\Desktop\test-targets\the-door-v105" --no-browser --port 8765
```
Open http://localhost:8765/wizard.html, run through analyze flow, verify on completion shell fades out + onboarding card subtly zooms in.

- [ ] **Step 9: Commit**

```bash
git add docs/frontend-local-version-viewer/viewer/js/ui-wizard.js \
        docs/frontend-local-version-viewer/viewer/styles.css \
        docs/frontend-local-version-viewer/viewer/tests/wizard-redirect-transition.test.js
git commit -m "feat(wizard): cross-page door-threshold transition

新增 redirectWithTransition — 跳頁前對 .wizard-shell 套 .leaving 觸發
wizardThresholdOut 動畫，620ms 後跳；fallback：若無 .wizard-shell 直接 redirect。
.onboarding-card 加 viewerIn 動畫（只 scale，無 opacity:0 起始）。spec §6.2。

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```
