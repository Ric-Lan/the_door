# Task 2 — styles.css shared progress region + tokens A (11 個)

**Goal:** 在 `styles.css` 新增「共用進度樣式」區（phasebar + steplist + prog-live + spin），讓精靈與 Viewer modal 共用；同時補入 §1.3 A 段 11 個 token 到 `:root`。

**Dependencies:** none（純 CSS，可與 task 3 並行）。

**Files:**
- Modify: `docs/frontend-local-version-viewer/viewer/styles.css` (`:root` 加 11 token；檔尾或現有 progress 段加共用區)
- Create: `docs/frontend-local-version-viewer/viewer/tests/wizard-css-shared-progress.test.js`

---

- [ ] **Step 1: Add failing test for new tokens + shared progress classes**

Path: `docs/frontend-local-version-viewer/viewer/tests/wizard-css-shared-progress.test.js`

```js
import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const css = readFileSync(resolve(__dirname, '../styles.css'), 'utf8');

describe('styles.css :root — Part 2 A-section tokens (11)', () => {
  const tokens = [
    '--term-bg', '--term-fg', '--term-toolbar',
    '--radius', '--radius-card',
    '--rail-bg', '--rail-bg-2', '--rail-line',
    '--rail-text', '--rail-muted', '--rail-dim',
  ];
  for (const t of tokens) {
    it(`defines ${t} in :root`, () => {
      // simplistic check: token appears in a :root { ... } block at file top
      const rootBlock = css.match(/:root\s*{([^}]+)}/);
      expect(rootBlock).toBeTruthy();
      expect(rootBlock[1]).toMatch(new RegExp(`${t}\\s*:`));
    });
  }
  it('does NOT add --font-sans / --font-mono to styles.css :root (those live in wizard.css scope per spec §1.3 B)', () => {
    const rootBlock = css.match(/:root\s*{([^}]+)}/);
    expect(rootBlock[1]).not.toMatch(/--font-sans\s*:/);
    expect(rootBlock[1]).not.toMatch(/--font-mono\s*:/);
  });
});

describe('styles.css shared progress region', () => {
  const required = [
    '.wizard-phasebar',
    '.wizard-phase',
    '@keyframes wizardIndet',
    '.wizard-steplist',
    '.wizard-sl-row',
    '.wizard-prog-live',
    '.wizard-pl-head',
    '.wizard-pl-feed',
    '.wizard-pl-line',
    '.wizard-pl-count',
    '.wizard-pl-dot',
    '@keyframes wizardPlPulse',
    '@keyframes wizardPlIn',
    '.wizard-spin',
    '@keyframes wizardSpin',
  ];
  for (const sel of required) {
    it(`defines selector or keyframe: ${sel}`, () => {
      // escape regex meta for "."
      const re = new RegExp(sel.replace(/[.@]/g, m => '\\' + m) + '\\b');
      expect(css).toMatch(re);
    });
  }

  it('wizardPlIn has no opacity:0 starter (spec §3.1 violation rewrite)', () => {
    const m = css.match(/@keyframes\s+wizardPlIn\s*{([^}]+)}/);
    expect(m).toBeTruthy();
    expect(m[1]).not.toMatch(/opacity\s*:\s*0\b/);
  });

  it('phasebar supports .failed state (per spec §5.3 phaseStatus failed branch)', () => {
    expect(css).toMatch(/\.wizard-phase\.failed\b/);
  });

  it('sl-row supports .failed and .skipped states', () => {
    expect(css).toMatch(/\.wizard-sl-row\.failed\b/);
    expect(css).toMatch(/\.wizard-sl-row\.skipped\b/);
  });
});

describe('styles.css @keyframes hygiene (spec §3.1)', () => {
  it('no @keyframes block contains opacity:0 starter (from / 0% / any %)', () => {
    const blocks = [...css.matchAll(/@keyframes\s+\w+\s*{([^@}]*(?:}[^@}]*)*?)}/g)];
    for (const b of blocks) {
      // check each declaration block within
      expect(b[1]).not.toMatch(/opacity\s*:\s*0\b/);
    }
  });
});
```

- [ ] **Step 2: Run test, verify FAIL**

```bash
cd docs/frontend-local-version-viewer/viewer
npm test -- tests/wizard-css-shared-progress.test.js
```
Expected: most fail (selectors / tokens / keyframes not present).

- [ ] **Step 3: Add 11 tokens to `styles.css :root`**

Modify `docs/frontend-local-version-viewer/viewer/styles.css` — locate `:root {` (line 6-77). Before the closing `}` of `:root`, insert:

```css
  /* ── Part 2 onboarding flow tokens (spec §1.3 A) ── */
  --term-bg: #1e293b;
  --term-fg: #e2e8f0;
  --term-toolbar: #263238;
  --radius: 3px;
  --radius-card: 6px;
  --rail-bg: #0a3b37;
  --rail-bg-2: #072925;
  --rail-line: rgba(217, 243, 239, 0.16);
  --rail-text: #eafaf7;
  --rail-muted: #7fb8b1;
  --rail-dim: #4d827c;
```

- [ ] **Step 4: Add shared progress region**

Locate the existing `/* Pipeline progress bar */` block (around line 822 in current file). REPLACE the chips region (lines 846-870 — the 6 `.steps-list` / `.step-*` rules) with the new shared progress CSS. (Removal of chips is split here from task 8 because both tasks need this swap; we land the shared rules now, task 8 deletes references and replaces `ui-modal.js` DOM.)

Insert before `/* Update modal */` (around line 872):

```css
/* ── Progress (shared by wizard + viewer modal, spec §7.2) ── */
.wizard-phasebar {
  display: flex;
  gap: 8px;
  max-width: 560px;
  margin: 30px 0 8px;
}
.wizard-phase { flex: 1; }
.wizard-phase .track {
  height: 7px;
  border-radius: 4px;
  background: var(--surface-muted);
  overflow: hidden;
}
.wizard-phase .track .fill {
  height: 100%;
  width: 0;
  background: linear-gradient(90deg, var(--accent), #2bb8a8);
  border-radius: 4px;
  transition: width 0.45s ease;
}
.wizard-phase.done .track .fill { width: 100%; }
.wizard-phase.active .track .fill { width: 100%; animation: wizardIndet 1.3s ease-in-out infinite; }
.wizard-phase.failed .track .fill { width: 100%; background: var(--removed-border); }
@keyframes wizardIndet { 0% { width: 8%; } 50% { width: 88%; } 100% { width: 8%; } }
.wizard-phase .pl {
  font-size: 11px;
  color: var(--muted);
  margin-top: 9px;
  display: flex;
  align-items: center;
  gap: 5px;
}
.wizard-phase.done .pl { color: var(--added-fg); }
.wizard-phase.active .pl { color: var(--accent); font-weight: 700; }
.wizard-phase.failed .pl { color: var(--removed-fg); font-weight: 700; }

.wizard-steplist {
  margin-top: 30px;
  max-width: 560px;
  border: 1px solid var(--line);
  border-radius: var(--radius-card);
  overflow: hidden;
}
.wizard-sl-row {
  display: flex;
  align-items: center;
  gap: 13px;
  padding: 14px 18px;
  border-bottom: 1px solid var(--line);
  font-size: 14px;
}
.wizard-sl-row:last-child { border-bottom: none; }
.wizard-sl-row .si {
  width: 22px; height: 22px;
  border-radius: 50%;
  flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
  font-size: 12px; font-weight: 700;
}
.wizard-sl-row.done .si { background: var(--added-bg); color: var(--added-fg); }
.wizard-sl-row.running .si { background: var(--accent-soft); color: var(--accent-press); }
.wizard-sl-row.failed .si { background: var(--removed-bg); color: var(--removed-fg); }
.wizard-sl-row.skipped .si { background: var(--surface-muted); color: var(--muted); }
.wizard-sl-row.pending .si { background: var(--surface-muted); color: var(--muted); }
.wizard-sl-row .sn { color: var(--text); }
.wizard-sl-row.pending .sn { color: var(--muted); }
.wizard-sl-row.skipped .sn { color: var(--muted); }
.wizard-sl-row.running .sn { font-weight: 600; }
.wizard-sl-row.failed .sn { color: var(--removed-fg); }
.wizard-sl-row .dur { margin-left: auto; font-size: 12px; color: var(--muted); }

.wizard-prog-live {
  margin-top: 22px;
  max-width: 560px;
  background: var(--term-bg);
  border: 1px solid #0b1220;
  border-radius: var(--radius-card);
  overflow: hidden;
}
.wizard-pl-head {
  display: flex; align-items: center; gap: 9px;
  padding: 11px 16px;
  background: var(--term-toolbar);
  border-bottom: 1px solid #0b1220;
  font-size: 13px; color: #cbd5e1; font-weight: 600;
}
.wizard-pl-count { color: #5eead4; font-weight: 700; }
.wizard-pl-dot {
  width: 8px; height: 8px; border-radius: 50%;
  background: #5eead4; box-shadow: 0 0 8px #5eead4;
  animation: wizardPlPulse 1s ease-in-out infinite;
}
@keyframes wizardPlPulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.35; } }
.wizard-pl-feed {
  padding: 10px 16px 12px;
  min-height: 96px;
  display: flex; flex-direction: column; justify-content: flex-end; gap: 3px;
}
.wizard-pl-line {
  font-size: 12px; color: #5b6b80; line-height: 1.5;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  animation: wizardPlIn 0.25s ease;
}
.wizard-pl-line:last-child { color: #e2e8f0; }
.wizard-pl-line:last-child::before { content: "▸ "; color: #5eead4; }
@keyframes wizardPlIn { from { transform: translateY(4px); } to { transform: translateY(0); } }

.wizard-spin {
  display: inline-block;
  width: 13px; height: 13px;
  border: 2px solid var(--accent-soft);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: wizardSpin 0.7s linear infinite;
}
@keyframes wizardSpin { to { transform: rotate(360deg); } }
```

(Keep existing `.pipeline-progress` / `.progress-header` / `.progress-title` / `.current-step` for the index.html container; task 8 will rewrite `ui-modal.js` to render phasebar inside this container.)

**Do NOT remove `.steps-list` / `.step-item` / `.step-completed` / `.step-failed` / `.step-skipped` / `.step-error` 6 條規則 yet** — they will be removed in task 8 atomically with `ui-modal.js` DOM rewrite. This task only adds new region.

- [ ] **Step 5: Run new test, verify all PASS**

```bash
npm test -- tests/wizard-css-shared-progress.test.js
```
Expected: all pass.

- [ ] **Step 6: Run existing CSS hygiene tests, verify no regression**

```bash
npm test -- tests/wizard-css-units.test.js
```
Expected: 3 pass (FIX-2 baseline preserved).

- [ ] **Step 7: Run full JS suite — no regressions**

```bash
npm test
```
Expected: 731 + new = 741 passing.

- [ ] **Step 8: Commit**

```bash
git add docs/frontend-local-version-viewer/viewer/styles.css \
        docs/frontend-local-version-viewer/viewer/tests/wizard-css-shared-progress.test.js
git commit -m "feat(css): shared progress region + 11 Part 2 :root tokens

styles.css 加 .wizard-phasebar/.wizard-steplist/.wizard-prog-live/.wizard-spin
+ wizardIndet/wizardPlPulse/wizardPlIn/wizardSpin keyframes + 11 個 token
（terminal/radius/rail）。spec §1.3 A 段、§7.2。

舊 .step-* chips 規則保留待 task 8 與 ui-modal.js DOM 改寫一起刪除。

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```
