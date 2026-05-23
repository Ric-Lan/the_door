# Stream B — Viewer 視覺套設計系統 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `design/The Door Design System/design_handoff_v1.1.1_diff_visuals/README.md` 的 design system 套用到 `docs/frontend-local-version-viewer/viewer/` 的 production 檔案，並對純邏輯函式補 vitest 單測。

**Architecture:** 維持 vanilla JS、無 build step、無 React。設計 reference `.jsx` 檔僅作 DOM/CSS 對照來源，不引入。改動分布在 `index.html`、`styles.css`、`js/ui-{topbar,list,detail,notes}.js`、`js/graph.js`、`mindmap-popup.html` + 2 個新檔 `js/diff-util.js`、`js/ui-doubt.js`。撤回設計 README 的 § 6 / § 7.4（與 "功能卡片維持原本顯示方式" 決議衝突）。

**Tech Stack:** vanilla JS（ES modules）、CSS custom properties、vitest（既有）、Cytoscape.js（既有，§ 9 改 style 不換 lib）

**Spec reference:**
- `consolidated-roadmap-2026-05-23/spec.md` § 3
- `design/The Door Design System/design_handoff_v1.1.1_diff_visuals/README.md`
- 3 個 mockup：`docs/frontend-local-version-viewer/viewer/mockup{,-graph,-mindmap}.html`

**Prereq:** stoic-spence #3 必須先落地 main（見 `02-prereq-stoic-spence-land.md`）

---

### Task 1: 對齊設計 tokens（§ 1）

**Files:**
- Modify: `docs/frontend-local-version-viewer/viewer/styles.css`（`:root` 區塊）

- [ ] **Step 1: 抽 design 端 tokens 對照表**

```bash
grep -n "^\s*--" design/The\ Door\ Design\ System/design_handoff_v1.1.1_diff_visuals/reference/colors_and_type.css
```

- [ ] **Step 2: 對照 production styles.css 的 :root 找缺漏**

```bash
grep -n "^\s*--" docs/frontend-local-version-viewer/viewer/styles.css | head -60
```

- [ ] **Step 3: 補齊缺漏 tokens**

依 README § 1 表，確保 production `:root` 至少包含：
`--accent`, `--accent-soft`, `--added-border/bg`, `--removed-border/bg`, `--modified-border/bg`, `--warn`, `--warn-bg`, `--warn-fg`。值要與 design 端**位元級一致**。

- [ ] **Step 4: Commit**

```bash
git add docs/frontend-local-version-viewer/viewer/styles.css
git commit -m "viewer: align design tokens with design system v1.1.2"
```

---

### Task 2: § 3.5 Logo state mapping — TDD pure function

**Files:**
- Modify: `docs/frontend-local-version-viewer/viewer/js/ui-topbar.js`
- Test: `docs/frontend-local-version-viewer/viewer/tests/ui-topbar.test.js`（新增或追加 describe block）

- [ ] **Step 1: 寫 failing test**

在 `tests/ui-topbar.test.js` 追加：

```js
import { resolveLogoState } from '../js/ui-topbar.js';

describe('resolveLogoState', () => {
  it('L3 layer overrides mode', () => {
    expect(resolveLogoState('diff', 'L3')).toBe('l3');
    expect(resolveLogoState('current', 'L3')).toBe('l3');
  });
  it('diff mode → diff logo', () => {
    expect(resolveLogoState('diff', 'L1')).toBe('diff');
    expect(resolveLogoState('diff', 'L2')).toBe('diff');
  });
  it('current mode → l2 logo', () => {
    expect(resolveLogoState('current', 'L1')).toBe('l2');
  });
  it('baseline mode → l1 logo', () => {
    expect(resolveLogoState('baseline', 'L1')).toBe('l1');
  });
  it('unknown mode falls back to l1', () => {
    expect(resolveLogoState('weird', 'L1')).toBe('l1');
  });
});
```

- [ ] **Step 2: 跑 test 確認 fail**

```bash
cd docs/frontend-local-version-viewer/viewer && npx vitest run tests/ui-topbar.test.js
```
Expected: FAIL（`resolveLogoState` not exported）。

- [ ] **Step 3: 實作**

在 `js/ui-topbar.js` 加：

```js
export function resolveLogoState(mode, layerState) {
  if (layerState === 'L3') return 'l3';
  if (mode === 'diff')      return 'diff';
  if (mode === 'current')   return 'l2';
  if (mode === 'baseline')  return 'l1';
  return 'l1';
}
```

並把現有 logo 切換點改呼叫此函式。

- [ ] **Step 4: Test 綠**

```bash
npx vitest run tests/ui-topbar.test.js
```
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add js/ui-topbar.js tests/ui-topbar.test.js
git commit -m "viewer(topbar): add resolveLogoState pure function (state-aware logo)"
```

---

### Task 3: § 3.3 Mode-switch dynamic labels + § 3.4 version selector pills

**Files:**
- Modify: `viewer/index.html`（替換 `#version-selector-bar` markup）
- Modify: `viewer/styles.css`（追加 `.version-selector-bar` / `.vsb-*` CSS）
- Modify: `viewer/js/ui-topbar.js`（mode-switch label 跟著 versionA/B 更新）

- [ ] **Step 1: 寫 mode-switch label resolver test**

```js
// tests/ui-topbar.test.js 追加
import { modeSwitchLabel } from '../js/ui-topbar.js';

describe('modeSwitchLabel', () => {
  const snapshots = [
    { version_id: 'v1', label: 'v1.0.0' },
    { version_id: 'v2', label: 'v1.0.5' },
  ];
  it('returns 差異 for diff', () => {
    expect(modeSwitchLabel('diff', 'v1', 'v2', snapshots)).toBe('差異');
  });
  it('baseline shows 版本 A label', () => {
    expect(modeSwitchLabel('baseline', 'v1', 'v2', snapshots)).toBe('版本 A · v1.0.0');
  });
  it('current shows 版本 B label', () => {
    expect(modeSwitchLabel('current', 'v1', 'v2', snapshots)).toBe('版本 B · v1.0.5');
  });
  it('unknown version → 版本 X · —', () => {
    expect(modeSwitchLabel('baseline', 'xxx', 'v2', snapshots)).toBe('版本 A · —');
  });
});
```

- [ ] **Step 2: 跑 test 確認 fail**

```bash
npx vitest run tests/ui-topbar.test.js -t modeSwitchLabel
```
Expected: FAIL。

- [ ] **Step 3: 實作 modeSwitchLabel**

```js
export function modeSwitchLabel(mode, versionA, versionB, snapshots) {
  if (mode === 'diff') return '差異';
  const id = mode === 'baseline' ? versionA : versionB;
  const tag = mode === 'baseline' ? 'A' : 'B';
  const label = snapshots.find(s => s.version_id === id)?.label ?? '—';
  return `版本 ${tag} · ${label}`;
}
```

- [ ] **Step 4: 替換 index.html 的 version selector markup**

照 design README § 3.4 抄完整 markup（兩個 `.vsb-pill`，A 紅 / B 綠）。

- [ ] **Step 5: 加 CSS**

複製 README § 3.4 的 verbatim CSS 區塊到 `styles.css`。

- [ ] **Step 6: 接 mode-switch render 呼叫新 helper**

在既有的 mode-switch render 處用 `modeSwitchLabel(...)` 計算 label，把按鈕文字綁上去。當使用者改 A/B 時觸發 re-render。

- [ ] **Step 7: 視覺驗證**

```bash
cd docs/frontend-local-version-viewer/viewer && python -m http.server 8765 &
```
開 `http://localhost:8765/index.html`，對照 `/mockup.html` 視覺。

- [ ] **Step 8: Test 綠 + commit**

```bash
npx vitest run
git add -A
git commit -m "viewer(topbar): dynamic mode-switch labels + redesigned version selector pills"
```

---

### Task 4: § 3.2 Risk filter button（clickable）

**Files:**
- Modify: `viewer/index.html`（`<span id="count-risk">` → `<button>`）
- Modify: `viewer/styles.css`（追加 `.count-risk-button` rules）
- Modify: `viewer/js/ui-topbar.js`（click handler 切換 `state.riskOnly`）
- Modify: `viewer/js/ui-list.js`（filter pipeline 讀 `state.riskOnly`）

- [ ] **Step 1: 寫 riskOnly filter pipeline test（pure function）**

把 risk filter 抽成 pure function：

```js
// tests/ui-list.test.js 追加
import { applyRiskFilter } from '../js/ui-list.js';

describe('applyRiskFilter', () => {
  const features = [
    { id: 'a', anomaly_count: 0, confidence: 'high' },
    { id: 'b', anomaly_count: 2, confidence: 'high' },
    { id: 'c', anomaly_count: 0, confidence: 'low' },
  ];
  it('passes through when riskOnly false', () => {
    expect(applyRiskFilter(features, false).map(f => f.id)).toEqual(['a','b','c']);
  });
  it('keeps anomaly OR low-confidence when riskOnly true', () => {
    expect(applyRiskFilter(features, true).map(f => f.id)).toEqual(['b','c']);
  });
});
```

- [ ] **Step 2: 跑 test 確認 fail**

```bash
npx vitest run tests/ui-list.test.js -t applyRiskFilter
```
Expected: FAIL（`applyRiskFilter` not exported）。

- [ ] **Step 3: 實作**

```js
// js/ui-list.js
export function applyRiskFilter(features, riskOnly) {
  if (!riskOnly) return features;
  return features.filter(f => f.anomaly_count > 0 || f.confidence === 'low');
}
```

- [ ] **Step 4: 換 markup + 接 click handler**

`index.html`：
```html
<button id="count-risk" type="button"
        class="count-badge count-risk count-risk-button"
        title="點擊只顯示需注意的項目"
        hidden>注意 0</button>
```

`ui-topbar.js`：把 click 接到 `state.riskOnly = !state.riskOnly` 並觸發 list re-render。`.active` class 反映狀態。

- [ ] **Step 5: 加 CSS**

抄 README § 3.2 的 `.count-risk-button` CSS。

- [ ] **Step 6: 接到 list render pipeline**

`ui-list.js` 的 render 入口呼叫 `applyRiskFilter(features, state.riskOnly)`。

- [ ] **Step 7: 加「啟用過濾條」UI**

`index.html` 在 cards-filter-bar 下方加 `<div class="cards-filter-active">`（hidden by default），當 `state.riskOnly === true` 時顯示「⚠ 僅顯示需注意項目」pill + 「顯示 N/M」counter + 「清除全部過濾」按鈕（clear 一鍵重置）。

- [ ] **Step 8: Test 綠 + commit**

```bash
npx vitest run
git add -A
git commit -m "viewer(topbar+list): clickable risk filter button with active strip"
```

---

### Task 5: § 4 Summary band per-mode + version tag

**Files:**
- Modify: `viewer/index.html`（加 `<span id="summary-version-tag">`）
- Modify: `viewer/styles.css`（追加 `.summary-version-tag`）
- Modify: `viewer/js/ui-topbar.js`（per-mode render summary）

- [ ] **Step 1: 寫 summary text 純函式 test**

```js
// tests/ui-topbar.test.js
import { renderSummaryText } from '../js/ui-topbar.js';

describe('renderSummaryText', () => {
  it('diff mode uses updateModel.summary', () => {
    const r = renderSummaryText('diff', {
      updateModel: { summary: 'X 變了' }, snapshots: [], versionA: '', versionB: '', l1Model: { features: [] }
    });
    expect(r.text).toBe('X 變了');
    expect(r.tag).toBe(null);
  });
  it('baseline mode shows version tag + count', () => {
    const r = renderSummaryText('baseline', {
      snapshots: [{ version_id: 'a', label: 'v1.0.0' }],
      versionA: 'a', versionB: 'a',
      l1Model: { features: [{}, {}, {}] },
    });
    expect(r.tag).toBe('v1.0.0');
    expect(r.text).toContain('3 個 L1');
  });
});
```

- [ ] **Step 2: Fail → 實作 → Pass**

```js
export function renderSummaryText(mode, state) {
  if (mode === 'diff') {
    return { tag: null, text: state.updateModel?.summary ?? '尚未有分析報告。' };
  }
  const id = mode === 'baseline' ? state.versionA : state.versionB;
  const label = state.snapshots.find(s => s.version_id === id)?.label ?? '—';
  const count = state.l1Model?.features?.length ?? 0;
  return { tag: label, text: `${label} 共有 ${count} 個 L1 功能。` };
}
```

- [ ] **Step 3: 把 render 串到 DOM**

`#summary-version-tag` show/hide + `#summary-text` 內容更新。

- [ ] **Step 4: Visual verify + commit**

```bash
npx vitest run
git add -A
git commit -m "viewer(summary): per-mode summary text + version tag"
```

---

### Task 6: § 5 Cards filter bar — 信心 / 類型 / 排序

**Files:**
- Modify: `viewer/js/ui-list.js`
- Modify: `viewer/styles.css`
- Modify: `viewer/index.html`（加 `.cards-filter-bar` 容器）
- Test: `viewer/tests/ui-list.test.js`

- [ ] **Step 1: 寫 filter pipeline test（含三個維度）**

```js
import { applyCardFilters, sortCards } from '../js/ui-list.js';

describe('applyCardFilters', () => {
  const fs = [
    { id: 'a', confidence: 'high', change_type: 'added' },
    { id: 'b', confidence: 'medium', change_type: 'attribute_changed' },
    { id: 'c', confidence: 'low', change_type: null },
  ];
  it('confidence filter 僅高', () => {
    expect(applyCardFilters(fs, { conf: 'high' }).map(f => f.id)).toEqual(['a']);
  });
  it('confidence 非高 keeps medium + low', () => {
    expect(applyCardFilters(fs, { conf: 'not-high' }).map(f => f.id)).toEqual(['b','c']);
  });
  it('type 修改 covers attribute_changed and dependency_changed', () => {
    const x = [{ change_type: 'attribute_changed' }, { change_type: 'dependency_changed' }, { change_type: 'added' }];
    expect(applyCardFilters(x, { type: 'modified' }).length).toBe(2);
  });
});

describe('sortCards', () => {
  it('risk default: anomaly + low conf first', () => {
    const xs = [
      { id: 'safe', anomaly_count: 0, confidence: 'high' },
      { id: 'lowc', anomaly_count: 0, confidence: 'low' },
      { id: 'anom', anomaly_count: 2, confidence: 'high' },
    ];
    expect(sortCards(xs, 'risk').map(x => x.id)).toEqual(['anom', 'lowc', 'safe']);
  });
});
```

- [ ] **Step 2: Fail → 實作 → Pass**

```js
const CONF_PRIORITY = { low: 0, medium: 1, high: 2 };
const TYPE_PRIORITY = { removed: 0, attribute_changed: 1, dependency_changed: 1, added: 2, null: 9 };

export function applyCardFilters(features, { conf, type } = {}) {
  return features.filter(f => {
    if (conf === 'high'   && f.confidence !== 'high') return false;
    if (conf === 'medium' && f.confidence !== 'medium') return false;
    if (conf === 'low'    && f.confidence !== 'low') return false;
    if (conf === 'not-high' && f.confidence === 'high') return false;
    if (type === 'added'    && f.change_type !== 'added') return false;
    if (type === 'removed'  && f.change_type !== 'removed') return false;
    if (type === 'modified' && !['attribute_changed','dependency_changed'].includes(f.change_type)) return false;
    if (type === 'none'     && f.change_type != null) return false;
    return true;
  });
}

export function sortCards(features, mode) {
  const arr = [...features];
  if (mode === 'risk' || !mode) {
    return arr.sort((a, b) => {
      const ra = (a.anomaly_count > 0 ? 0 : 1) * 10 + (CONF_PRIORITY[a.confidence] ?? 2);
      const rb = (b.anomaly_count > 0 ? 0 : 1) * 10 + (CONF_PRIORITY[b.confidence] ?? 2);
      return ra - rb;
    });
  }
  if (mode === 'alpha')  return arr.sort((a, b) => (a.label ?? '').localeCompare(b.label ?? ''));
  if (mode === 'source') return arr.sort((a, b) => (b.source_nodes?.length ?? 0) - (a.source_nodes?.length ?? 0));
  if (mode === 'type')   return arr.sort((a, b) => (TYPE_PRIORITY[a.change_type] ?? 9) - (TYPE_PRIORITY[b.change_type] ?? 9));
  return arr;
}
```

- [ ] **Step 3: 加 markup + CSS（filter bar UI）**

照 mockup.html 的 `.cards-filter-bar` block 抄 markup + CSS。

⚠️ **不要加** README § 5.1 撤回的 search input 與 L1/L2/L3 chips。  
⚠️ **不要動** feature card 本體 layout（per consolidated spec § 3.2 決議：卡片維持原狀）。

- [ ] **Step 4: 接到 render pipeline**

`ui-list.js` 的 render 入口：`applyRiskFilter` → `applyCardFilters` → `sortCards` → render。

- [ ] **Step 5: 類型 dropdown 在非 diff 模式 hidden**

```js
document.querySelector('.cards-filter-bar .type-select')?.toggleAttribute('hidden', state.mode !== 'diff');
```

- [ ] **Step 6: Test 綠 + commit**

```bash
npx vitest run
git add -A
git commit -m "viewer(list): filter bar (信心/類型/排序) with pure pipeline"
```

---

### Task 7: § 7.3 Word-diff util（新檔，TDD）

**Files:**
- Create: `viewer/js/diff-util.js`
- Test: `viewer/tests/diff-util.test.js`

- [ ] **Step 1: 寫 failing test**

```js
// tests/diff-util.test.js
import { wordDiff, tokenize } from '../js/diff-util.js';

describe('tokenize', () => {
  it('CJK chars are individual tokens', () => {
    expect(tokenize('你好世界')).toEqual(['你','好','世','界']);
  });
  it('ASCII words stay as units', () => {
    expect(tokenize('hello world')).toEqual(['hello',' ','world']);
  });
  it('mixed CJK + ASCII', () => {
    expect(tokenize('我 use API')).toEqual(['我',' ','use',' ','API']);
  });
});

describe('wordDiff', () => {
  it('identical strings → all equal', () => {
    const r = wordDiff('hello', 'hello');
    expect(r.every(seg => seg.type === 'equal')).toBe(true);
  });
  it('appending text → equal + add', () => {
    const r = wordDiff('hello', 'hello world');
    expect(r.find(s => s.type === 'add')?.text).toContain('world');
  });
  it('CJK token-level diff', () => {
    const r = wordDiff('使用者可在設定頁查看', '使用者可在通知中心查看');
    expect(r.some(s => s.type === 'remove' && s.text.includes('設定'))).toBe(true);
    expect(r.some(s => s.type === 'add' && s.text.includes('通知'))).toBe(true);
  });
});
```

- [ ] **Step 2: Fail**

```bash
npx vitest run tests/diff-util.test.js
```
Expected: FAIL（module not found）。

- [ ] **Step 3: 實作 ~70 行 LCS-based diff**

```js
// js/diff-util.js
const CJK_RE = /[　-〿㐀-䶿一-鿿豈-﫿]/;

export function tokenize(s) {
  const out = [];
  let buf = '';
  for (const ch of s) {
    if (CJK_RE.test(ch)) {
      if (buf) { out.push(buf); buf = ''; }
      out.push(ch);
    } else if (/\s/.test(ch)) {
      if (buf) { out.push(buf); buf = ''; }
      out.push(ch);
    } else if (/[^\w]/.test(ch)) {
      if (buf) { out.push(buf); buf = ''; }
      out.push(ch);
    } else {
      buf += ch;
    }
  }
  if (buf) out.push(buf);
  return out;
}

function lcs(a, b) {
  const m = a.length, n = b.length;
  const dp = Array.from({ length: m + 1 }, () => new Int32Array(n + 1));
  for (let i = m - 1; i >= 0; i--)
    for (let j = n - 1; j >= 0; j--)
      dp[i][j] = a[i] === b[j] ? dp[i+1][j+1] + 1 : Math.max(dp[i+1][j], dp[i][j+1]);
  const ops = [];
  let i = 0, j = 0;
  while (i < m && j < n) {
    if (a[i] === b[j])               { ops.push({ type: 'equal',  text: a[i] }); i++; j++; }
    else if (dp[i+1][j] >= dp[i][j+1]) { ops.push({ type: 'remove', text: a[i] }); i++; }
    else                              { ops.push({ type: 'add',    text: b[j] }); j++; }
  }
  while (i < m) ops.push({ type: 'remove', text: a[i++] });
  while (j < n) ops.push({ type: 'add',    text: b[j++] });
  // merge consecutive same-type
  const merged = [];
  for (const o of ops) {
    const last = merged[merged.length - 1];
    if (last && last.type === o.type) last.text += o.text;
    else merged.push({ ...o });
  }
  return merged;
}

export function wordDiff(before, after) {
  return lcs(tokenize(before), tokenize(after));
}
```

- [ ] **Step 4: Test 綠**

```bash
npx vitest run tests/diff-util.test.js
```
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add js/diff-util.js tests/diff-util.test.js
git commit -m "viewer(diff-util): CJK-aware word-level diff (LCS, ~70 lines)"
```

---

### Task 8: § 7 Detail panel — sticky header/tabs + section reorder + warning banner + Before/After

**Files:**
- Modify: `viewer/js/ui-detail.js`
- Modify: `viewer/styles.css`
- Modify: `viewer/tests/ui-detail.test.js`（既有 test 需同步調整）

- [ ] **Step 1: 看既有 ui-detail.test.js 哪些 case 會被 break**

```bash
grep -n "describe\|it(" docs/frontend-local-version-viewer/viewer/tests/ui-detail.test.js | head -30
```

把會被新 section order 影響的 case 標記出來，等 Step 4 同步修。

- [ ] **Step 2: 加 sticky CSS（純樣式無 test）**

抄 README § 7.2 進 styles.css：

```css
.detail-panel .panel-header.sticky { position: sticky; top: 0; z-index: 2; background: var(--surface); }
.detail-panel .detail-tabs.sticky  { position: sticky; top: var(--detail-header-h, 56px); z-index: 1; background: var(--surface); }
```

- [ ] **Step 3: 改 render 加 warning banner（pure render function）**

把 warning banner 抽純函式：

```js
export function shouldShowWarningBanner(feature) {
  return feature?.change_type === 'added' && feature?.confidence === 'low';
}
```

加 test：

```js
import { shouldShowWarningBanner } from '../js/ui-detail.js';
describe('shouldShowWarningBanner', () => {
  it('true only when added + low confidence', () => {
    expect(shouldShowWarningBanner({ change_type: 'added', confidence: 'low' })).toBe(true);
    expect(shouldShowWarningBanner({ change_type: 'added', confidence: 'high' })).toBe(false);
    expect(shouldShowWarningBanner({ change_type: 'attribute_changed', confidence: 'low' })).toBe(false);
    expect(shouldShowWarningBanner(null)).toBe(false);
  });
});
```

實作 banner DOM：照 README § 7.4 markup。

- [ ] **Step 4: Render Before/After（attribute_changed only）**

import wordDiff from diff-util.js。給定 feature 的 before/after description，跑 `wordDiff(before, after)` 並依照 README § 7.3 的規則：
- Before panel 渲染 `equal + remove` segments，`remove` 包 `<mark class="diff-mark diff-mark-remove">`
- After panel 渲染 `equal + add`，`add` 包 `<mark class="diff-mark diff-mark-add">`

加對應 CSS（README § 7.3 verbatim）。

- [ ] **Step 5: Section 重排**

依 README § 7.1 順序：warning → 描述 → Before/After → 差異推論 → Source nodes → 信心 → 疑義 → attribution。

⚠️ § 7.4 在 **detail panel** 內的 warning banner **保留**（與 § 3.2 撤回的 card-level danger chip 不同）。

- [ ] **Step 6: 同步既有 test**

把 Step 1 標記的 case 依新 section 順序更新。不要刪 test 來「解決」test fail，要改 expectation。

- [ ] **Step 7: Test 全綠 + visual verify**

```bash
npx vitest run
```
開 viewer 對比 mockup.html。

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "viewer(detail): sticky header/tabs + warning banner + Before/After word-diff + section reorder"
```

⚠️ 此 Task 是與 **Stream C** 衝突最深的點（C 也想動 `renderStructuralDiffDetail`）。執行此 Task 前先讀 `02-prereq-stoic-spence-land.md` 已完成、並參考 `04-stream-c-diff-detail.md` 的決策。

---

### Task 9: § 7.5 Notes tab — collapsed form + card list + relative time

**Files:**
- Modify: `viewer/js/ui-notes.js`
- Modify: `viewer/styles.css`
- Test: `viewer/tests/ui-notes.test.js`（若不存在則新增）

- [ ] **Step 1: 寫 relative time test**

```js
import { relativeTime } from '../js/ui-notes.js';

describe('relativeTime', () => {
  const now = new Date('2026-05-23T12:00:00Z').getTime();
  it('seconds → 剛剛', () => {
    expect(relativeTime(now - 30 * 1000, now)).toBe('剛剛');
  });
  it('minutes', () => {
    expect(relativeTime(now - 5 * 60 * 1000, now)).toBe('5 分鐘前');
  });
  it('hours', () => {
    expect(relativeTime(now - 3 * 3600 * 1000, now)).toBe('3 小時前');
  });
  it('days', () => {
    expect(relativeTime(now - 2 * 86400 * 1000, now)).toBe('2 天前');
  });
  it('older than 7d falls back to UTC MM-DD HH:MM', () => {
    const past = new Date('2026-04-01T08:30:00Z').getTime();
    expect(relativeTime(past, now)).toBe('04-01 08:30');
  });
});
```

- [ ] **Step 2: Fail → 實作**

```js
export function relativeTime(ts, now = Date.now()) {
  const diff = now - ts;
  if (diff < 60_000) return '剛剛';
  if (diff < 3600_000) return `${Math.floor(diff/60_000)} 分鐘前`;
  if (diff < 86400_000) return `${Math.floor(diff/3600_000)} 小時前`;
  if (diff < 7 * 86400_000) return `${Math.floor(diff/86400_000)} 天前`;
  const d = new Date(ts);
  const pad = n => String(n).padStart(2,'0');
  // 用 UTC 避免測試在非整點 offset 時區（如 +5:30）flaky
  return `${pad(d.getUTCMonth()+1)}-${pad(d.getUTCDate())} ${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}`;
}
```

- [ ] **Step 3: 改 notes DOM**

照 README § 7.5：
- 默認顯示 dashed `+ 新增備註` 按鈕；click 展開 form 卡片（名稱 input + 意見 textarea + 取消/新增 button）
- Notes list 用 `<article class="user-note-card">`（不是 `<details>`）
- 每筆 note：header 名稱（700/13）左 + relative time（11px muted）右；body `white-space: pre-wrap`

加 CSS。

- [ ] **Step 4: Tab strip styling**

照 README § 7.5 表抄。

- [ ] **Step 5: 接 `_appendUserNotesSection` 既有 hook**

確認 mode-switch / layer-drill / feature-change 時 tab 重置為「詳情」（README § 2.4 表）。

- [ ] **Step 6: Test 綠 + commit**

```bash
npx vitest run
git add -A
git commit -m "viewer(notes): collapsed form + card list + relative time"
```

---

### Task 10: § 8 Doubts view — 新檔 ui-doubt.js

**Files:**
- Create: `viewer/js/ui-doubt.js`
- Modify: `viewer/js/ui-notes.js`（加 `mode='doubt'` 參數）

- [ ] **Step 1: 寫 status badge mapping test**

```js
// tests/ui-doubt.test.js
import { statusBadge } from '../js/ui-doubt.js';

describe('statusBadge', () => {
  it('open → 未解決 low palette', () => {
    expect(statusBadge('open')).toEqual({ className: 'confidence-badge confidence-badge-low', label: '未解決' });
  });
  it('assigned → 處理中 medium', () => {
    expect(statusBadge('assigned').label).toBe('處理中');
  });
  it('resolved → 已解決 high', () => {
    expect(statusBadge('resolved').label).toBe('已解決');
  });
  it('escalated → custom red', () => {
    expect(statusBadge('escalated').label).toBe('已升級');
  });
  it('unknown → fallback to open', () => {
    expect(statusBadge('garbage').label).toBe('未解決');
  });
});
```

- [ ] **Step 2: Fail → 實作 statusBadge 純函式**

```js
const MAP = {
  open:     { className: 'confidence-badge confidence-badge-low',    label: '未解決' },
  assigned: { className: 'confidence-badge confidence-badge-medium', label: '處理中' },
  resolved: { className: 'confidence-badge confidence-badge-high',   label: '已解決' },
  escalated:{ className: 'confidence-badge confidence-badge-escalated', label: '已升級' },
};
export function statusBadge(status) {
  return MAP[status] ?? MAP.open;
}
```

加 `.confidence-badge-escalated { background: #dc3545; color: #fff; }` 到 styles.css。

- [ ] **Step 3: Render doubt detail panel**

照 README § 8 結構：sticky header + tabs（詳情/備註）+ 詳情 tab 內 fixed 欄位順序：異常類型 / 說明 / 狀態 / 指派對象 / 建立時間 / 來源功能 / 解決原因 / 升級歷史 / attribution。

- [ ] **Step 4: notes 復用**

`ui-notes.js` 加 `mode` 參數：`mode='feature'`（既有，scope key = versionA/B + featureId）／`mode='doubt'`（versionA=null, versionB=null, scope key = doubtId）。

- [ ] **Step 5: Test 綠 + commit**

```bash
npx vitest run
git add -A
git commit -m "viewer(doubt): doubt detail view with status badges + notes reuse"
```

---

### Task 11: § 9 Relation graph — Cytoscape style block

**Files:**
- Modify: `viewer/js/graph.js`（`buildCytoscapeStyle()` + `buildCytoscapeElements()`）

- [ ] **Step 1: 寫 displayLabel 純函式 test**

```js
// tests/graph.test.js 追加
import { buildDisplayLabel } from '../js/graph.js';

describe('buildDisplayLabel', () => {
  it('prepends type tag for added', () => {
    expect(buildDisplayLabel({ label: 'Foo', change_type: 'added' })).toBe('+ 新增\nFoo');
  });
  it('no tag when change_type missing', () => {
    expect(buildDisplayLabel({ label: 'Foo' })).toBe('Foo');
  });
  it('dependency_changed → ≠ 依賴', () => {
    expect(buildDisplayLabel({ label: 'X', change_type: 'dependency_changed' })).toBe('≠ 依賴\nX');
  });
});
```

- [ ] **Step 2: Fail → 實作**

```js
const TYPE_TAG = {
  added:              '+ 新增',
  removed:            '− 移除',
  attribute_changed:  '~ 修改',
  dependency_changed: '≠ 依賴',
};
export function buildDisplayLabel(node) {
  const tag = TYPE_TAG[node.change_type];
  return tag ? `${tag}\n${node.label}` : node.label;
}
```

把 `buildCytoscapeElements` 改成在 `data` 加 `displayLabel: buildDisplayLabel(node)`。

- [ ] **Step 3: 改 buildCytoscapeStyle 用 displayLabel + 新色票**

照 README § 9.1 抄樣式 block：
- default node：pale `#fbfcfd` + border `#d7dde5` + dark text `#17202a`
- 各 change_type 用設計系統色票（pale fill + saturated border）
- 信心 → border-style（既有規則保留）
- selected → `border-color: #0f766e`, 4px solid

- [ ] **Step 4: 移除 text-outline + 改字級**

`text-outline-width: 0`、`font-size: '24px'`（README 指定）。

- [ ] **Step 5: Test 綠 + visual verify**

```bash
npx vitest run tests/graph.test.js
```
開 viewer 切到 relation graph 對照 `/mockup-graph.html`。

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "viewer(graph): pale fill + saturated border node style with type-tag displayLabel"
```

---

### Task 12: § 10 Mindmap badges + L1 sizing + toolbar legend + guide panel

**Files:**
- Create: `viewer/js/mindmap-util.js`（抽 badge 選擇純函式以利測試）
- Test: `viewer/tests/mindmap-util.test.js`
- Modify: `viewer/mindmap-popup.html`（**只動 4 個 block，不動 layout 與 #info-panel**）

- [ ] **Step 0: 寫 failing test — selectDiffBadge 純函式**

```js
// tests/mindmap-util.test.js
import { selectDiffBadge, DIFF_BADGE } from '../js/mindmap-util.js';

describe('selectDiffBadge', () => {
  it('returns null when node id not in diffNodes', () => {
    expect(selectDiffBadge('foo', [])).toBeNull();
    expect(selectDiffBadge('foo', [{ id: 'bar', change_type: 'added' }])).toBeNull();
  });
  it('returns added badge with correct palette + text', () => {
    const b = selectDiffBadge('x', [{ id: 'x', change_type: 'added' }]);
    expect(b).toBe(DIFF_BADGE.added);
    expect(b.text).toBe('+ 新增');
    expect(b.fill).toBe('#d4edda');
  });
  it('removed badge', () => {
    expect(selectDiffBadge('x', [{ id: 'x', change_type: 'removed' }]).text).toBe('− 移除');
  });
  it('attribute_changed → ~ 修改', () => {
    expect(selectDiffBadge('x', [{ id: 'x', change_type: 'attribute_changed' }]).text).toBe('~ 修改');
  });
  it('dependency_changed reuses modified palette but distinct text', () => {
    const b = selectDiffBadge('x', [{ id: 'x', change_type: 'dependency_changed' }]);
    expect(b.text).toBe('≠ 依賴');
    expect(b.fill).toBe('#ffe0cc');
  });
  it('unknown change_type → null', () => {
    expect(selectDiffBadge('x', [{ id: 'x', change_type: 'weird' }])).toBeNull();
  });
  it('null diffNodes safe', () => {
    expect(selectDiffBadge('x', null)).toBeNull();
  });
});
```

- [ ] **Step 0.1: Fail**

```bash
npx vitest run tests/mindmap-util.test.js
```
Expected: FAIL（module not found）。

- [ ] **Step 0.2: 實作 mindmap-util.js**

```js
// js/mindmap-util.js
export const DIFF_BADGE = {
  added:              { fill: "#d4edda", stroke: "#28a745", color: "#1d6e34", text: "+ 新增" },
  removed:            { fill: "#f8d7da", stroke: "#dc3545", color: "#9a1a1a", text: "− 移除" },
  attribute_changed:  { fill: "#ffe0cc", stroke: "#fd7e14", color: "#7a4e00", text: "~ 修改" },
  dependency_changed: { fill: "#ffe0cc", stroke: "#fd7e14", color: "#7a4e00", text: "≠ 依賴" },
};

export function selectDiffBadge(nodeId, diffNodes) {
  const entry = (diffNodes ?? []).find(d => d.id === nodeId);
  if (!entry) return null;
  return DIFF_BADGE[entry.change_type] ?? null;
}
```

L1 尺寸（160×36）為純視覺常數、且 mindmap-popup.html 的 SVG layout 演算法仍維持現況（spec § 3.2 決議），不需抽出。**徽章邏輯是有條件分支的程式碼，必須抽到 util 以避免兩份 copy 飄移。**

- [ ] **Step 0.3: Test 綠**

```bash
npx vitest run tests/mindmap-util.test.js
```
Expected: PASS。

- [ ] **Step 1: 改 L1 sizing 常數**

```bash
grep -n "L1_W\|L1_H" docs/frontend-local-version-viewer/viewer/mindmap-popup.html
```

把 `L1_W = 148, L1_H = 46` 改成 `L1_W = 160, L1_H = 36`。

- [ ] **Step 2: 讓 mindmap-popup.html 從 mindmap-util.js 取 badge 邏輯**

定位 `<script>` 區塊改為 ES module，並 import：

```html
<script type="module">
import { selectDiffBadge } from './js/mindmap-util.js';
// ...既有程式碼...
</script>
```

定位 `buildSVG` 內畫 `Δ 有差異` 的區段，改為：

```js
const badge = selectDiffBadge(node.id, data.diffNodes);
if (badge) {
  // render pill rect width:56 height:14 rx:7 + 9px text
  // 用 badge.fill / badge.stroke / badge.color / badge.text
}
```

⚠️ 不要在 mindmap-popup.html 內再內聯一份 `DIFF_BADGE` map — 單一來源在 `mindmap-util.js`，靠 Step 0 的 test 防止飄移。

- [ ] **Step 3: Recolor anomaly badge**

把現有 `⚠ N`（純色 `#FF6D00`）改為：
- rect fill `#fef3c7`、stroke `#b45309`
- text fill `#855207`
- text content：`⚠ 注意 N`（不是 `⚠ N`）
- width:52, height:14, rx:7

兩種徽章同時存在時：anomaly 在左、diff 在右（per README § 10.3）。

- [ ] **Step 4: Toolbar legend**

把現有 `tb-badge-orange ⚠ N` / `tb-badge-blue Δ 有差異` 兩個整段換成 5 個 badge：

```html
<span class="tb-badge tb-badge-anom">⚠ 注意</span><span class="tb-hint">異常</span>
<span class="tb-divider">|</span>
<span class="tb-badge tb-badge-added">+ 新增</span>
<span class="tb-badge tb-badge-removed">− 移除</span>
<span class="tb-badge tb-badge-modified">~ 修改</span><span class="tb-hint">版本差異</span>
```

加 CSS（4 個 `.tb-badge-*` per README § 10.5）。

- [ ] **Step 5: Guide panel**

`<aside id="guide-panel">` 內把舊的 gb-diff / gb-anom 行替換成五個徽章解釋（4 diff + 1 anomaly），照 `mockup-mindmap.html` 第 5 段對照。

- [ ] **Step 6: 視覺驗證**

開 mindmap-popup（透過 viewer 內的 `🧠 心智圖` 按鈕），確認：
- L1 節點變寬變矮
- 各 change_type 顯示對應顏色徽章
- anomaly 徽章用 warn-yellow
- 兩 badge 並排不重疊
- **右側 #info-panel 與整體 layout 完全沒變**（驗證 § 10 邊界遵守）

- [ ] **Step 7: Commit**

```bash
git add docs/frontend-local-version-viewer/viewer/mindmap-popup.html
git commit -m "viewer(mindmap): type-aware diff badges + warn-palette anomaly badge + new L1 sizing"
```

---

### Task 13: Cleanup — 移除 mockup 檔

**Files:**
- Delete: `viewer/mockup.html`、`viewer/mockup-graph.html`、`viewer/mockup-mindmap.html`

- [ ] **Step 1: 確認 production 已對齊 mockup**

最後一輪 visual review：production index.html / 關聯圖 / 心智圖 全部對得上 mockup 樣式。

- [ ] **Step 2: 刪除 mockup**

```bash
git rm docs/frontend-local-version-viewer/viewer/mockup.html
git rm docs/frontend-local-version-viewer/viewer/mockup-graph.html
git rm docs/frontend-local-version-viewer/viewer/mockup-mindmap.html
```

- [ ] **Step 3: Commit**

```bash
git commit -m "chore(viewer): remove mockup files (production now matches design)"
```

---

## Self-review checklist（Task 全部完成後）

- [ ] 既有 vitest 套件全綠不退化
- [ ] 新增 pure functions 都有 unit test：`resolveLogoState` / `modeSwitchLabel` / `applyRiskFilter` / `applyCardFilters` / `sortCards` / `wordDiff` / `tokenize` / `shouldShowWarningBanner` / `relativeTime` / `statusBadge` / `buildDisplayLabel` / `renderSummaryText` / `selectDiffBadge`
- [ ] 視覺對照三個 mockup 全部一致
- [ ] **沒有**新增：`feature-card-source-chip` / `feature-card-anomaly-chip` / `feature-card-danger`（§ 6 / § 7.4 已撤回）
- [ ] **沒有**動：mindmap layout 算法、`#info-panel`、feature card DOM 結構（`<button>` + label/desc/meta）
- [ ] 不引入 React / 任何 build step
