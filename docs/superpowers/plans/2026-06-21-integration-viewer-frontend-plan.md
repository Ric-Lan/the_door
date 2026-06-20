# 整合健檢 viewer — 前端 Plan（徽章 + 面板 + 連動）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`).
> **前置**：後端 plan（`2026-06-21-integration-viewer-backend-plan.md`）已完成——`GET /api/integration` 可用、回 `{relations[], features{id:verdict}, rollup{}}`（缺結構時 `structure_missing:true`）。

**Goal:** viewer 以單一 `state.integration` 驅動：功能卡徽章（✅/❌/⚠）+ 獨立「整合健檢」面板，面板點 gap 連動選中對應功能卡。

**Architecture:** 純函式（`featureVerdict`/`integrationBadge`/面板渲染）集中在新檔 `js/ui-integration.js`；`api.js` 加 `fetchIntegration`、`state.js` 加 `integration` slice、載入流程與 L1 同步取；`ui-list.js` 的卡片在 `.feature-card-meta` 追加徽章。兩處都讀同一 slice ⇒ 天然一致。

**Tech Stack:** vanilla ES modules、vitest（jsdom）。

**對應 spec：** [`docs/superpowers/specs/2026-06-21-integration-viewer-design.md`](../specs/2026-06-21-integration-viewer-design.md) §3.3–§3.4、§5、§6。

## 環境
- viewer 唯一正式版＝`docs/frontend-local-version-viewer/viewer/`（⛔ 勿動 `prototype/`）。
- 測試 cwd ＝ `docs/frontend-local-version-viewer/viewer/`；指令 `npx vitest run <file>`（或 `npm test`）。
- branch 護欄：commit 前 `git rev-parse --abbrev-ref HEAD` 須為 `feat/integration-viewer`。
- commit 結尾 `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`。
- 改前端**不需 build**，重啟 `the-door ui <test-target>` 即生效（驗收用，非自動化測試）。

## File Structure
- Create: `viewer/js/ui-integration.js`（純函式 + 面板渲染 + 徽章）
- Modify: `viewer/js/api.js`（`fetchIntegration`）、`viewer/js/state.js`（`integration` slice）
- Modify: `viewer/js/ui-list.js`（卡片追加徽章）
- Modify: `viewer/js/app.js`（載入時取 integration、render 面板、接選取 callback）
- Create tests: `viewer/tests/ui-integration.test.js`；Modify: `viewer/tests/ui-list.test.js`（徽章）

---

### Task 1: state slice + api.js + 純判定/徽章函式

**Files:**
- Modify: `viewer/js/state.js`、`viewer/js/api.js`
- Create: `viewer/js/ui-integration.js`
- Create: `viewer/tests/ui-integration.test.js`

- [ ] **Step 1: 寫失敗測試（純函式）**

Create `viewer/tests/ui-integration.test.js`:
```javascript
import { describe, it, expect } from 'vitest';
import { featureVerdict, integrationBadge } from '../js/ui-integration.js';

describe('featureVerdict', () => {
  const integ = { features: { a: 'gap', b: 'backed', c: 'undetermined', d: 'none' } };
  it('returns verdict for a known feature', () => {
    expect(featureVerdict(integ, 'a')).toBe('gap');
    expect(featureVerdict(integ, 'b')).toBe('backed');
  });
  it('returns null for "none" (no static deps)', () => {
    expect(featureVerdict(integ, 'd')).toBe(null);
  });
  it('returns null when missing or no integration', () => {
    expect(featureVerdict(integ, 'zzz')).toBe(null);
    expect(featureVerdict(null, 'a')).toBe(null);
  });
});

describe('integrationBadge', () => {
  it('builds a span with the right symbol+class for gap', () => {
    const el = integrationBadge('gap');
    expect(el.tagName).toBe('SPAN');
    expect(el.classList.contains('integration-badge')).toBe(true);
    expect(el.classList.contains('integration-gap')).toBe(true);
    expect(el.textContent).toContain('❌');
  });
  it('uses ✅ for backed, ⚠ for undetermined', () => {
    expect(integrationBadge('backed').textContent).toContain('✅');
    expect(integrationBadge('undetermined').textContent).toContain('⚠');
  });
  it('returns null for null/none', () => {
    expect(integrationBadge(null)).toBe(null);
    expect(integrationBadge('none')).toBe(null);
  });
});
```

- [ ] **Step 2: 跑測試確認失敗**

Run（cwd = viewer）: `npx vitest run tests/ui-integration.test.js`
Expected: FAIL（`../js/ui-integration.js` 不存在）。

- [ ] **Step 3: 建 ui-integration.js（純函式部分）**

Create `viewer/js/ui-integration.js`:
```javascript
// 整合健檢：純判定/徽章/面板。資料一律來自 state.integration（單一真相）。

const BADGE = {
  gap:          { sym: '❌', cls: 'integration-gap',          title: '宣稱要連、結構上沒接上' },
  undetermined: { sym: '⚠',  cls: 'integration-undetermined', title: '目標非程式碼節點，無法判定' },
  backed:       { sym: '✅', cls: 'integration-backed',        title: '宣稱的依賴有結構連線支撐' },
};

// 回傳 'gap'|'undetermined'|'backed'，或 null（none / 缺資料 ⇒ 不顯示徽章）
export function featureVerdict(integration, featureId) {
  const v = integration?.features?.[featureId];
  return v && v !== 'none' ? v : null;
}

// 回傳徽章 span，或 null
export function integrationBadge(verdict) {
  const spec = verdict && BADGE[verdict];
  if (!spec) return null;
  const el = document.createElement('span');
  el.className = 'integration-badge ' + spec.cls;
  el.title = spec.title;
  el.textContent = spec.sym;
  return el;
}
```

- [ ] **Step 4: 跑測試確認通過**

Run: `npx vitest run tests/ui-integration.test.js`
Expected: PASS。

- [ ] **Step 5: state slice + api.js**

`viewer/js/state.js`：在物件內加一行（與其他 model slice 並列）：
```javascript
  integration: null,
```

`viewer/js/api.js`：比照 `fetchL1Graph` 加：
```javascript
export async function fetchIntegration(versionId = null) {
  const url = versionId
    ? `${API_BASE}/api/integration?version_id=${encodeURIComponent(versionId)}`
    : `${API_BASE}/api/integration`;
  const res = await fetch(url, { cache: "no-store" });
  return res.json();
}
```

- [ ] **Step 6: Commit**
```bash
git add viewer/js/ui-integration.js viewer/js/state.js viewer/js/api.js viewer/tests/ui-integration.test.js
git commit -m "feat(viewer): integration state slice + fetch + verdict/badge helpers" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```
（cwd 在 viewer；路徑相對 viewer。）

---

### Task 2: 功能卡徽章（ui-list 追加，讀 state.integration）

**Files:**
- Modify: `viewer/js/ui-list.js`
- Modify: `viewer/tests/ui-list.test.js`

- [ ] **Step 1: 寫失敗測試（卡片含整合徽章）**

在 `viewer/tests/ui-list.test.js` 末端追加（檔案已 import `featureCard`、`state`；徽章由 `featureCard` 內部讀 `state.integration` 產生，測試不需另 import）：
```javascript
describe('featureCard integration badge', () => {
  it('appends ❌ badge when feature verdict is gap', () => {
    state.integration = { features: { 'feat-1': 'gap' } };
    const card = featureCard({ id: 'feat-1', label: 'F1', confidence: 'high' }, false, {});
    expect(card.querySelector('.integration-badge.integration-gap')).not.toBeNull();
    state.integration = null;
  });
  it('no integration badge when verdict is none/missing', () => {
    state.integration = { features: { 'feat-1': 'none' } };
    const card = featureCard({ id: 'feat-1', label: 'F1', confidence: 'high' }, false, {});
    expect(card.querySelector('.integration-badge')).toBeNull();
    state.integration = null;
  });
});
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `npx vitest run tests/ui-list.test.js`
Expected: FAIL（卡片無 `.integration-badge`）。

- [ ] **Step 3: ui-list.js 追加徽章**

`viewer/js/ui-list.js` 頂部 import 加：
```javascript
import { featureVerdict, integrationBadge } from './ui-integration.js';
```
在 `featureCard(...)` 內，於 `card.append(labelEl, descEl, metaEl);` **之前**，把整合徽章塞進 `metaEl`：
```javascript
  const integBadge = integrationBadge(featureVerdict(state.integration, feature.id));
  if (integBadge) metaEl.appendChild(integBadge);
```
在 `changeListButton(...)` 內，同樣於其 `card.append(labelEl, descEl, metaEl);` 之前：
```javascript
  const integBadge = integrationBadge(featureVerdict(state.integration, item.id));
  if (integBadge) metaEl.appendChild(integBadge);
```

- [ ] **Step 4: 跑測試確認通過 + ui-list 回歸**

Run: `npx vitest run tests/ui-list.test.js`
Expected: PASS（新 2 + 既有全綠）。

- [ ] **Step 5: Commit**
```bash
git add viewer/js/ui-list.js viewer/tests/ui-list.test.js
git commit -m "feat(viewer): integration badge on feature cards (from state.integration)" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: 整合健檢面板（渲染 rollup + gap 清單）

**Files:**
- Modify: `viewer/js/ui-integration.js`（加 `renderIntegrationPanel`）
- Modify: `viewer/tests/ui-integration.test.js`

- [ ] **Step 1: 寫失敗測試（面板渲染 + 連動 callback）**

在 `viewer/tests/ui-integration.test.js` 末端追加：
```javascript
import { renderIntegrationPanel } from '../js/ui-integration.js';

describe('renderIntegrationPanel', () => {
  const integ = {
    rollup: { backed: 2, gap: 1, undetermined: 1, conceptual: 0, not_assessed: 0 },
    relations: [
      { from_feature: 'feat-user', to_feature: 'feat-db', verdict: 'gap' },
      { from_feature: 'feat-cache', to_feature: 'feat-redis', verdict: 'undetermined' },
      { from_feature: 'feat-order', to_feature: 'feat-db', verdict: 'backed' },
    ],
  };
  it('shows rollup summary and one row per gap/undetermined', () => {
    const root = document.createElement('div');
    renderIntegrationPanel(root, integ, {});
    expect(root.textContent).toContain('1');           // gap 數
    expect(root.querySelectorAll('.integration-row').length).toBe(2);  // gap + undetermined（backed 不列）
  });
  it('clicking a gap row calls onSelectFeature with from_feature', () => {
    const root = document.createElement('div');
    const picked = [];
    renderIntegrationPanel(root, integ, { onSelectFeature: id => picked.push(id) });
    root.querySelector('.integration-row').click();
    expect(picked).toContain('feat-user');
  });
  it('shows 未評估 empty state when structure missing', () => {
    const root = document.createElement('div');
    renderIntegrationPanel(root, { structure_missing: true, rollup: {}, relations: [] }, {});
    expect(root.textContent).toContain('未評估');
  });
});
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `npx vitest run tests/ui-integration.test.js`
Expected: FAIL（`renderIntegrationPanel` 未匯出）。

- [ ] **Step 3: 加 renderIntegrationPanel**

在 `viewer/js/ui-integration.js` 末端加：
```javascript
const VERDICT_LABEL = {
  gap: '❌ 沒接上', undetermined: '⚠ 無法判定',
};

// 把整合健檢渲染進 container。callbacks.onSelectFeature(featureId) 用於連動選取。
export function renderIntegrationPanel(container, integration, callbacks = {}) {
  container.textContent = '';
  if (!integration || integration.structure_missing) {
    const empty = document.createElement('div');
    empty.className = 'empty-state';
    empty.textContent = '未評估（尚未標記 static 依賴或缺結構檔）。';
    container.appendChild(empty);
    return;
  }
  const r = integration.rollup || {};
  const header = document.createElement('div');
  header.className = 'integration-summary';
  const claimed = (r.backed || 0) + (r.gap || 0) + (r.undetermined || 0);
  header.textContent = `整合健檢：${claimed} 條宣稱、${r.gap || 0} 條沒接上、${r.undetermined || 0} 條無法判定`;
  container.appendChild(header);

  const issues = (integration.relations || []).filter(
    x => x.verdict === 'gap' || x.verdict === 'undetermined');
  if (issues.length === 0) {
    const ok = document.createElement('div');
    ok.className = 'empty-state';
    ok.textContent = '所有宣稱的依賴都接上了。';
    container.appendChild(ok);
    return;
  }
  for (const it of issues) {
    const row = document.createElement('button');
    row.type = 'button';
    row.className = 'integration-row integration-' + it.verdict;
    row.textContent = `${VERDICT_LABEL[it.verdict]}：${it.from_feature} → ${it.to_feature}`;
    row.addEventListener('click', () => callbacks.onSelectFeature?.(it.from_feature));
    container.appendChild(row);
  }
}
```

- [ ] **Step 4: 跑測試確認通過**

Run: `npx vitest run tests/ui-integration.test.js`
Expected: PASS。

- [ ] **Step 5: Commit**
```bash
git add viewer/js/ui-integration.js viewer/tests/ui-integration.test.js
git commit -m "feat(viewer): integration health panel (rollup + gap rows + select callback)" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: 接線——載入 integration、渲染面板、連動選取（app.js）

**Files:**
- Modify: `viewer/js/app.js`（可能含 `viewer/index.html` 加一個面板容器）

- [ ] **Step 1: 查證載入點與選取/容器**

先讀 `viewer/js/app.js`：找到 (a) 呼叫 `fetchL1Graph(...)` 並把結果寫進 state 的載入函式；(b) 既有「選取某 feature」的處理（如設 `state.selectedFeatureId` / `state.selectedId` 並重渲染詳情的函式）；(c) `viewer/index.html` 是否有可放面板的容器（找 `els.*` 對應的 DOM id）。記下三者確切名稱。

- [ ] **Step 2: 載入 integration（與 L1 同步）**

在該載入函式內、取得 L1 後，加（用 Step 1 找到的版本 id 變數）：
```javascript
import { fetchIntegration } from './api.js';
// …在載入流程中：
try {
  state.integration = await fetchIntegration(versionId);
} catch (e) {
  state.integration = null; // 失敗不阻斷主畫面；面板顯示未評估
}
```
（`versionId` 用該函式既有的版本變數；若該函式無版本變數，用與 `fetchL1Graph` 相同的引數來源。）

- [ ] **Step 3: 渲染面板 + 連動**

在 index.html 的整合健檢容器（Step 1 確認的 id；若無則於功能清單區塊旁新增一個 `<section id="integration-panel"></section>` 並在 `dom.js` 的 `els` 註冊），於 L1/integration 載入後呼叫：
```javascript
import { renderIntegrationPanel } from './ui-integration.js';
renderIntegrationPanel(els.integrationPanel, state.integration, {
  onSelectFeature: (featureId) => selectFeatureById(featureId),  // 用 Step 1 找到的既有選取函式
});
```
`selectFeatureById` ＝ Step 1 找到的既有「依 id 選取 feature 並渲染詳情/捲動」流程；若既有選取以 feature 物件為參數，於此用 `state.l1GraphViewModel` 找出該 id 的物件再傳入。

- [ ] **Step 4: 驗證（自動化 + 手動驗收）**

Run（viewer 全套，確認沒打壞）: `npx vitest run`
Expected: PASS（全綠）。

手動驗收（非自動化，但必做一次）：重啟 `the-door ui "C:\Users\Ric\Desktop\test-targets\the-door-v170" --no-browser --port 8765`，開 http://localhost:8765，確認：功能卡出現徽章、面板列出 gap、點面板列會選中對應卡。（v170 的 snapshot 多無 typed relations → 面板可能顯示「未評估」；可另用一個帶 static relation 的 target 驗，或先 snapshot_patch 一條 static relation。若僅「未評估」也算正確空狀態。）

- [ ] **Step 5: Commit**
```bash
git add viewer/js/app.js viewer/js/dom.js viewer/index.html
git commit -m "feat(viewer): wire integration load + panel render + gap→card linking" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review
**1. Spec(§3.3-§3.4/§5/§6) coverage：** 單一 slice `state.integration` → Task 1；徽章讀 slice → Task 2；面板 rollup+gap → Task 3；連動 onSelectFeature → Task 3(callback)+Task 4(接既有選取)；空狀態未評估 → Task 3 測試；載入與 L1 同步 → Task 4。
**2. Placeholder scan：** 純函式/面板/徽章/卡片皆完整程式碼。Task 4 是**接線到既有未知（app.js 載入函式名、既有選取函式、index.html 容器）**，以「先讀 app.js 找三者、再用確切名稱接」處理——這是對既有程式的查證指引，附了要找什麼與備援（無容器則新增 section+els），非佔位。
**3. Type 一致性：** `featureVerdict(integration, id)->'gap'|'undetermined'|'backed'|null`；`integrationBadge(verdict)->span|null`；`renderIntegrationPanel(container, integration, {onSelectFeature})`；卡片 join key ＝ `feature.id`/`item.id`（= L1 view model 的 `id`＝feature_id，已查證 `graph_view_model.py:110`）；整合 payload 形狀與後端 plan 的 `run_integration_check` 回傳一致（features{id:verdict}/relations[]/rollup{}）。

> **誠實邊界**：Task 4 動 `app.js`（本 plan 未逐字讀其載入/選取流程），故以「先讀、用既有名稱接、附備援」涵蓋；Task 1-3 全為純函式/可獨立測之單元、零 app.js 依賴，風險集中且小。手動驗收一步明列為必做（自動化測 jsdom 無法覆蓋真實伺服器串接）。
