# Flow View 分層有向布局 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 viewer 圖形視圖從無向平鋪網格替換為拓撲分層有向布局（左＝入口、右＝底層），邊帶箭頭與 integration 狀態色。

**Architecture:** 新增純函式布局模組 `flow-layout.js`（DFS back-edge + longest-path 分欄 + 孤島分離），`graph.js` 的 `renderGridGraph` 換成 `renderFlowGraph`（卡片渲染碼原樣沿用、邊繪製加箭頭/色）。integration 資料生命週期收進 `loadL1Graph`（附掛 `viewModel.integration`）。零後端/API/契約/gate 改動。

**Tech Stack:** Vanilla JS ES modules、SVG（邊）、CSS flex（band/子欄）、vitest + jsdom。

**Spec:** `docs/superpowers/specs/2026-07-05-flow-view-layered-layout-design.md`（決策 D1–D6 全定案，本 plan 不重議）。

## Global Constraints

- 只動 `docs/frontend-local-version-viewer/viewer/`（⛔ 絕不碰 `prototype/`）。
- 改動範圍限：`js/flow-layout.js`（新）、`js/graph.js`、`js/layers.js`、`js/app.js`、`styles.css`、`tests/flow-layout.test.js`（新）、`tests/graph.test.js`、`tests/layers.test.js`。
- `initGraph(containerId, viewModel, onNodeClick)` 介面不變。
- 測試指令一律在 `docs/frontend-local-version-viewer/viewer/` 目錄下跑 `npx vitest run <file>`（本 repo C4 hook 擋 `python -c`/`python x.py`；C5 擋 Bash 的 grep/cat/find——實作中查檔用 Read/Grep 工具）。
- **就地開 feature 分支**（`git checkout -b feature/flow-view-layered-layout`），⛔ 不開獨立 worktree（editable install 指向主 repo，worktree 內測試取不到改動）。commit 前先 `git rev-parse --abbrev-ref HEAD` 驗證不在 main。
- 決定性鐵則：同一 viewModel 輸入，布局輸出必須一致（排序皆字典序）。
- 誠實鐵則：integration 無資料＝灰邊，不得推測著色。

---

### Task 1: `flow-layout.js` 純函式布局模組（TDD）

**Files:**
- Create: `docs/frontend-local-version-viewer/viewer/js/flow-layout.js`
- Test: `docs/frontend-local-version-viewer/viewer/tests/flow-layout.test.js`

**Interfaces:**
- Consumes: 無（零依賴、零 DOM）。
- Produces（後續 Task 依賴的精確簽章）:
  - `edgeKey(source, target) → string`（`'\u0000'` 分隔）
  - `detectBackEdges(nodeIds: string[], edges: {source,target}[]) → Set<string>`（edgeKey 集合）
  - `splitIsolated(nodeIds, edges) → { linked: string[], isolated: string[] }`
  - `assignColumns(nodeIds, edges, backEdges: Set) → Map<string, number>`（**顯示欄**，已反轉：0＝最左＝entry）
  - `computeFlowLayout(viewModel) → { bands: string[][][], isolated: string[], backEdges: Set<string> }`（`bands[欄][子欄] = node_id[]`）
  - `MAX_PER_SUBCOL = 8`

- [ ] **Step 1: 寫失敗測試**

```js
// tests/flow-layout.test.js
import { describe, it, expect } from 'vitest';
import {
  edgeKey, detectBackEdges, splitIsolated, assignColumns,
  computeFlowLayout, MAX_PER_SUBCOL,
} from '../js/flow-layout.js';

const E = (s, t) => ({ source: s, target: t });

describe('detectBackEdges', () => {
  it('無環圖回空集合', () => {
    expect(detectBackEdges(['a', 'b', 'c'], [E('a', 'b'), E('b', 'c')]).size).toBe(0);
  });
  it('二節點環標出一條 back-edge', () => {
    const be = detectBackEdges(['a', 'b'], [E('a', 'b'), E('b', 'a')]);
    expect(be.size).toBe(1);
    expect(be.has(edgeKey('b', 'a'))).toBe(true); // 決定性：DFS 從字典序 'a' 起，b→a 是回邊
  });
  it('self-loop 忽略不計', () => {
    expect(detectBackEdges(['a'], [E('a', 'a')]).size).toBe(0);
  });
});

describe('splitIsolated', () => {
  it('無任何邊的節點進 isolated', () => {
    const r = splitIsolated(['a', 'b', 'x'], [E('a', 'b')]);
    expect(r.linked).toEqual(['a', 'b']);
    expect(r.isolated).toEqual(['x']);
  });
  it('只有 self-loop 的節點視為孤島', () => {
    const r = splitIsolated(['a', 'b', 's'], [E('a', 'b'), E('s', 's')]);
    expect(r.isolated).toEqual(['s']);
  });
});

describe('assignColumns（顯示欄：0＝最左＝entry）', () => {
  it('鏈 a→b→c：a 欄 0、b 欄 1、c 欄 2（被依賴最深在最右）', () => {
    const col = assignColumns(['a', 'b', 'c'], [E('a', 'b'), E('b', 'c')], new Set());
    expect(col.get('a')).toBe(0);
    expect(col.get('b')).toBe(1);
    expect(col.get('c')).toBe(2);
  });
  it('菱形 a→b, a→c, b→d, c→d：d 最右、a 最左', () => {
    const col = assignColumns(['a', 'b', 'c', 'd'],
      [E('a', 'b'), E('a', 'c'), E('b', 'd'), E('c', 'd')], new Set());
    expect(col.get('a')).toBe(0);
    expect(col.get('b')).toBe(1);
    expect(col.get('c')).toBe(1);
    expect(col.get('d')).toBe(2);
  });
  it('back-edge 不參與 depth 計算', () => {
    const be = new Set([edgeKey('b', 'a')]);
    const col = assignColumns(['a', 'b'], [E('a', 'b'), E('b', 'a')], be);
    expect(col.get('a')).toBe(0);
    expect(col.get('b')).toBe(1);
  });
});

describe('computeFlowLayout', () => {
  const vm = (nodes, edges) => ({ nodes: nodes.map(id => ({ id, label: id })), edges });

  it('integration-demo 形狀：order → auth/report/user → db 三欄', () => {
    const r = computeFlowLayout(vm(
      ['feat-order', 'feat-auth', 'feat-report', 'feat-user', 'feat-db'],
      [E('feat-order', 'feat-auth'), E('feat-order', 'feat-report'), E('feat-order', 'feat-user'),
       E('feat-auth', 'feat-db'), E('feat-report', 'feat-db'), E('feat-user', 'feat-db')]));
    expect(r.bands).toHaveLength(3);
    expect(r.bands[0][0]).toEqual(['feat-order']);
    expect(r.bands[1][0]).toEqual(['feat-auth', 'feat-report', 'feat-user']); // 欄內字典序
    expect(r.bands[2][0]).toEqual(['feat-db']);
    expect(r.isolated).toEqual([]);
  });

  it('超過 MAX_PER_SUBCOL 折子欄', () => {
    const ids = Array.from({ length: MAX_PER_SUBCOL + 2 }, (_, i) => `leaf-${String(i).padStart(2, '0')}`);
    const edges = ids.map(id => E('root', id));
    const r = computeFlowLayout(vm(['root', ...ids], edges));
    expect(r.bands[1]).toHaveLength(2);                      // 10 卡 → 2 子欄
    expect(r.bands[1][0]).toHaveLength(MAX_PER_SUBCOL);
    expect(r.bands[1][1]).toHaveLength(2);
  });

  it('全孤島：bands 空、全進 isolated', () => {
    const r = computeFlowLayout(vm(['a', 'b'], []));
    expect(r.bands).toEqual([]);
    expect(r.isolated).toEqual(['a', 'b']);
  });

  it('決定性：同輸入兩次呼叫深相等', () => {
    const input = vm(['c', 'a', 'b'], [E('a', 'b'), E('b', 'c'), E('c', 'a')]);
    const r1 = computeFlowLayout(input);
    const r2 = computeFlowLayout(input);
    expect(r1.bands).toEqual(r2.bands);
    expect([...r1.backEdges].sort()).toEqual([...r2.backEdges].sort());
  });
});
```

- [ ] **Step 2: 跑測試確認失敗**

Run（cwd＝`docs/frontend-local-version-viewer/viewer/`）: `npx vitest run tests/flow-layout.test.js`
Expected: FAIL — `Cannot find module '../js/flow-layout.js'`

- [ ] **Step 3: 實作**

```js
// js/flow-layout.js
// 拓撲分層布局 — 純函式、零 DOM。演算法定案見 spec D1–D3
// （docs/superpowers/specs/2026-07-05-flow-view-layered-layout-design.md）。

export const MAX_PER_SUBCOL = 8;

export function edgeKey(source, target) {
  return source + '\u0000' + target;
}

// 決定性 DFS back-edge 偵測：根節點與鄰接串列皆字典序；self-loop 忽略。
export function detectBackEdges(nodeIds, edges) {
  const adj = new Map(nodeIds.map(id => [id, []]));
  for (const e of edges) {
    if (!adj.has(e.source) || !adj.has(e.target) || e.source === e.target) continue;
    adj.get(e.source).push(e.target);
  }
  for (const list of adj.values()) list.sort();
  const color = new Map(nodeIds.map(id => [id, 0])); // 0=white 1=gray 2=black
  const back = new Set();
  const visit = (u) => {
    color.set(u, 1);
    for (const v of adj.get(u)) {
      if (color.get(v) === 0) visit(v);
      else if (color.get(v) === 1) back.add(edgeKey(u, v));
    }
    color.set(u, 2);
  };
  for (const id of [...nodeIds].sort()) if (color.get(id) === 0) visit(id);
  return back;
}

// 無任何（非 self-loop）邊的節點分離（spec D3「未宣告關聯」列）。
export function splitIsolated(nodeIds, edges) {
  const idSet = new Set(nodeIds);
  const touched = new Set();
  for (const e of edges) {
    if (e.source === e.target) continue;
    if (idSet.has(e.source) && idSet.has(e.target)) {
      touched.add(e.source);
      touched.add(e.target);
    }
  }
  return {
    linked: nodeIds.filter(id => touched.has(id)),
    isolated: nodeIds.filter(id => !touched.has(id)),
  };
}

// 顯示欄指派：depth(n)=1+max(depth(依賴))（無依賴=0），顯示欄=maxDepth−depth（spec D1 反轉）。
export function assignColumns(nodeIds, edges, backEdges) {
  const dep = new Map(nodeIds.map(id => [id, []]));
  for (const e of edges) {
    if (!dep.has(e.source) || !dep.has(e.target) || e.source === e.target) continue;
    if (backEdges.has(edgeKey(e.source, e.target))) continue;
    dep.get(e.source).push(e.target);
  }
  const depth = new Map();
  const calc = (n) => {
    if (depth.has(n)) return depth.get(n);
    depth.set(n, 0); // 防禦 guard（去 back-edge 後不應再有環）
    let d = 0;
    for (const t of dep.get(n)) d = Math.max(d, calc(t) + 1);
    depth.set(n, d);
    return d;
  };
  for (const id of nodeIds) calc(id);
  const maxDepth = nodeIds.length ? Math.max(...nodeIds.map(id => depth.get(id))) : 0;
  const col = new Map();
  for (const id of nodeIds) col.set(id, maxDepth - depth.get(id));
  return col;
}

// 組裝：bands[顯示欄][子欄]=node_id[]（欄內字典序、每 MAX_PER_SUBCOL 卡折一子欄）。
export function computeFlowLayout(viewModel) {
  const nodeIds = (viewModel.nodes || []).map(n => n.id);
  const edges = viewModel.edges || [];
  const { linked, isolated } = splitIsolated(nodeIds, edges);
  const backEdges = detectBackEdges(linked, edges);
  if (!linked.length) return { bands: [], isolated: [...isolated].sort(), backEdges };
  const col = assignColumns(linked, edges, backEdges);
  const maxCol = Math.max(...linked.map(id => col.get(id)));
  const byCol = Array.from({ length: maxCol + 1 }, () => []);
  for (const id of linked) byCol[col.get(id)].push(id);
  const bands = byCol.map(ids => {
    ids.sort();
    const subs = [];
    for (let i = 0; i < ids.length; i += MAX_PER_SUBCOL) subs.push(ids.slice(i, i + MAX_PER_SUBCOL));
    return subs;
  });
  return { bands, isolated: [...isolated].sort(), backEdges };
}
```

- [ ] **Step 4: 跑測試確認通過**

Run: `npx vitest run tests/flow-layout.test.js`
Expected: PASS（12 tests）

- [ ] **Step 5: Commit**

```bash
git rev-parse --abbrev-ref HEAD   # 必須是 feature/flow-view-layered-layout
git add docs/frontend-local-version-viewer/viewer/js/flow-layout.js docs/frontend-local-version-viewer/viewer/tests/flow-layout.test.js
git commit -m "feat(viewer): add flow-layout pure module (DFS back-edge + layered columns + isolated split)"
```

---

### Task 2: `renderFlowGraph` 取代 `renderGridGraph`（band/子欄 DOM + 孤島列）

**Files:**
- Modify: `docs/frontend-local-version-viewer/viewer/js/graph.js`（`renderGridGraph` 82-119 行整段替換；`initGraph` 142 行改呼叫）
- Test: `docs/frontend-local-version-viewer/viewer/tests/graph.test.js`

**Interfaces:**
- Consumes: Task 1 全部匯出。
- Produces:
  - `renderFlowGraph(container, viewModel, onNodeClick)`（匯出，取代 `renderGridGraph`——舊名**刪除**，production 唯一 caller 是 `initGraph`，測試同步改名）
  - `_buildNodeCard(node, onNodeClick) → HTMLElement`（模組內部函式，自現有 renderGridGraph 89-113 行卡片碼原樣抽出：`gv-node`＋`conf-*`＋change_type class/tag＋title＋meta＋click handler，**一行不改**）
  - DOM 結構（Task 3、CSS 依賴）：
    ```
    .gv-flow-wrapper > .gv-flow(position:relative)
      > .gv-bands > .gv-band(每欄) > .gv-subcol(每子欄) > .gv-node(卡片)
      > .gv-isolated-row（僅孤島非空時）> .gv-isolated-title("未宣告關聯") + .gv-subcol > .gv-node
    ```
  - 邊繪製呼叫（Task 3 接手實作）：`requestAnimationFrame(() => _drawFlowEdges(flow, edges, cardMap, viewModel.integration, layout.backEdges))`

- [ ] **Step 1: 改測試（既有 renderGridGraph 引用改名 + 新斷言）**

`tests/graph.test.js` 修改：import 的 `renderGridGraph` → `renderFlowGraph`；
92-105 行三個 it 的 `.gv-grid-wrapper` → `.gv-flow-wrapper`（`.gv-node` 斷言不動）；
128-142 行兩個 conf 測試把 `renderGridGraph(` → `renderFlowGraph(`。新增：

```js
describe('renderFlowGraph 分層布局', () => {
  it('鏈 a→b 產生兩個 .gv-band，a 在第一欄', () => {
    const container = document.createElement('div');
    renderFlowGraph(container,
      { nodes: [{ id: 'b', label: 'B' }, { id: 'a', label: 'A' }],
        edges: [{ source: 'a', target: 'b' }] }, () => {});
    const bands = container.querySelectorAll('.gv-band');
    expect(bands).toHaveLength(2);
    expect(bands[0].querySelector('.gv-node-title').textContent).toBe('A');
    expect(bands[1].querySelector('.gv-node-title').textContent).toBe('B');
  });

  it('無邊節點進 .gv-isolated-row，標題為 未宣告關聯', () => {
    const container = document.createElement('div');
    renderFlowGraph(container,
      { nodes: [{ id: 'a', label: 'A' }, { id: 'x', label: 'X' }, { id: 'b', label: 'B' }],
        edges: [{ source: 'a', target: 'b' }] }, () => {});
    const iso = container.querySelector('.gv-isolated-row');
    expect(iso).not.toBeNull();
    expect(iso.querySelector('.gv-isolated-title').textContent).toBe('未宣告關聯');
    expect(iso.querySelectorAll('.gv-node')).toHaveLength(1);
  });

  it('無孤島時不渲染 .gv-isolated-row', () => {
    const container = document.createElement('div');
    renderFlowGraph(container,
      { nodes: [{ id: 'a', label: 'A' }, { id: 'b', label: 'B' }],
        edges: [{ source: 'a', target: 'b' }] }, () => {});
    expect(container.querySelector('.gv-isolated-row')).toBeNull();
  });

  it('卡片 click handler 保留（點擊回傳 node）', () => {
    const container = document.createElement('div');
    let clicked = null;
    renderFlowGraph(container,
      { nodes: [{ id: 'a', label: 'A' }], edges: [] }, (n) => { clicked = n; });
    container.querySelector('.gv-node').click();
    expect(clicked.id).toBe('a');
  });
});
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `npx vitest run tests/graph.test.js`
Expected: FAIL — `renderFlowGraph is not exported`

- [ ] **Step 3: 實作**

`graph.js`：把 89-113 行卡片建構碼原樣抽成 `_buildNodeCard(node, onNodeClick)`（回傳 card 元素、含 click listener），然後：

```js
import { computeFlowLayout } from './flow-layout.js';

export function renderFlowGraph(container, viewModel, onNodeClick) {
  container.textContent = '';
  const wrapper = document.createElement('div');
  wrapper.className = 'gv-flow-wrapper';
  const flow = document.createElement('div');
  flow.className = 'gv-flow';
  const nodeById = new Map((viewModel.nodes || []).map(n => [n.id, n]));
  const layout = computeFlowLayout(viewModel);
  const cardMap = {};

  const bandsRow = document.createElement('div');
  bandsRow.className = 'gv-bands';
  layout.bands.forEach(subs => {
    const band = document.createElement('div');
    band.className = 'gv-band';
    subs.forEach(ids => {
      const sub = document.createElement('div');
      sub.className = 'gv-subcol';
      ids.forEach(id => {
        const card = _buildNodeCard(nodeById.get(id), onNodeClick);
        sub.appendChild(card);
        cardMap[id] = card;
      });
      band.appendChild(sub);
    });
    bandsRow.appendChild(band);
  });
  flow.appendChild(bandsRow);

  if (layout.isolated.length) {
    const iso = document.createElement('div');
    iso.className = 'gv-isolated-row';
    const title = document.createElement('div');
    title.className = 'gv-isolated-title';
    title.textContent = '未宣告關聯';
    iso.appendChild(title);
    const sub = document.createElement('div');
    sub.className = 'gv-subcol';
    layout.isolated.forEach(id => {
      const card = _buildNodeCard(nodeById.get(id), onNodeClick);
      sub.appendChild(card);
      cardMap[id] = card;
    });
    iso.appendChild(sub);
    flow.appendChild(iso);
  }

  wrapper.appendChild(flow);
  container.appendChild(wrapper);
  const edges = viewModel.edges || [];
  if (edges.length) {
    requestAnimationFrame(() =>
      _drawFlowEdges(flow, edges, cardMap, viewModel.integration, layout.backEdges));
  }
}
```

本 task 的 `_drawFlowEdges` 先放**空殼**（Task 3 實作）：

```js
function _drawFlowEdges(_flow, _edges, _cardMap, _integration, _backEdges) {
  // Task 3 實作：SVG 箭頭邊 + integration 色 + back-edge 虛線
}
```

`initGraph` 142 行 `renderGridGraph(...)` → `renderFlowGraph(...)`；刪除舊
`renderGridGraph` 與 `_drawGridEdges`（無其他 production caller，已驗證）。

- [ ] **Step 4: 跑測試確認通過**

Run: `npx vitest run tests/graph.test.js`
Expected: PASS（既有改名測試 + 4 新測試）

- [ ] **Step 5: Commit**

```bash
git rev-parse --abbrev-ref HEAD
git add docs/frontend-local-version-viewer/viewer/js/graph.js docs/frontend-local-version-viewer/viewer/tests/graph.test.js
git commit -m "feat(viewer): replace grid graph with layered flow layout (bands/subcols/isolated row)"
```

---

### Task 3: 邊繪製（箭頭 + integration 色 + back-edge 虛線）與 Legend

**Files:**
- Modify: `docs/frontend-local-version-viewer/viewer/js/graph.js`（`_drawFlowEdges` 實作、`renderLegend` 增項、新增兩個匯出純函式）
- Test: `docs/frontend-local-version-viewer/viewer/tests/graph.test.js`

**Interfaces:**
- Consumes: Task 1 `edgeKey`；Task 2 的 `_drawFlowEdges` 呼叫約定與 DOM 結構。
- Produces:
  - `buildIntegrationIndex(integration) → Map<edgeKey, verdict>`（匯出純函式；`integration` 可為 null/undefined → 空 Map）
  - `edgeStyle(edge, integrationIndex, backEdges) → { color: string, dashed: boolean }`（匯出純函式；gap=`#dc2626`、backed=`#16a34a`、其餘=`#94a3b8`）

- [ ] **Step 1: 寫失敗測試（純函式部分——jsdom rect 全 0，SVG 繪製走既有 early-return 慣例不強測）**

```js
// graph.test.js 追加
import { buildIntegrationIndex, edgeStyle } from '../js/graph.js';
import { edgeKey } from '../js/flow-layout.js';

describe('buildIntegrationIndex / edgeStyle', () => {
  const integration = { relations: [
    { from_feature: 'feat-a', to_feature: 'feat-db', verdict: 'gap' },
    { from_feature: 'feat-a', to_feature: 'feat-b',  verdict: 'backed' },
    { from_feature: 'feat-a', to_feature: 'feat-c',  verdict: 'not_assessed' },
  ] };

  it('gap 邊為紅', () => {
    const idx = buildIntegrationIndex(integration);
    expect(edgeStyle({ source: 'feat-a', target: 'feat-db' }, idx, new Set()).color).toBe('#dc2626');
  });
  it('backed 邊為綠', () => {
    const idx = buildIntegrationIndex(integration);
    expect(edgeStyle({ source: 'feat-a', target: 'feat-b' }, idx, new Set()).color).toBe('#16a34a');
  });
  it('not_assessed 與查無資料皆為灰（不洗成綠）', () => {
    const idx = buildIntegrationIndex(integration);
    expect(edgeStyle({ source: 'feat-a', target: 'feat-c' }, idx, new Set()).color).toBe('#94a3b8');
    expect(edgeStyle({ source: 'zz', target: 'yy' }, idx, new Set()).color).toBe('#94a3b8');
  });
  it('integration 為 null → 空 index → 全灰', () => {
    const idx = buildIntegrationIndex(null);
    expect(idx.size).toBe(0);
    expect(edgeStyle({ source: 'feat-a', target: 'feat-db' }, idx, new Set()).color).toBe('#94a3b8');
  });
  it('back-edge 標 dashed', () => {
    const be = new Set([edgeKey('b', 'a')]);
    expect(edgeStyle({ source: 'b', target: 'a' }, buildIntegrationIndex(null), be).dashed).toBe(true);
    expect(edgeStyle({ source: 'a', target: 'b' }, buildIntegrationIndex(null), be).dashed).toBe(false);
  });
});

describe('renderLegend（flow 版）', () => {
  it('包含方向/整合/循環三個新圖例項（共 7 項）', () => {
    renderLegend();
    expect(document.querySelectorAll('#legend-panel .legend-item')).toHaveLength(7);
    expect(document.getElementById('legend-panel').textContent).toContain('左＝入口');
    expect(document.getElementById('legend-panel').textContent).toContain('沒接上');
    expect(document.getElementById('legend-panel').textContent).toContain('循環');
  });
});
```

同時把既有 renderLegend 測試（graph.test.js 67-70 行「inserts 4 .legend-item」）的
`4` 改 `7`（或整個 it 併入上面新 describe——擇一，不留兩個互相矛盾的斷言）。

- [ ] **Step 2: 跑測試確認失敗**

Run: `npx vitest run tests/graph.test.js`
Expected: FAIL — `buildIntegrationIndex is not exported`

- [ ] **Step 3: 實作**

```js
// graph.js
import { computeFlowLayout, edgeKey } from './flow-layout.js';

const EDGE_COLOR = { gap: '#dc2626', backed: '#16a34a', default: '#94a3b8' };

export function buildIntegrationIndex(integration) {
  const idx = new Map();
  for (const r of integration?.relations || []) {
    idx.set(edgeKey(r.from_feature, r.to_feature), r.verdict);
  }
  return idx;
}

export function edgeStyle(edge, integrationIndex, backEdges) {
  const k = edgeKey(edge.source, edge.target);
  const verdict = integrationIndex.get(k);
  return {
    color: EDGE_COLOR[verdict] || EDGE_COLOR.default,
    dashed: backEdges.has(k),
  };
}

const SVG_NS = 'http://www.w3.org/2000/svg';

function _makeArrowMarker(id, color) {
  const m = document.createElementNS(SVG_NS, 'marker');
  m.setAttribute('id', id);
  m.setAttribute('viewBox', '0 0 10 10');
  m.setAttribute('refX', '9');
  m.setAttribute('refY', '5');
  m.setAttribute('markerWidth', '7');
  m.setAttribute('markerHeight', '7');
  m.setAttribute('orient', 'auto-start-reverse');
  const p = document.createElementNS(SVG_NS, 'path');
  p.setAttribute('d', 'M 0 0 L 10 5 L 0 10 z');
  p.setAttribute('fill', color);
  m.appendChild(p);
  return m;
}

function _drawFlowEdges(flow, edges, cardMap, integration, backEdges) {
  const flowRect = flow.getBoundingClientRect();
  if (!flowRect.width) return; // jsdom / 未布局：沿用既有 early-return 慣例
  const svg = document.createElementNS(SVG_NS, 'svg');
  svg.classList.add('gv-edges');
  svg.setAttribute('aria-hidden', 'true');
  svg.setAttribute('width', flow.scrollWidth);
  svg.setAttribute('height', flow.scrollHeight);
  const defs = document.createElementNS(SVG_NS, 'defs');
  defs.appendChild(_makeArrowMarker('gv-arrow-gap', EDGE_COLOR.gap));
  defs.appendChild(_makeArrowMarker('gv-arrow-backed', EDGE_COLOR.backed));
  defs.appendChild(_makeArrowMarker('gv-arrow-default', EDGE_COLOR.default));
  svg.appendChild(defs);

  const idx = buildIntegrationIndex(integration);
  edges.forEach(edge => {
    const src = cardMap[edge.source];
    const tgt = cardMap[edge.target];
    if (!src || !tgt) return;
    const { color, dashed } = edgeStyle(edge, idx, backEdges);
    const sr = src.getBoundingClientRect();
    const tr = tgt.getBoundingClientRect();
    // 錨點（spec §4）：一般邊＝源卡右緣中點→目標卡左緣中點；back-edge＝源卡左緣→目標卡右緣
    let x1, y1, x2, y2;
    if (!dashed) {
      x1 = sr.right - flowRect.left;  y1 = sr.top + sr.height / 2 - flowRect.top;
      x2 = tr.left - flowRect.left;   y2 = tr.top + tr.height / 2 - flowRect.top;
    } else {
      x1 = sr.left - flowRect.left;   y1 = sr.top + sr.height / 2 - flowRect.top;
      x2 = tr.right - flowRect.left;  y2 = tr.top + tr.height / 2 - flowRect.top;
    }
    const line = document.createElementNS(SVG_NS, 'line');
    line.setAttribute('x1', x1); line.setAttribute('y1', y1);
    line.setAttribute('x2', x2); line.setAttribute('y2', y2);
    line.setAttribute('stroke', color);
    line.setAttribute('stroke-width', '1.5');
    if (dashed) line.setAttribute('stroke-dasharray', '6 4');
    const markerId = color === EDGE_COLOR.gap ? 'gv-arrow-gap'
      : color === EDGE_COLOR.backed ? 'gv-arrow-backed' : 'gv-arrow-default';
    line.setAttribute('marker-end', `url(#${markerId})`);
    svg.appendChild(line);
  });
  flow.insertBefore(svg, flow.firstChild);
}
```

`renderLegend`（graph.js 13-34 行）items 陣列改為：

```js
  const items = [
    { color: '#4caf50', label: '新增' },
    { color: '#f44336', label: '移除' },
    { color: '#ff9800', label: '修改' },
    { color: '#9e9e9e', label: '未變更' },
    { color: '#94a3b8', label: '→ 左＝入口 · 右＝底層' },
    { color: '#dc2626', label: '紅邊＝宣稱依賴沒接上' },
    { color: '#94a3b8', label: '虛線邊＝循環' },
  ];
```

（swatch 建構迴圈不動——7 項全走同一路徑。）

- [ ] **Step 4: 跑測試確認通過**

Run: `npx vitest run tests/graph.test.js`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git rev-parse --abbrev-ref HEAD
git add docs/frontend-local-version-viewer/viewer/js/graph.js docs/frontend-local-version-viewer/viewer/tests/graph.test.js
git commit -m "feat(viewer): directed edges with arrows, integration verdict colors, back-edge dashes, legend"
```

---

### Task 4: integration 資料生命週期收進 `loadL1Graph`

**Files:**
- Modify: `docs/frontend-local-version-viewer/viewer/js/layers.js:35-82`（loadL1Graph）
- Modify: `docs/frontend-local-version-viewer/viewer/js/app.js:172-191`（移除原 fetchIntegration）
- Test: `docs/frontend-local-version-viewer/viewer/tests/layers.test.js`

**Interfaces:**
- Consumes: `api.js` `fetchIntegration(versionId = null)`（既有，回 `res.json()`）。
- Produces: `loadL1Graph(versionId)` 現在保證——`state.integration` 為**同 versionId** 的
  integration（失敗＝null）、`state.l1GraphViewModel.integration` 同值、兩者都在
  `initGraph` **之前**就緒。app.js 不再自行 fetch integration。

- [ ] **Step 1: 寫失敗測試**

```js
// layers.test.js 追加（沿用檔內既有 global.fetch = vi.fn() mock 模式，見 261/286 行）
import { loadL1Graph } from '../js/layers.js';
import { state } from '../js/state.js';

describe('loadL1Graph attaches integration', () => {
  it('成功時 viewModel.integration 與 state.integration 同值且先於渲染就緒', async () => {
    const integrationPayload = { relations: [
      { from_feature: 'feat-a', to_feature: 'feat-b', verdict: 'gap' }], rollup: { gap: 1 } };
    global.fetch = vi.fn((url) => {
      if (String(url).includes('/api/integration')) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(integrationPayload) });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve(
        { nodes: [{ id: 'feat-a', label: 'A' }, { id: 'feat-b', label: 'B' }],
          edges: [{ source: 'feat-a', target: 'feat-b' }] }) });
    });
    await loadL1Graph('ver-123');
    expect(state.integration).toEqual(integrationPayload);
    expect(state.l1GraphViewModel.integration).toEqual(integrationPayload);
    // versionId 有傳遞給 integration endpoint
    const urls = global.fetch.mock.calls.map(c => String(c[0]));
    expect(urls.some(u => u.includes('/api/integration') && u.includes('ver-123'))).toBe(true);
  });

  it('integration fetch 失敗 → null fail-soft、不阻斷圖渲染', async () => {
    global.fetch = vi.fn((url) => {
      if (String(url).includes('/api/integration')) return Promise.reject(new Error('boom'));
      return Promise.resolve({ ok: true, json: () => Promise.resolve(
        { nodes: [{ id: 'feat-a', label: 'A' }], edges: [] }) });
    });
    await loadL1Graph(null);
    expect(state.integration).toBeNull();
    expect(state.l1GraphViewModel.integration).toBeNull();
    expect(document.querySelectorAll('#graph-container .gv-node')).toHaveLength(1);
  });
});
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `npx vitest run tests/layers.test.js`
Expected: FAIL — `state.l1GraphViewModel.integration` 為 undefined

- [ ] **Step 3: 實作**

`layers.js` `loadL1Graph`：在 `state.l1GraphViewModel = await res.json();`（:46）之後、
`initGraph(...)`（:64）之前插入：

```js
    // integration 生命週期收於此（單一權威）：同 versionId、fail-soft、先於 initGraph 就緒
    // ——修正 spec D5 記載的首繪時序與版本切換過期資料問題。
    try {
      state.integration = await fetchIntegration(versionId);
    } catch (_) {
      state.integration = null; // 失敗不阻斷主畫面；邊全灰、面板顯示未評估
    }
    state.l1GraphViewModel.integration = state.integration;
```

檔頭 import 加：`import { fetchIntegration } from "./api.js";`（併入既有 api.js import 行若有）。

`app.js` `loadFromApi`（:175-179）刪除整個 `try { state.integration = await fetchIntegration(versionId); } catch ...` 區塊（`loadL1Graph(versionId)` 在 :174 已負責）。:185-189 的 `renderIntegrationPanel(els.integrationPanel, state.integration, ...)` **保留不動**（讀的是 loadL1Graph 寫好的同一份 state）。

- [ ] **Step 4: 跑測試確認通過（含全套回歸）**

Run: `npx vitest run`
Expected: 全綠（三檔改動 + 其餘測試不受影響）

- [ ] **Step 5: Commit**

```bash
git rev-parse --abbrev-ref HEAD
git add docs/frontend-local-version-viewer/viewer/js/layers.js docs/frontend-local-version-viewer/viewer/js/app.js docs/frontend-local-version-viewer/viewer/tests/layers.test.js
git commit -m "fix(viewer): move integration fetch into loadL1Graph (fresh per version, ready before render)"
```

---

### Task 5: styles.css 分欄樣式 + 全套回歸 + e2e 手動驗收

**Files:**
- Modify: `docs/frontend-local-version-viewer/viewer/styles.css:1618-1687`（gv-grid 區段替換為 flow 版）

**Interfaces:**
- Consumes: Task 2 的 DOM class 結構（`.gv-flow-wrapper/.gv-flow/.gv-bands/.gv-band/.gv-subcol/.gv-isolated-row/.gv-isolated-title`）。
- Produces: 無（終端 task）。

- [ ] **Step 1: 替換樣式**

styles.css 1618-1633 行（`.gv-grid-wrapper`/`.gv-grid`）替換為：

```css
.gv-flow-wrapper {
  flex: 1;
  overflow: auto;
  padding: 24px 28px 48px;
  background: var(--bg, #f6f7f9);
}
.gv-flow { position: relative; }
.gv-bands {
  display: flex;
  align-items: flex-start;
  gap: 56px;              /* 欄間距＝邊的呼吸空間 */
}
.gv-band {
  display: flex;
  gap: 16px;              /* 子欄間距 */
  padding: 8px;
  border-radius: 8px;
  background: rgba(16, 24, 40, .03);  /* band 視覺分隔（spec D2） */
}
.gv-subcol {
  display: flex;
  flex-direction: column;
  gap: 12px;
  width: 180px;
}
.gv-isolated-row {
  margin-top: 40px;
  padding-top: 16px;
  border-top: 1px dashed var(--border, #d7dde5);
}
.gv-isolated-title {
  font: 600 12px var(--font-sans, sans-serif);
  color: var(--muted, #667085);
  margin-bottom: 10px;
}
.gv-isolated-row .gv-subcol {
  flex-direction: row;
  flex-wrap: wrap;
  width: auto;
}
```

`.gv-node`（1634-1681 行）與 `.gv-edges`（1682-1687 行）**全部保留不動**
（卡片樣式沿用；`.gv-edges` 的 absolute 定位掛在 `.gv-flow` 的 relative 上）。
`.gv-node` 在 flex 子欄內需要固定高：在 `.gv-subcol .gv-node` 加一條：

```css
.gv-subcol .gv-node { min-height: 90px; }
```

- [ ] **Step 2: 全套測試回歸**

Run（cwd＝viewer/）: `npx vitest run`
Expected: 全綠

- [ ] **Step 3: e2e 手動驗收（spec §6）**

```
the-door ui "C:\Users\Ric\Desktop\test-targets\integration-demo" --no-browser --port 8765
```
開 http://localhost:8765 → 開「関聯圖」drawer，驗收：
1. 三欄：`feat-order` | `feat-auth/report/user` | `feat-db`，箭頭一律向右。
2. UserService gap 邊為紅（此 demo 已知 gap）。
3. 點卡片 → detail 面板正常連動。

```
the-door ui "C:\Users\Ric\Desktop\test-targets\the-door-v170" --no-browser --port 8765
```
驗收：
4. L1 五欄、`feat-datamodel-localization`/`feat-domain-models`/`feat-execution-gate` 三孤島在「未宣告關聯」列。
5. 切換版本 → 邊色跟著新版本（F1 回歸：不得殘留上一版 verdict）。
6. drill 進 `feat-ui-http-api` 的 L3 → 折子欄呈現、邊全灰（L3 無 integration）。
7. Legend 顯示 7 項。

- [ ] **Step 4: Commit**

```bash
git rev-parse --abbrev-ref HEAD
git add docs/frontend-local-version-viewer/viewer/styles.css
git commit -m "feat(viewer): flow layout band/subcol styles, isolated row"
```

- [ ] **Step 5: 收尾（由主 agent 執行，非 subagent）**

e2e 全過後：回報使用者、等指示（ff-merge 回 main / push 皆須明示）。
