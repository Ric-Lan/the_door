# H1 Implementation Plan：人類面 confidence 缺值誠實化

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (inline) to implement task-by-task. Steps use checkbox (`- [ ]`).

**Goal:** 把 S4 的「confidence None＝未評估」誠實性補滲透到人類面——後端 graph view-model 對齊既有 `"unknown"` token、viewer 顯式渲染「未評估」中性態、停止把缺值謊報成等級。

**Architecture:** 純加法、不碰 persisted/schema。後端 3 個 graph node builder 改 `confidence or "unknown"`（對齊 `view_model.py:164` 先例）；前端 graph.js/ui-list.js 加 `unknown` 分支（label/排序/樣式），具體可觀測 token＝node class `conf-unknown`、edge 自有 dasharray。

**Tech Stack:** Python（pytest，cwd 內層 `the_door/`、`PYTHONUTF8=1`）＋ JS（vitest，cwd `docs/frontend-local-version-viewer/viewer/`，`npm test`）。

**權威 — exact 落點在 spec，勿重貼：** `docs/superpowers/specs/2026-06-07-H1-confidence-honesty-humanface-spec.md`（§3.1 後端／§3.2 前端 concrete token／§4 不變量 H1-1..6）。

**🔴 基線注意：** viewer 測有 **8 個 pre-existing red**（`graph.test.js` cytoscape ×5、`ui-detail.test.js` user-notes ×3，`npm ci` 下確認），與本刀正交。**gate＝紅數維持恰 8、新測全綠**，勿試圖修那 8 個（OUT）。python 全測基線 **1611 passed**。

---

## Task 0（spike，已完成）：L2 confidence scope 判定

**結論（已 spike）**：`graph_view_model.py:159/193` 屬 `build_l2_graph_view_model`（L2Module/L2Anomaly，L2 圖）＝與 H1 的 L1 feature confidence 謊報 bug **不同 surface**。即便 `BlockSummary.confidence`（snapshot L1.5）為 `str|None`，L2 圖誠實化＝獨立未來刀。**H1 嚴格限 L1 三點：`:67`、`:112`、`graph.py:66`。不動 :159/:193。**

---

## Task 1：後端 graph view-model 對齊誠實 token（python TDD）

**Files:**
- Modify: `the_door/src/the_door/core/ui/graph_view_model.py:67,112`（+ `:159` 視 Task 0）
- Modify: `the_door/src/the_door/core/ui/api/handlers/graph.py:66`
- Test: `the_door/tests/unit/core/ui/test_graph_view_model.py`（既有檔擴充或新增；先確認檔名）

- [ ] **Step 1：先確認測試檔位置**

Run: `find the_door/tests -name "*graph_view_model*" -o -name "*test_graph*" | head`
若有既有檔擴充之；無則新建 `the_door/tests/unit/core/ui/test_graph_view_model_confidence.py`。

- [ ] **Step 2：寫失敗測試（characterization：None→"unknown"）**

針對 `build_l1_graph_view_model`（從 L1Output）與 `build_l1_graph_view_model_from_snapshot`（從 snapshot dict）各一筆 confidence=None 的 feature，斷言輸出 node `confidence == "unknown"`：

```python
from the_door.core.ui.graph_view_model import (
    build_l1_graph_view_model,
    build_l1_graph_view_model_from_snapshot,
)


def test_l1_graph_none_confidence_emits_unknown_token():
    """H1-1：未評估 feature（confidence=None）→ node confidence 'unknown'（對齊 view_model.py:164）。"""
    snapshot = {
        "feat-x": {
            "label": "X", "description": "D", "source_node_count": 0,
            "confidence": None, "source_nodes": [],
        }
    }
    vm = build_l1_graph_view_model_from_snapshot(snapshot, [])
    assert vm["nodes"][0]["confidence"] == "unknown"


def test_l1_graph_real_confidence_unchanged():
    """已評估 feature 逐位元不變（純加法、不誤傷）。"""
    snapshot = {
        "feat-y": {
            "label": "Y", "description": "D", "source_node_count": 1,
            "confidence": "high", "source_nodes": [],
        }
    }
    vm = build_l1_graph_view_model_from_snapshot(snapshot, [])
    assert vm["nodes"][0]["confidence"] == "high"
```

（`build_l1_graph_view_model` 走 L1Output：用真實 `L1Output`/`Feature` 建一筆 confidence=None——比照既有 graph_view_model 測的 fixture 風格；若既有測已有 builder helper 沿用之。）

- [ ] **Step 3：跑測試確認失敗**

Run: `cd the_door && PYTHONUTF8=1 python -m pytest tests/unit/core/ui/ -k confidence -q`
Expected: FAIL — node confidence 為 `None`（非 `"unknown"`）。

- [ ] **Step 4：實作（spec §3.1）**

`graph_view_model.py:67` `"confidence": f.confidence` → `"confidence": f.confidence or "unknown"`；
`:112` `summary["confidence"]` → `summary["confidence"] or "unknown"`；
`graph.py:66` `fs.confidence` → `fs.confidence or "unknown"`；
（`:159` 視 Task 0。）

- [ ] **Step 5：跑測試確認通過＋該目錄零回歸**

Run: `cd the_door && PYTHONUTF8=1 python -m pytest tests/unit/core/ui/ -q`
Expected: PASS（新測綠、既有 ui 測不破）。

- [ ] **Step 6：Commit**

```bash
git add the_door/src/the_door/core/ui/graph_view_model.py the_door/src/the_door/core/ui/api/handlers/graph.py the_door/tests/unit/core/ui/
git commit -m "fix(ui): graph view-model 對齊誠實 token confidence None→unknown (H1-1)"
```

---

## Task 2：前端 graph.js 渲染「未評估」中性態（vitest TDD）

**Files:**
- Modify: `docs/frontend-local-version-viewer/viewer/js/graph.js`（:24 confRank／:32 lowestConf／:243 CONF_LABEL／:272 edge／:289 node）
- Test: `docs/frontend-local-version-viewer/viewer/tests/graph.test.js`（**新 describe**，避開既有 5 red 的 `initGraph`/`openGraphDrawer` describe）

- [ ] **Step 1：寫失敗測試（新 describe，import 已 export 的純函式）**

先確認 graph.js 對 `renderGridGraph`/`CONF_LABEL` 的 export 狀態（`grep -n "export" graph.js`）。對可測單元寫斷言：

```javascript
import { describe, it, expect } from 'vitest';
import { renderGridGraph } from '../js/graph.js';

describe('H1 confidence honesty', () => {
  it('unknown-confidence node gets conf-unknown class, not conf-high', () => {
    const container = document.createElement('div');
    document.body.appendChild(container);
    renderGridGraph(container, { nodes: [{ id: 'n1', confidence: 'unknown', label: 'N1' }], edges: [] }, () => {});
    const card = container.querySelector('.gv-node');
    expect(card.classList.contains('conf-unknown')).toBe(true);
    expect(card.classList.contains('conf-high')).toBe(false);
  });

  it('missing-confidence node does NOT fall back to conf-high (no lying)', () => {
    const container = document.createElement('div');
    document.body.appendChild(container);
    renderGridGraph(container, { nodes: [{ id: 'n1', label: 'N1' }], edges: [] }, () => {});
    const card = container.querySelector('.gv-node');
    expect(card.classList.contains('conf-high')).toBe(false);
    expect(card.classList.contains('conf-unknown')).toBe(true);
  });
});
```

（若 `CONF_LABEL` 未 export，補一個只讀斷言走 `renderGridGraph` 的 DOM；若 export 則直接 `expect(CONF_LABEL.unknown).toBe('未評估')`。edge dasharray 斷言視 `_drawGridEdges` 是否可由 `renderGridGraph` 觸發——若 edge 線在 jsdom 因 `getBoundingClientRect` 回 0 而 early-return（:251），則 edge token 改以 export 的純 mapping 斷言，或標記為 gap 於 plan 收尾說明。）

- [ ] **Step 2：跑測試確認失敗**

Run: `cd docs/frontend-local-version-viewer/viewer && npx vitest run tests/graph.test.js -t "H1 confidence honesty"`
Expected: FAIL — 缺值 node 取得 `conf-high`（`node.confidence || 'high'`）。

- [ ] **Step 3：實作（spec §3.2）**

- `:289` `const conf = node.confidence || 'high';` → `'unknown'`。
- `:243` `CONF_LABEL` 加 `unknown: '未評估'`。
- `:24` `confRank` 加 `unknown: 0`。
- `:32` `lowestConf(src?.confidence ?? 'medium', ...)` → `?? 'unknown'`（兩處）。
- `:272` `const conf = edge.lowestConfidence || 'high';` → `'unknown'`；加 `if (conf === 'unknown') line.setAttribute('stroke-dasharray', '1 3');`。

- [ ] **Step 4：跑測試確認通過**

Run: `cd docs/frontend-local-version-viewer/viewer && npx vitest run tests/graph.test.js -t "H1 confidence honesty"`
Expected: PASS。

- [ ] **Step 5：Commit**

```bash
git add docs/frontend-local-version-viewer/viewer/js/graph.js docs/frontend-local-version-viewer/viewer/tests/graph.test.js
git commit -m "fix(viewer): graph.js 渲染未評估中性態、停止謊報信心等級 (H1-2/H1-3)"
```

---

## Task 3：前端 ui-list.js unknown 排序/anomaly（vitest TDD）

**Files:**
- Modify: `docs/frontend-local-version-viewer/viewer/js/ui-list.js`（:4 CONF_PRIORITY；:38 anomaly 保持只認 'low'）
- Test: `docs/frontend-local-version-viewer/viewer/tests/ui-list.test.js`（新 describe）

- [ ] **Step 1：先讀 ui-list.js 的 export 與排序函式**

Run: `grep -n "export\|CONF_PRIORITY\|anomaly\|sort" docs/frontend-local-version-viewer/viewer/js/ui-list.js`
確認可測單元（排序函式或 filter）以決定斷言入口。

- [ ] **Step 2：寫失敗測試**

針對可測單元斷言：(a) unknown feature 不被列為 low-anomaly（H1-4）；(b) unknown 在排序中有自有位置、不當 high/low。具體斷言依 Step 1 找到的 export 形狀填入（若僅 `CONF_PRIORITY` 為模組私有，改測經 export 的 list-builder 行為）。

```javascript
// 範式（依實際 export 調整）：anomaly bucket 只認 'low'
import { describe, it, expect } from 'vitest';
// import { <anomaly-or-sort-fn> } from '../js/ui-list.js';

describe('H1 unknown not low-anomaly', () => {
  it('unknown-confidence feature is NOT flagged as low-confidence anomaly', () => {
    // features = [{confidence:'unknown', anomaly_count:0}, {confidence:'low', anomaly_count:0}]
    // expect anomaly filter 只納 'low' 那筆
  });
});
```

- [ ] **Step 3：跑測試確認失敗 → 實作（spec §3.3）→ 跑通過**

- `:4` `CONF_PRIORITY = { low: 0, medium: 1, high: 2 }` → 加 `unknown: -1`（最低資訊端、與既有方向一致）。
- `:38` anomaly：維持 `f.confidence === 'low'`（unknown 不納），加測釘住。

Run（fail→green）：`cd docs/frontend-local-version-viewer/viewer && npx vitest run tests/ui-list.test.js -t "H1"`

- [ ] **Step 4：Commit**

```bash
git add docs/frontend-local-version-viewer/viewer/js/ui-list.js docs/frontend-local-version-viewer/viewer/tests/ui-list.test.js
git commit -m "fix(viewer): ui-list unknown 排序自有位置、未評估不誤判低信心異常 (H1-4)"
```

---

## Task 4：Gate（H1-5/H1-6）

- [ ] **Step 1：python 全測零回歸**

Run: `cd the_door && PYTHONUTF8=1 python -m pytest -q`
Expected: 1611 passed（+ 新 ui 測），0 failed。

- [ ] **Step 2：vitest 紅數維持恰 8（新測全綠）**

Run: `cd docs/frontend-local-version-viewer/viewer && npm test 2>&1 | grep "Tests "`
Expected: `Tests  8 failed | N passed`——**failed 仍恰 8**（同 pre-existing 8 個），passed 數較基線 893 增加（新測）。**若 failed > 8＝本刀破了東西、回退查。**

- [ ] **Step 3：grep gate — persisted/schema/diff-explanation 未動（H1-5）**

Run:
```bash
git -C C:/Users/Ric/Desktop/the_door diff --name-only d87fa4e -- the_door/schemas/ | grep -v "snapshot.schema.json"   # 應只剩 contract-version 那次的 snapshot.schema（H1 不再動 schema）
git -C C:/Users/Ric/Desktop/the_door diff d87fa4e -- the_door/src/the_door/core/ui/api/handlers/diff.py docs/frontend-local-version-viewer/viewer/js/ui-diff-explanation.js
```
Expected: 第二條為空＝diff-explanation confidence 未動（OUT 邊界守住）。

- [ ] **Step 4：ff-merge main（不主動 push）**

```bash
git -C C:/Users/Ric/Desktop/the_door merge --ff-only <本刀 branch>
```

---

## 驗收（對應 spec §4）

| # | 驗收 | 關卡 |
|---|---|---|
| H1-1 | 後端 3 點 None→"unknown" | Task 1 python 測 |
| H1-2 | `CONF_LABEL.unknown==='未評估'`、不 fall-through | Task 2 vitest |
| H1-3 | node `conf-unknown`（非 conf-high）、edge 自有 dash | Task 2 vitest |
| H1-4 | unknown 不入 low-anomaly、排序自有位置 | Task 3 vitest |
| H1-5 | schema/persisted/diff-explanation 未動 | Task 4 grep |
| H1-6 | 紅數恰 8、python 1611+ 零回歸 | Task 4 全測 |

## Self-Review
- spec §3.1/3.2/3.3 全覆蓋（Task 1/2/3）。✓
- concrete token（`conf-unknown` class、edge `1 3` dash、`CONF_LABEL.unknown`）已對 graph.js:290/272/243 真實碼驗。✓
- 8-red 基線隔離策略明確（新 describe、gate 斷紅數==8）。✓
- module confidence 不虛建（Task 0 spike gated）。✓
- jsdom edge 渲染風險已預先標註退路（Task 2 Step 1 註）。✓
