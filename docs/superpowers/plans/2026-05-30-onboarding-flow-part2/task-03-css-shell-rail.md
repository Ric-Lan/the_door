# Task 3 — wizard.css shell + rail + font tokens B (2 個)

**Goal:** 在 `wizard.css` 新增雙欄外殼（`.wizard-shell` / `.wizard-rail*` / `.wizard-content` / `.wizard-screen` + `wizardScreenIn` / `wizardThresholdOut`）、`.wizard-eyebrow` / `.wizard-mode-note*` / `.wizard-btn-ghost` / `.wizard-transient` / `.wizard-bigspin` / `.wizard-agent-why` / `.wizard-agent-steps` / `.wizard-astep*`；並把 `--font-sans` / `--font-mono` 注入 `.wizard-shell` scope（不放 styles.css :root）。

**Dependencies:** none（純 CSS，可與 task 2 並行）。

**Files:**
- Modify: `docs/frontend-local-version-viewer/viewer/wizard.css`（append 大量新區塊）
- Create: `docs/frontend-local-version-viewer/viewer/tests/wizard-shell-css.test.js`

---

- [ ] **Step 1: Add failing test**

Path: `docs/frontend-local-version-viewer/viewer/tests/wizard-shell-css.test.js`

```js
import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const css = readFileSync(resolve(__dirname, '../wizard.css'), 'utf8');

describe('wizard.css Part 2 shell + rail', () => {
  const required = [
    '.wizard-shell',
    '.wizard-rail',
    '.wizard-rail-brand',
    '.wizard-door-wrap',
    '.wizard-door-light',
    '.wizard-door-leaf',
    '.wizard-stepper',
    '.wizard-step',
    '.wizard-rail-foot',
    '.wizard-content',
    '.wizard-screen',
    '@keyframes wizardScreenIn',
    '@keyframes wizardThresholdOut',
    '.wizard-eyebrow',
    '.wizard-mode-note',
    '.wizard-btn-ghost',
    '.wizard-transient',
    '.wizard-bigspin',
    '.wizard-agent-why',
    '.wizard-agent-steps',
    '.wizard-astep',
    '.wizard-prog-note',
  ];
  for (const sel of required) {
    it(`defines: ${sel}`, () => {
      const re = new RegExp(sel.replace(/[.@]/g, m => '\\' + m) + '\\b');
      expect(css).toMatch(re);
    });
  }
});

describe('wizard.css font tokens scope (spec §1.3 B)', () => {
  it('defines --font-sans inside .wizard-shell scope (NOT :root)', () => {
    // Match `.wizard-shell, .wizard-shell * { ... --font-sans: ... }`
    expect(css).toMatch(/\.wizard-shell[^{]*{[^}]*--font-sans\s*:/);
  });
  it('defines --font-mono inside .wizard-shell scope', () => {
    expect(css).toMatch(/\.wizard-shell[^{]*{[^}]*--font-mono\s*:/);
  });
  it('does NOT define --font-sans / --font-mono in :root', () => {
    const rootBlock = css.match(/:root\s*{([^}]+)}/);
    if (rootBlock) {
      expect(rootBlock[1]).not.toMatch(/--font-sans\s*:/);
      expect(rootBlock[1]).not.toMatch(/--font-mono\s*:/);
    }
  });
});

describe('wizard.css door-light opacity:0 transition (spec §3.1 example)', () => {
  it('.wizard-door-light has opacity:0 starter (intentional, transition not keyframe)', () => {
    const block = css.match(/\.wizard-door-light\s*{([^}]+)}/);
    expect(block).toBeTruthy();
    expect(block[1]).toMatch(/opacity\s*:\s*0\b/);
    expect(block[1]).toMatch(/transition\s*:\s*opacity/);
  });
  it('.wizard-door-light.lit has non-zero opacity', () => {
    expect(css).toMatch(/\.wizard-door-light\.lit\s*{[^}]*opacity\s*:\s*\.?[1-9]/);
  });
});

describe('wizard.css @keyframes hygiene (spec §3.1)', () => {
  it('no @keyframes block contains opacity:0 starter', () => {
    const blocks = [...css.matchAll(/@keyframes\s+\w+\s*{([^@}]*(?:}[^@}]*)*?)}/g)];
    for (const b of blocks) {
      expect(b[1]).not.toMatch(/opacity\s*:\s*0\b/);
    }
  });
});

describe('wizard.css FIX-2 baseline preserved', () => {
  it('no rem literals (FIX-2 px-only discipline)', () => {
    expect((css.match(/\d*\.?\d+rem\b/g) || [])).toEqual([]);
  });
  it('all border-radius are 6px or token (var(--radius-card))', () => {
    const decls = css.match(/border-radius:\s*[^;]+;/g) || [];
    for (const d of decls) {
      expect(d).toMatch(/border-radius:\s*(6px|var\(--radius-card\))\s*;/);
    }
  });
});
```

- [ ] **Step 2: Run test, verify FAIL**

```bash
cd docs/frontend-local-version-viewer/viewer
npm test -- tests/wizard-shell-css.test.js
```
Expected: ~22 fail.

- [ ] **Step 3: Append shell + rail + tokens B to wizard.css**

Append to end of `docs/frontend-local-version-viewer/viewer/wizard.css`:

```css
/* ========================================================================
   Part 2 — Onboarding flow shell (spec §3)
   ======================================================================== */

/* Font tokens (spec §1.3 B — scoped to wizard, NOT in styles.css :root
   to avoid silent regression on the 7 mindmap/legend/cards usages.) */
.wizard-shell,
.wizard-shell * {
  --font-sans: "Segoe UI", Arial, "Noto Sans TC", "PingFang TC", sans-serif;
  --font-mono: Consolas, "Courier New", monospace;
}

/* Shell (dual-pane, full viewport) */
.wizard-shell {
  position: absolute;
  inset: 0;
  display: flex;
  background: var(--surface);
  font-family: var(--font-sans);
}
.wizard-shell.leaving {
  animation: wizardThresholdOut 0.62s cubic-bezier(0.7, 0, 0.3, 1) forwards;
}
@keyframes wizardThresholdOut {
  to { transform: scale(1.06); opacity: 0; filter: brightness(1.25); }
}

/* Left: rail (門外暗面) */
.wizard-rail {
  width: 312px;
  flex-shrink: 0;
  background: linear-gradient(160deg, var(--rail-bg), var(--rail-bg-2));
  color: var(--rail-text);
  display: flex;
  flex-direction: column;
  padding: 26px 26px 22px;
  position: relative;
  overflow: hidden;
}
.wizard-rail::after {
  content: "";
  position: absolute;
  inset: 0;
  pointer-events: none;
  background: radial-gradient(80% 50% at 120% 8%, rgba(217, 243, 239, 0.10), transparent 60%);
}
.wizard-rail-brand {
  display: flex; align-items: center; gap: 10px;
  position: relative; z-index: 1;
}
.wizard-rail-brand .leaf { width: 30px; height: 30px; }
.wizard-rail-brand .wd { font-size: 15px; font-weight: 700; letter-spacing: -0.01em; color: #fff; }
.wizard-rail-brand .sub {
  font-size: 11px; letter-spacing: 0.08em;
  color: var(--rail-muted); text-transform: uppercase; margin-top: 1px;
}

/* Door SVG container */
.wizard-door-wrap {
  position: relative; z-index: 1;
  margin: 30px auto 26px;
  width: 148px; height: 188px;
  perspective: 780px;
}
.wizard-door-frame { position: absolute; inset: 0; }
.wizard-door-light {
  position: absolute; left: 14px; top: 8px;
  width: 120px; height: 172px;
  border-radius: 2px;
  background: linear-gradient(180deg, #fdfefe, #d9f3ef);
  opacity: 0;                                /* intentional: door-light off by default (spec §3.1 example) */
  transition: opacity 0.55s ease;
}
.wizard-door-light.lit {
  opacity: 0.92;
  box-shadow: 0 0 38px 6px rgba(217, 243, 239, 0.55);
}
.wizard-door-leaf {
  position: absolute; left: 14px; top: 8px;
  width: 120px; height: 172px;
  background: linear-gradient(100deg, #0e514b, #0a3f3a);
  border: 2px solid rgba(217, 243, 239, 0.55);
  border-radius: 2px 3px 3px 2px;
  transform-origin: left center;
  transform: rotateY(0deg);
  transition: transform 0.6s cubic-bezier(0.5, 0, 0.2, 1), box-shadow 0.6s ease;
  box-shadow: inset -10px 0 26px rgba(0, 0, 0, 0.4);
}
.wizard-door-leaf .knob {
  position: absolute; right: 12px; top: 50%;
  width: 7px; height: 7px;
  border-radius: 50%;
  background: var(--accent-soft);
  transform: translateY(-50%);
  box-shadow: 0 0 6px rgba(217, 243, 239, 0.7);
}
.wizard-door-leaf .grain {
  position: absolute; left: 50%; top: 14px; bottom: 14px;
  width: 1px;
  transform: translateX(-50%);
  background: rgba(217, 243, 239, 0.14);
}
.wizard-door-pct {
  position: absolute; left: 0; right: 0; bottom: -2px;
  text-align: center;
  font-size: 11px; letter-spacing: 0.04em;
  color: var(--rail-muted);
  font-family: var(--font-mono);
  z-index: 2;
}

/* Stepper */
.wizard-stepper {
  position: relative; z-index: 1;
  margin-top: auto;
  display: flex; flex-direction: column; gap: 0;
}
.wizard-stepper-line {
  position: absolute; left: 13px; top: 14px; bottom: 14px;
  width: 2px;
  background: var(--rail-line);
}
.wizard-stepper-fill {
  position: absolute; left: 13px; top: 14px;
  width: 2px;
  background: linear-gradient(var(--accent-soft), #5fd6c8);
  transition: height 0.5s ease;
  border-radius: 2px;
  box-shadow: 0 0 8px rgba(95, 214, 200, 0.5);
}
/* Rail stepper items — qualified by .wizard-stepper to avoid clashing with
   FIX-1 ship 的 .wizard-steps .wizard-step[data-step-status] (PROGRESS steplist). */
.wizard-stepper .wizard-step {
  position: relative;
  display: flex; align-items: center; gap: 13px;
  padding: 8px 0;
  z-index: 1;
}
.wizard-stepper .wizard-step .dot {
  width: 28px; height: 28px;
  border-radius: 50%;
  flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
  background: var(--rail-bg-2);
  border: 2px solid var(--rail-dim);
  font-size: 12px;
  color: var(--rail-muted);
  transition: all 0.35s ease;
  font-weight: 700;
}
.wizard-stepper .wizard-step .lbl {
  font-size: 13px;
  color: var(--rail-muted);
  transition: color 0.35s ease;
  font-weight: 500;
}
.wizard-stepper .wizard-step.done .dot { background: var(--accent-soft); border-color: var(--accent-soft); color: var(--accent-press); }
.wizard-stepper .wizard-step.done .lbl { color: var(--rail-text); }
.wizard-stepper .wizard-step.active .dot {
  background: #fff;
  border-color: #fff;
  color: var(--accent-press);
  box-shadow: 0 0 0 5px rgba(217, 243, 239, 0.18);
  transform: scale(1.04);
}
.wizard-stepper .wizard-step.active .lbl { color: #fff; font-weight: 700; }

.wizard-rail-foot {
  position: relative; z-index: 1;
  margin-top: 20px;
  font-size: 11px; letter-spacing: 0.1em;
  color: var(--rail-dim);
  text-transform: uppercase;
}

/* Right: content (門內明亮) */
.wizard-content {
  flex: 1;
  position: relative;
  overflow: hidden;
  background: var(--surface);
}
.wizard-screen {
  position: absolute; inset: 0;
  padding: 52px 56px;
  display: flex; flex-direction: column;
  overflow-y: auto;
  opacity: 1;
}
.wizard-screen-enter {
  animation: wizardScreenIn 0.42s cubic-bezier(0.2, 0.7, 0.2, 1) both;
}
@keyframes wizardScreenIn {
  from { transform: translateX(18px); }
  to { transform: translateX(0); }
}

/* Eyebrow + mode-note */
.wizard-eyebrow {
  font-size: 11px; letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--accent);
  font-weight: 700;
  margin: 0 0 12px;
}
.wizard-mode-note {
  display: flex; align-items: center; gap: 11px;
  margin-top: 20px; max-width: 520px;
  padding: 11px 15px;
  border-radius: var(--radius-card);
  font-size: 13px; line-height: 1.5;
}
.wizard-mode-note.api {
  background: var(--accent-soft);
  color: var(--accent-press);
  border: 1px solid #a9e3db;
}
.wizard-mode-note.agent {
  background: var(--warn-bg);
  color: #6b3d05;
  border: 1px solid #f0d999;
}
.wizard-mode-note .mn-badge {
  flex-shrink: 0;
  font-weight: 700; font-size: 12px;
  padding: 3px 10px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.6);
}

/* Ghost button */
.wizard-btn-ghost {
  display: inline-flex; align-items: center; justify-content: center;
  gap: 8px;
  padding: 12px 26px;
  border-radius: 6px;
  font-size: 14px; font-weight: 600;
  cursor: pointer;
  font-family: inherit;
  background: var(--surface);
  border: 2px solid var(--line);
  color: var(--text-body);
  transition: all 0.15s;
}
.wizard-btn-ghost:hover { border-color: var(--accent); color: var(--accent); }

/* Transient + bigspin (LOADING / SUBMITTING) */
.wizard-transient {
  position: absolute; inset: 0;
  display: flex; flex-direction: column;
  align-items: center; justify-content: center;
  gap: 18px;
  background: var(--surface);
}
.wizard-bigspin {
  width: 46px; height: 46px;
  border: 4px solid var(--accent-soft);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: wizardSpin 0.8s linear infinite;
}

/* Agent-mode wrapper (PROGRESS !hasApiKey) */
.wizard-agent-why {
  display: flex; gap: 12px;
  margin-top: 26px; max-width: 600px;
  padding: 14px 18px;
  background: var(--warn-bg);
  border: 1px solid #f0d999;
  border-radius: var(--radius-card);
  font-size: 13px; color: #6b3d05; line-height: 1.55;
}
.wizard-agent-steps {
  margin-top: 26px; max-width: 600px;
  display: flex; flex-direction: column; gap: 18px;
}
.wizard-astep { display: flex; gap: 14px; }
.wizard-astep .n {
  width: 26px; height: 26px;
  border-radius: 50%;
  flex-shrink: 0;
  background: var(--accent);
  color: #fff;
  display: flex; align-items: center; justify-content: center;
  font-size: 13px; font-weight: 700;
}
.wizard-astep .ac { flex: 1; }
.wizard-astep .ac .at { font-size: 14px; font-weight: 600; color: var(--text); margin: 2px 0 0; }
.wizard-astep .ac .ad { font-size: 13px; color: var(--muted); margin: 3px 0 0; }

.wizard-prog-note {
  margin-top: 22px;
  font-size: 13px; color: var(--muted);
  display: flex; align-items: center; gap: 8px;
  max-width: 560px;
}
```

- [ ] **Step 4: Run new shell test, verify all PASS**

```bash
npm test -- tests/wizard-shell-css.test.js
```
Expected: all pass.

- [ ] **Step 5: Run FIX-2 baseline test — no regression**

```bash
npm test -- tests/wizard-css-units.test.js
```
Expected: 3 pass.

- [ ] **Step 6: Run full JS suite**

```bash
npm test
```
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add docs/frontend-local-version-viewer/viewer/wizard.css \
        docs/frontend-local-version-viewer/viewer/tests/wizard-shell-css.test.js
git commit -m "feat(css): wizard.css Part 2 shell + rail + scoped font tokens

新增 .wizard-shell / .wizard-rail* / .wizard-door-* / .wizard-stepper / 
.wizard-content / .wizard-screen + wizardScreenIn/wizardThresholdOut keyframes
+ .wizard-eyebrow / .wizard-mode-note* / .wizard-btn-ghost / .wizard-transient
/ .wizard-bigspin / .wizard-agent-* / .wizard-prog-note。

--font-sans / --font-mono 限定 .wizard-shell 後代 scope（不入 styles.css :root，
避免主 Viewer 7 處 fallback silent regression，spec §1.3 B）。

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```
