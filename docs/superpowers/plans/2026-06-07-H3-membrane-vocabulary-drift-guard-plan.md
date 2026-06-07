# H3 Implementation Plan：膜詞彙封閉集 drift-guard（vitest conformance）

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (inline)、task-by-task。Steps 用 checkbox。

**Goal:** 新增單一 vitest 測檔 `tests/membrane-vocabulary.test.js`，讀 checked-in schema enum，**行為斷言**每個「以封閉集為鍵」的 viewer 消費點處理 schema 全集（漏值不 fall-through）。Python 改 enum 而 JS 漏接 → 測紅。

**Architecture:** 純測試新增、**零生產碼**（現況零漂移；僅在某消費點公開行為路徑不可達時退而補 `export`，Task 0 先判）。守 KEY 維度（涵蓋），不動 VALUE（label per-surface）。

**Tech Stack:** JS（vitest，cwd `docs/frontend-local-version-viewer/viewer/`，`npm test`）。讀 repo `the_door/schemas/*.json`（Node fs，跨樹）。零 python。

**權威 — exact 落點/清單/語意在 spec，勿重貼：** `docs/superpowers/specs/2026-06-07-H3-membrane-vocabulary-drift-guard-spec.md`（§1 消費點表＋in/out／§3.2 斷言語意／§3.3 路徑+三形狀／§4 不變量 H3-1..8）。

**🔴 基線注意：** viewer 測有 **8 個 pre-existing red**（`graph.test.js` cytoscape ×5、`ui-detail.test.js` user-notes ×3），與本刀正交。**gate＝紅數維持恰 8、新測全綠**。新檔獨立 → 不碰那 8 個 describe。

**🔴 本刀 TDD 特性（誠實聲明）：** 現況零漂移 ⟹ 對真實消費點的 conformance 斷言**寫即綠**（這是 regression guard 的正常性質）。真正的 red→green 紀律落在 **Task 1 的 helper meta-test**（負例：對故意缺值的假 map 斷言 helper **會丟錯**——helper 寫錯成恆真則 meta-test 紅）＋ **Task 5 的一次性 drift 注入驗證**（暫時破一個消費點、見守紅、還原）。不假裝對既有正確碼「先紅」。

---

## Task 0：spike（gating，必先做；填事實入測檔註解）

**目的：** 關掉三個未知，決定 Task 2-4 的斷言入口（行為 vs export）。

- [ ] **Step 1：schema 相對路徑上溯層數（承 H1 critical：schema 不在 src 下）**

**🔴 base 一致性**：測檔在 `viewer/tests/`，其 `import.meta.url` 的 dir＝`viewer/tests/`（比 cwd=viewer 深一層）。**勿用 cwd-based 探路**（會 off-by-one）。改為**讓測自報**：在 Task 1 的測檔先寫
```javascript
const SCHEMA_DIR = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '<上溯>', 'the_door/schemas');
console.log('SCHEMA_DIR=', SCHEMA_DIR, existsSync(SCHEMA_DIR));
```
先以 `'../../../../..'` 起跑、看 log 的 existsSync→調整 `<上溯>` 到 `true`（單一真相＝測自身 `import.meta.url`）。層數推算：`viewer/tests`→viewer→frontend-local-version-viewer→docs→repo-root（4 個 `..`），再 `the_door/schemas` ⟹ 起手猜 `'../../../..'`，以 log 實證為準。

- [ ] **Step 2：三 schema 的精確 JSON path 與形狀**

讀並記下（exact key path）：
- `update-report.schema.json`：change_type enum 的物件路徑（`:97-103`，兩處 l1_changes/l2_details——取一致那份）；risk_flags 的 `items.enum`（`:110-113`）。
- `l1-output.schema.json`：confidence 的 `oneOf[].const`（`:62-66`）。
記入 helper 的 shape 對應表（`'enum'`/`'items-enum'`/`'oneof-const'`）。

- [ ] **Step 3：每消費點公開行為路徑可達性（決定行為斷言 vs 退 export）**

對 spec §1-in 每點，grep 其「公開消費函式」並判 jsdom 可達：
```bash
grep -n "export\|buildDisplayLabel\|badgeFor\|changeSymbol\|CONF_LABEL\|confidenceMap\|riskCounts\|DIFF_LABELS\|CHANGE_TYPE_LABEL" docs/frontend-local-version-viewer/viewer/js/{graph,mindmap-util,layers,ui-detail,ui-list,viewmodel,ui-diff-explanation}.js
```
逐點裁定（記入測檔註解）：
- `graph.js TYPE_TAG` → 經 `buildDisplayLabel(node)`（:10，已 export？確認）餵每值斷言 label 含 tag、非裸 label。
- `mindmap-util.js DIFF_BADGE`（export）→ 經 `badgeFor`（:16）或直接集斷言 keys ⊇ 4。
- `layers.js DIFF_LABELS` → 找其公開渲染入口（:451 在哪個 export 函式內）；不可達則：本點以「import 的 `changeSymbol` 行為」覆蓋 symbol 面，DIFF_LABELS 若內部不可達→記 gap 或退 export。
- `ui-detail.js CHANGE_TYPE_LABEL` → 找 :201 所在的 export 函式餵值。
- `ui-list.js changeSymbol`（export 函式）→ 直接 `changeSymbol(v)` 每值 ≠ `'?'`。
- `viewmodel.js riskCounts` → 找其 export 計數函式，餵含各 risk_flag 的 input 斷言計數鍵齊；不可達則退「該物件若 export 集斷言」。
- `graph.js CONF_LABEL` / `ui-diff-explanation.js confidenceMap` / `ui-list.js CONF_PRIORITY` → 確認可達入口（CONF_PRIORITY 經排序函式 `sortCards`('risk') 行為；confidenceMap 經 `appendDiffExplanationSection` 已有測法可借；CONF_LABEL 經 graph 渲染或 export）。

**Step 3 產物＝一張「消費點→斷言入口（行為 fn / 集斷言 / 退 export）」對照表**，寫進測檔頂註解。**若某點唯一可達法是 export 私有 const，記下該 export 為本刀唯一生產碼變動（純加法）並於 Task 5 grep gate 接受之。**

---

## Task 1：helper + meta-test（TDD red→green 在此）

**Files:** Create `docs/frontend-local-version-viewer/viewer/tests/membrane-vocabulary.test.js`

- [ ] **Step 1：先寫 meta 負例測 + helper 空殼（red）→ 再實作 helper（green）**

**TDD 順序**：先寫 meta 測 ＋ `assertCovers` **空殼**（`function assertCovers(){}`＝恆綠）→ 跑 meta「對缺值集會判失敗」→ **紅**（空殼不丟錯）→ 實作正確 helper → **綠**。這是本刀真正的 red→green。helper 同檔共用、**不 export**（測檔內部即可）。

```javascript
import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const SCHEMA_DIR = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  <Task0-Step1 上溯>, 'the_door/schemas',
);

function readSchemaEnum(file, jsonPathFn) {
  const doc = JSON.parse(readFileSync(path.join(SCHEMA_DIR, file), 'utf8'));
  const vals = jsonPathFn(doc);                       // Task0-Step2 形狀
  if (!Array.isArray(vals) || vals.length === 0) {
    throw new Error(`schema enum 解析失敗：${file}`); // fail-loud（H3-4/§3.3）
  }
  return vals;
}

// 守界 helper：keySet 須涵蓋 schemaSet，否則列出缺值丟錯
function assertCovers(label, keySet, schemaSet) {
  const missing = schemaSet.filter(v => !keySet.has(v));
  expect(missing, `${label} 漏接膜值：${missing.join(',')}`).toEqual([]);
}

describe('guard 自我有效性（meta）', () => {
  it('readSchemaEnum 對解析失敗 fail-loud', () => {
    expect(() => readSchemaEnum('update-report.schema.json', () => null)).toThrow();
  });
  it('assertCovers 對缺值集會判失敗（非恆綠）', () => {
    const incomplete = new Set(['added', 'removed']);          // 缺 attribute/dependency
    expect(() => assertCovers('x', incomplete, ['added','removed','attribute_changed','dependency_changed']))
      .toThrow();
  });
});

// helper 同檔共用、不 export。
```

- [ ] **Step 2：跑確認 red→green**

Run: `cd docs/frontend-local-version-viewer/viewer && npx vitest run tests/membrane-vocabulary.test.js -t "meta"`
Expected: 空殼 `assertCovers` 下 meta「對缺值集會判失敗」**紅**（不丟錯）→ 實作正確 helper → **綠**。證 assertCovers 非恆真＝本刀 red→green 核心。

---

## Task 2：change_type 軸 conformance（5 消費點，行為為主）

**Files:** 續 `tests/membrane-vocabulary.test.js`（新 describe）

- [ ] **Step 1：依 Task 0 對照表寫斷言**

```javascript
describe('change_type 封閉集 drift-guard', () => {
  const SET = readSchemaEnum('update-report.schema.json', <Task0 change_type path>);
  // 每消費點一 it，行為斷言不 fall-through：
  // changeSymbol：SET.forEach(v => expect(changeSymbol(v)).not.toBe('?'))
  // buildDisplayLabel / badgeFor / CHANGE_TYPE_LABEL 入口 / DIFF_LABELS 入口：餵 v 斷言非哨兵
  // DIFF_BADGE（export）：assertCovers('DIFF_BADGE', new Set(Object.keys(DIFF_BADGE)), SET)
});
```

- [ ] **Step 2：跑確認綠（現況零漂移）＋零其他回歸**

Run: `npx vitest run tests/membrane-vocabulary.test.js -t "change_type"`
Expected: PASS（5 消費點皆覆蓋 4 值）。**若某點紅＝既有真漂移 bug、當場修該消費點（補缺鍵/分支）並記入 commit。**

---

## Task 3：risk_flags 軸 conformance

- [ ] **Step 1：寫 `riskCounts` 涵蓋 3 值斷言（集或計數行為，依 Task 0）**；排序 `RISK_PRIORITY` **不測**（spec §1-out）。
- [ ] **Step 2：跑確認綠。** `npx vitest run tests/membrane-vocabulary.test.js -t "risk_flags"`

---

## Task 4：confidence 軸 conformance（schema 3 ∪ {unknown}）

- [ ] **Step 1：`const SET = [...readSchemaEnum(l1-output, oneof-const), 'unknown']`（編碼不對稱，spec §0/§3.2）**

對 `CONF_LABEL`（不 fall-through 到 undefined/空白）、`confidenceMap`（每值非裸 fall-through）、`CONF_PRIORITY`（**keys ⊇ SET**——漏鍵落 `?? 2` 謊報 medium，spec §1-in 例外）三點斷言。

- [ ] **Step 2：跑確認綠。** `npx vitest run tests/membrane-vocabulary.test.js -t "confidence"`

---

## Task 5：guard 涵蓋邊界 + gate + drift 注入驗證 + merge

- [ ] **Step 1：guard 涵蓋邊界誠實處置（spec §3.4）**

評估反向掃描成本：
- 低成本可行 → 加一條「掃 viewer/js 找含 ≥2 個膜值字面量的 object literal 檔案集 ⊆ 已測檔案集」斷言。
- 否則 → 在測檔頂加維護規約註解（新增膜詞彙消費點須登記於此），接受手動納管。**二擇一、記入測檔。**

- [ ] **Step 2：一次性 drift 注入驗證（證 guard 真會抓）**

暫時把某消費點刪一個鍵（如 `mindmap-util.js DIFF_BADGE` 移除 `dependency_changed`）→ 跑該 describe 應**紅**（守住）→ **還原**。記錄已驗（不留改動）。

- [ ] **Step 3：全 vitest gate**

Run: `cd docs/frontend-local-version-viewer/viewer && npm test 2>&1 | grep -E "Test Files|Tests "`
Expected: **failed 仍恰 8**（pre-existing），passed＝900＋本刀新測數。**failed>8＝回退查。**

- [ ] **Step 4：grep gate — 零生產碼（或僅 export 加法）**

Run:
```bash
git -C C:/Users/Ric/Desktop/the_door status --porcelain
```
Expected: 只有新測檔 `tests/membrane-vocabulary.test.js`（＋若 Task 0 判需 export，則對應 js 檔僅多 `export` 字；diff 審確認無行為改動）。**無 schema/persisted/runtime 邏輯改動。**

- [ ] **Step 5：Commit ＋ ff-merge（不主動 push）**

```bash
git -C C:/Users/Ric/Desktop/the_door add docs/frontend-local-version-viewer/viewer/tests/membrane-vocabulary.test.js <若有 export 的 js>
git -C C:/Users/Ric/Desktop/the_door commit -m "test(viewer): 膜詞彙封閉集 drift-guard — schema↔JS key 涵蓋 conformance (H3)"
git -C C:/Users/Ric/Desktop/the_door merge --ff-only <本刀 branch>   # 若已在 worktree branch 上 commit
```

---

## 驗收（對應 spec §4）

| # | 驗收 | 關卡 |
|---|---|---|
| H3-1 | change_type 5 消費點不 fall-through schema 4 值 | Task 2 |
| H3-2 | riskCounts ⊇ 3 值 | Task 3 |
| H3-3 | confidence 3∪{unknown} 涵蓋（含 CONF_PRIORITY） | Task 4 |
| H3-4 | 讀 checked-in schema、解析失敗 fail-loud | Task 1 |
| H3-5 | 零 runtime/schema/persisted（至多 export 加法） | Task 5 Step 4 |
| H3-6 | 排序 value 不綁；排序 map（除 CONF_PRIORITY）不測 | Task 2-4 斷言內容 |
| H3-7 | meta 負例證非恆綠 ＋ 涵蓋邊界誠實標明 | Task 1 / Task 5 Step 1-2 |
| H3-8 | 紅數恰 8、其餘 vitest 零回歸 | Task 5 Step 3 |

## Self-Review
- 機制＝行為斷言為主（spec 定稿），Task 0 先判每點入口、避免假設可 import。✓
- TDD 誠實：red→green 落在 helper meta-test（Task 1）＋drift 注入（Task 5），不假裝對正確碼先紅。✓
- 零生產碼為預設，export 為唯一可能加法、grep gate 守住。✓
- CONF_PRIORITY 例外（漏鍵謊報非良性）已單列入 confidence 軸。✓
- 跨樹 fs 路徑 Task 0 先親探、fail-loud（非 silent skip）。✓
- 8-red 基線隔離（獨立新檔）。✓
