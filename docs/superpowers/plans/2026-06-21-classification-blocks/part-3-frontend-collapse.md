# 功能分類層 — Part 3：前端兩層折疊

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** viewer 在 current/baseline 模式、當有區塊資料時，把功能總覽改成「依區塊兩層折疊」呈現（收合顯示加總、卡片含描述/信心/整合徽章、本版新增徽章），無區塊時 fallback 回現有平鋪。

**Architecture:** 新建 `ui-blocks.js` 渲染折疊視圖，重用 `ui-list.js` 既有的 `featureCard`（保留選取連動與整合徽章一致）；資料走新 `state.blocks`（`GET /api/blocks`）。前端無單元測試框架，驗證走 `the-door ui` 真實 app（verify 精神）。

**Tech Stack:** 原生 ES modules、CSS（viewer 既有變數）

**Spec:** `docs/superpowers/specs/2026-06-21-feature-classification-blocks-design.md`（§8）

**前置：** Part 1、Part 2 完成（`/api/blocks` 可回資料）。

**⚠ 唯一正式前端 =** `docs/frontend-local-version-viewer/viewer/`（勿動 `prototype/`）。改完重啟伺服器即生效，無 build step。

---

## Task 1：state + fetchBlocks + load wire

**Files:**
- Modify: `docs/frontend-local-version-viewer/viewer/js/state.js:25`
- Modify: `docs/frontend-local-version-viewer/viewer/js/api.js`（末尾）
- Modify: `docs/frontend-local-version-viewer/viewer/js/app.js:21`（import）、`168-182`（loadFromApi）

- [ ] **Step 1：state 加 blocks**

`state.js` 在 `integration: null,`（25）後加：

```javascript
  integration: null,
  blocks: null,
```

- [ ] **Step 2：api.js 加 fetchBlocks**

`api.js` 末尾加（照 `fetchIntegration` 模式）：

```javascript
export async function fetchBlocks(versionId = null) {
  const url = versionId
    ? `${API_BASE}/api/blocks?version_id=${encodeURIComponent(versionId)}`
    : `${API_BASE}/api/blocks`;
  const res = await fetch(url, { cache: "no-store" });
  return res.json();
}
```

- [ ] **Step 3：app.js import + load**

`app.js:21` 的 import 加 `fetchBlocks`：

```javascript
import { fetchGroup, setProject, fetchIntegration, fetchBlocks } from "./api.js";
```

`loadFromApi`（168-182），在 `fetchIntegration` 的 try/catch 之後、`render();`（181）之前插入：

```javascript
    try {
      state.blocks = await fetchBlocks(versionId);
    } catch (e) {
      state.blocks = null; // 失敗不阻斷；render 會 fallback 平鋪
    }
```

- [ ] **Step 4：手動煙測**

重啟伺服器：`the-door ui "C:\Users\Ric\Desktop\test-targets\the-door-v170" --no-browser --port 8765`
開 `http://localhost:8765`，開瀏覽器 console 確認 `/api/blocks` 有被請求、無 JS 錯誤（v170 此時尚無區塊資料，回 `{"blocks":[]}`，畫面維持平鋪——這就是 fallback 正常）。

- [ ] **Step 5：Commit**

```bash
git add docs/frontend-local-version-viewer/viewer/js/state.js docs/frontend-local-version-viewer/viewer/js/api.js docs/frontend-local-version-viewer/viewer/js/app.js
git commit -m "feat(viewer): fetch /api/blocks into state.blocks"
```

---

## Task 2：ui-blocks.js + render dispatch

**Files:**
- Create: `docs/frontend-local-version-viewer/viewer/js/ui-blocks.js`
- Modify: `docs/frontend-local-version-viewer/viewer/js/app.js:6`（import）、`25-42`（render dispatch）

- [ ] **Step 1：建 ui-blocks.js**

建 `docs/frontend-local-version-viewer/viewer/js/ui-blocks.js`：

```javascript
import { state } from './state.js';
import { els } from './dom.js';
import { featureCard } from './ui-list.js';
import { featureVerdict } from './ui-integration.js';

// 算一組功能的 high/medium/整合(backed) 數，給收合統計用。
function computeStats(features) {
  let high = 0, med = 0, backed = 0;
  for (const f of features) {
    if (f.confidence === 'high') high++;
    else if (f.confidence === 'medium') med++;
    if (featureVerdict(state.integration, f.id) === 'backed') backed++;
  }
  return { high, med, backed };
}

function statsEl(features) {
  const wrap = document.createElement('span');
  wrap.className = 'block-stats';
  const { high, med, backed } = computeStats(features);
  if (high) {
    const s = document.createElement('span');
    s.className = 'confidence-badge confidence-badge-high';
    s.textContent = 'high ' + high;
    wrap.appendChild(s);
  }
  if (med) {
    const s = document.createElement('span');
    s.className = 'confidence-badge confidence-badge-medium';
    s.textContent = 'medium ' + med;
    wrap.appendChild(s);
  }
  if (backed) {
    const s = document.createElement('span');
    s.className = 'block-stat-integ';
    s.textContent = '✓ ' + backed;
    wrap.appendChild(s);
  }
  return wrap;
}

function cardsGrid(features, callbacks) {
  const grid = document.createElement('div');
  grid.className = 'block-cards';
  for (const f of features) {
    grid.appendChild(featureCard(f, f.id === state.selectedId, callbacks));
  }
  return grid;
}

// 把區塊的 related_features（id）映射回 state 裡完整的 feature 物件；
// 被篩選掉（不在 visible map）的成員自動略過。
function resolveFeatures(block, featById) {
  return (block.features || [])
    .map(f => featById.get(f.feature_id))
    .filter(Boolean);
}

function renderTopBlock(top, children, featById, callbacks) {
  const own = resolveFeatures(top, featById);
  const childSections = [];
  const childFeatures = [];
  for (const c of children) {
    const cf = resolveFeatures(c, featById);
    if (!cf.length) continue;
    childFeatures.push(...cf);
    const subH = document.createElement('div');
    subH.className = 'block-sub-header';
    subH.textContent = c.label;
    childSections.push(subH, cardsGrid(cf, callbacks));
  }
  const allVisible = [...own, ...childFeatures];
  if (!allVisible.length) return null; // 全被篩掉 → 不顯示此區塊

  const header = document.createElement('div');
  header.className = 'block-header';
  const chev = document.createElement('span');
  chev.className = 'block-chev';
  chev.textContent = '▾';
  const name = document.createElement('span');
  name.className = 'block-name';
  name.textContent = top.label;
  const count = document.createElement('span');
  count.className = 'block-count';
  count.textContent = allVisible.length;
  header.append(chev, name, count);
  if (top.is_new_this_version) {
    const nb = document.createElement('span');
    nb.className = 'block-new';
    nb.textContent = '本版新增';
    header.appendChild(nb);
  }
  header.appendChild(statsEl(allVisible));

  const body = document.createElement('div');
  body.className = 'block-body';
  if (own.length) body.appendChild(cardsGrid(own, callbacks));
  childSections.forEach(el => body.appendChild(el));

  header.addEventListener('click', () => {
    header.classList.toggle('collapsed');
    body.classList.toggle('hidden');
  });

  const wrap = document.createElement('div');
  wrap.className = 'block-group';
  wrap.append(header, body);
  return wrap;
}

export function renderBlockList(callbacks) {
  const list = els.featureList;
  list.textContent = '';
  els.listTitle.textContent = state.mode === 'baseline' ? '舊版功能' : '新版功能';
  els.listSource.textContent = '依區塊分類';

  const blocks = state.blocks?.blocks ?? [];
  const visibleFeatures = state._filteredFeatures ?? state.l1Model?.features ?? [];
  const featById = new Map(visibleFeatures.map(f => [f.id, f]));

  const tops = blocks.filter(b => !b.parent_block_id);
  const childrenOf = pid => blocks.filter(b => b.parent_block_id === pid);

  let rendered = 0;
  for (const top of tops) {
    const el = renderTopBlock(top, childrenOf(top.block_id), featById, callbacks);
    if (el) { list.appendChild(el); rendered++; }
  }
  if (!rendered) {
    const d = document.createElement('div');
    d.className = 'empty-state';
    d.textContent = '無符合篩選的功能。';
    list.appendChild(d);
  }
}
```

- [ ] **Step 2：app.js render dispatch**

`app.js:6` import 加 `renderBlockList`：

```javascript
import { renderChangeList, applyCardFilters } from "./ui-list.js";
import { renderBlockList } from "./ui-blocks.js";
```

`render()`（25-42）中，把無條件的 `renderChangeList({...})`（31-34）改為 dispatch：

```javascript
  const useBlocks = state.mode !== "diff"
    && (state.blocks?.blocks?.length ?? 0) > 0;
  if (useBlocks) {
    renderBlockList({ onSelectFeature, onSelectChange });
  } else {
    renderChangeList({ onSelectFeature, onSelectChange });
  }
```

- [ ] **Step 3：Commit**

```bash
git add docs/frontend-local-version-viewer/viewer/js/ui-blocks.js docs/frontend-local-version-viewer/viewer/js/app.js
git commit -m "feat(viewer): two-level block-collapse view (fallback to flat list)"
```

---

## Task 3：styles.css 區塊折疊樣式

**Files:**
- Modify: `docs/frontend-local-version-viewer/viewer/styles.css`（末尾追加）

- [ ] **Step 1：追加樣式**

`styles.css` 末尾加（用既有 CSS 變數，不引新色）：

```css
/* ── Block-collapse view (L1.5 classification) ── */
.block-group { margin-bottom: 10px; }
.block-header {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  padding: 9px 12px;
  border: 1px solid var(--line);
  border-radius: 6px;
  background: var(--surface);
  user-select: none;
}
.block-header:hover { border-color: var(--accent); }
.block-chev { font-size: 14px; color: var(--muted); transition: transform 0.15s; }
.block-header.collapsed .block-chev { transform: rotate(-90deg); }
.block-name { font-size: 14px; font-weight: 500; color: var(--text); }
.block-count {
  font-size: 12px; color: var(--muted);
  background: var(--surface-muted); border-radius: 999px; padding: 1px 9px;
}
.block-new {
  font-size: 11px; padding: 1px 9px; border-radius: 999px;
  background: var(--accent-soft); color: var(--accent); margin-left: 4px;
}
.block-stats { display: none; align-items: center; gap: 6px; margin-left: auto; }
.block-header.collapsed .block-stats { display: inline-flex; }
.block-stat-integ { font-size: 11px; color: var(--accent); }
.block-body { margin: 10px 0 8px 6px; }
.block-body.hidden { display: none; }
.block-sub-header {
  font-size: 13px; color: var(--muted); margin: 8px 0 8px 4px;
}
.block-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
  gap: 10px;
  margin-bottom: 12px;
}
```

註：`.feature-card` 既有樣式（label/desc/meta/信心徽章/整合徽章）由 `featureCard()` 沿用，
不需在此重定義；`.block-cards` 只負責格線排列。

- [ ] **Step 2：Commit**

```bash
git add docs/frontend-local-version-viewer/viewer/styles.css
git commit -m "style(viewer): block-collapse view styles"
```

---

## Task 4：端到端手動驗證（real app）

前端無單元測試框架；依 verify 精神驅動真實 app 觀察。需 Part 1-2 已實作。

- [ ] **Step 1：重啟讓 MCP server 載入新後端**

殺掉執行中的 the-door 程序（exe 鎖檔），重啟 Claude Code app（MCP server 是長駐程序、
需重啟才載入 Part 1-2 的新 code）。

- [ ] **Step 2：寫一組測試區塊進 v170 最新快照**

用 MCP `snapshot_patch` 寫入（對應 v170 的 21 個功能、含一個兩層示範與一個本版新增）：

```
snapshot_patch(
  codebase_path="C:/Users/Ric/Desktop/test-targets/the-door-v170",
  version_ref="v1.7.0",
  blocks={
    "blk-core": {"label": "核心分析引擎群組", "responsibility": "抽取與分析程式結構",
      "related_features": ["feat-code-extraction", "feat-pipeline-orchestration", "feat-execution-gate"]},
    "blk-evolution": {"label": "版本與演化群組", "responsibility": "版本差異與時間軸",
      "related_features": ["feat-versioning-diff", "feat-feature-evolution"]},
    "blk-quality": {"label": "品質與安全功能群組", "responsibility": "把關品質與依賴安全",
      "related_features": []},
    "blk-validation": {"label": "輸出與範圍驗證子群組", "responsibility": "驗證輸出與範圍",
      "parent_block_id": "blk-quality",
      "related_features": ["feat-output-validation", "feat-scope-doubt"]},
    "blk-security": {"label": "依賴與資料安全子群組", "responsibility": "漏洞與資料模型",
      "parent_block_id": "blk-quality",
      "related_features": ["feat-vulnerability-scan", "feat-datamodel-localization"]},
    "blk-semantic": {"label": "語意翻譯與敘事群組", "responsibility": "膜模型與敘事",
      "related_features": ["feat-membrane-model", "feat-llm-translation", "feat-narrative-reading", "feat-guidance-flow"]},
    "blk-interface": {"label": "對外介面功能群組", "responsibility": "CLI/MCP/HTTP/註冊",
      "related_features": ["feat-ui-http-api", "feat-cli", "feat-mcp-server", "feat-project-registry"]},
    "blk-frontend": {"label": "前端工作台群組", "responsibility": "viewer 與引導",
      "is_new_this_version": True,
      "related_features": ["feat-viewer-workbench", "feat-onboarding-wizard", "feat-diagram-rendering"]},
    "blk-models": {"label": "共用資料模型群組", "responsibility": "跨子系統資料契約",
      "related_features": ["feat-domain-models"]}
  }
)
```

期望：回傳 `blocks_written` 含 9 個 id、無 `BlockValidationError`（21 功能全歸屬、單一歸屬、
品質與安全為兩層父、深度未超兩層）。

- [ ] **Step 3：啟動 viewer 驗證**

```
the-door ui "C:\Users\Ric\Desktop\test-targets\the-door-v170" --no-browser --port 8765
```

開 `http://localhost:8765`，確認：
- 功能總覽改為依區塊折疊（9 個頂層、品質與安全展開兩層子區塊）。
- 點標題列可折疊；收合時右側顯示 `high N` / `medium N` / `✓ N` 加總。
- 卡片含 label + description + 信心 pill + 整合 ✓ 徽章（與既有一致）。
- 「前端工作台」有「本版新增」徽章。
- 信心篩選器仍有效（縮減區塊內成員，空區塊隱藏）。
- 切到「差異」模式：回變更清單（區塊視圖只在 baseline/current）。

- [ ] **Step 4：驗證 fallback**

把版本選擇器切到一個沒有區塊資料的舊快照（如 v1.6.5），確認功能總覽 fallback 回平鋪清單、
無 JS 錯誤。

---

## Part 3 Self-Review

- [x] **Spec coverage**：§8 全部——兩層折疊(T2)、收合統計(T2/T3)、卡片含描述+信心+整合徽章
  （重用 featureCard，T2）、本版新增徽章(T2/T3)、fallback(T2 dispatch)、整合徽章走既有
  `state.integration`（statsEl/featureCard 用 `featureVerdict(state.integration,…)`，T2）。
- [x] **Placeholder scan**：無 TBD/TODO；ui-blocks.js 完整、樣式完整、驗證步驟具體。
- [x] **Type consistency**：`renderBlockList(callbacks)`、`state.blocks.blocks[]`、區塊欄位
  （block_id/label/parent_block_id/is_new_this_version/features[].feature_id）與 Part 2
  endpoint payload 完全對應；`featureCard(feature,isActive,callbacks)` 簽名與 ui-list.js 一致。
