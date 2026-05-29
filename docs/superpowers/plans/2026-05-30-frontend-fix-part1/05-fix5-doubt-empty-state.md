# Task 05 — FIX-5: 疑義空狀態 `.no-selection` → `.empty-state` + 補齊 renderDoubtDetail 覆蓋（P2）

**Files:**
- Modify: `docs/frontend-local-version-viewer/viewer/js/ui-doubt.js`（line 20，1 個 class 名替換）
- Modify: `docs/frontend-local-version-viewer/viewer/tests/ui-doubt.test.js`（補齊 `renderDoubtDetail` 兩條分支的覆蓋）

**根因：**
1. `ui-doubt.js:20` 的空狀態用 `class="no-selection"`，但 styles.css 內無此 class → 樣式無效。`styles.css:704` 有既有 `.empty-state`（斜體灰字，全站統一空狀態），應改用之。
2. 既有 `tests/ui-doubt.test.js` 只測 `statusBadge`；`renderDoubtDetail` 與內部 `escapeHtml` 完全未被測試呼叫 → 100% coverage threshold 之下這個檔案很可能 baseline 是 borderline，本 task 順手補齊兩條分支（null vs non-null）的覆蓋。

**注意（DEFER 範圍區隔）：** 整個疑義面板的契約與配色語意問題（6 態工作流、`current_state` 欄位名、`state_history` 等）在 spec DEFER 段落明示「不要 patch，排程重做（轉 Part 2）」。本 task **只動空狀態那一行 className**，**不重繪面板、不改契約、不動 statusBadge 配色**。

**Coverage 影響：** 補的 2 條 `renderDoubtDetail` test 會把該函式與 `escapeHtml` 補進覆蓋率，是 task 的必要部分。

---

## Step-by-step

- [ ] **Step 1: 寫失敗測試（empty-state class + renderDoubtDetail 兩分支）**

開啟 `docs/frontend-local-version-viewer/viewer/tests/ui-doubt.test.js`，目前內容為：

```js
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

改寫成：

```js
import { statusBadge, renderDoubtDetail } from '../js/ui-doubt.js';

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

describe('renderDoubtDetail', () => {
  it('null doubt renders .empty-state placeholder (not .no-selection)', () => {
    const container = document.createElement('div');
    renderDoubtDetail(container, null);
    expect(container.querySelector('.empty-state')).not.toBeNull();
    expect(container.querySelector('.no-selection')).toBeNull();
    expect(container.textContent).toContain('請選擇一個疑義項目');
  });

  it('non-null doubt renders detail panel with title + status badge + fields', () => {
    const container = document.createElement('div');
    renderDoubtDetail(container, {
      title: 'Test doubt',
      anomaly_type: 'orphan',
      description: 'desc',
      status: 'resolved',
      assignee: 'alice',
      source_feature: 'feat-x',
    });
    expect(container.querySelector('.doubt-detail')).not.toBeNull();
    expect(container.querySelector('.doubt-title').textContent).toBe('Test doubt');
    expect(container.querySelector('.confidence-badge-high')).not.toBeNull();
    expect(container.textContent).toContain('orphan');
    expect(container.textContent).toContain('alice');
    expect(container.textContent).toContain('feat-x');
  });

  it('non-null doubt with missing fields renders em dashes via nullish fallback', () => {
    const container = document.createElement('div');
    renderDoubtDetail(container, { status: 'open' });
    // title fallback '（無標題）'
    expect(container.querySelector('.doubt-title').textContent).toBe('（無標題）');
    // each missing field renders '—'
    const fieldValues = container.querySelectorAll('.doubt-field span:nth-child(2)');
    // fields rendered: 異常類型, 說明, 狀態, 指派對象, 來源功能
    // status 'open' renders badge with label '未解決' (not '—'), others render '—'
    expect(fieldValues[0].textContent).toBe('—'); // 異常類型
    expect(fieldValues[1].textContent).toBe('—'); // 說明
    expect(fieldValues[3].textContent).toBe('—'); // 指派對象
    expect(fieldValues[4].textContent).toBe('—'); // 來源功能
  });

  it('escapes HTML in doubt fields', () => {
    const container = document.createElement('div');
    renderDoubtDetail(container, {
      title: '<script>alert(1)</script>',
      status: 'open',
    });
    // Two-pronged assertion (jsdom-version-independent):
    // (1) NO actual <script> element was created — proves escape happened before HTML parse
    // (2) textContent is the literal source string — proves chars are present as text, not markup
    expect(container.querySelector('script')).toBeNull();
    expect(container.querySelector('.doubt-title').textContent).toBe('<script>alert(1)</script>');
  });
});
```

- [ ] **Step 2: 跑測試確認新增分支失敗**

```bash
cd docs/frontend-local-version-viewer/viewer
npx vitest run tests/ui-doubt.test.js --reporter=verbose 2>&1 | tail -20
```

Expected：
- 既有 5 條 statusBadge PASS
- `null doubt renders .empty-state` FAIL（class 還是 `.no-selection`）
- `non-null doubt renders detail panel` 等 3 條 PASS（renderDoubtDetail 的非空分支不依賴本 fix）

如果非空分支也失敗，多半是 `import` 漏改、檢查 step 1 import 行加上 `renderDoubtDetail`。

- [ ] **Step 3: 改 `js/ui-doubt.js` 替換 className**

開啟 `docs/frontend-local-version-viewer/viewer/js/ui-doubt.js`，找到 line 20：

```js
  if (!doubt) { container.innerHTML = '<p class="no-selection">請選擇一個疑義項目。</p>'; return; }
```

改為：

```js
  if (!doubt) { container.innerHTML = '<p class="empty-state">請選擇一個疑義項目。</p>'; return; }
```

- [ ] **Step 4: 跑測試確認全綠**

```bash
cd docs/frontend-local-version-viewer/viewer
npx vitest run tests/ui-doubt.test.js --reporter=basic 2>&1 | tail -10
```

Expected：9 條測試全 PASS（5 條既有 statusBadge + 4 條新 renderDoubtDetail）。

- [ ] **Step 5: 跑全 viewer 測試 + coverage 確認 100%**

```bash
cd docs/frontend-local-version-viewer/viewer
npx vitest run --coverage 2>&1 | tail -25
```

Expected：
- 所有測試 PASS
- `ui-doubt.js` coverage 100%（renderDoubtDetail + escapeHtml 都被測到）
- 4 項 threshold 全綠
- pre-existing failures 清單不變

- [ ] **Step 6: Commit**

```bash
git add docs/frontend-local-version-viewer/viewer/js/ui-doubt.js \
        docs/frontend-local-version-viewer/viewer/tests/ui-doubt.test.js
git commit -m "$(cat <<'EOF'
fix(frontend): FIX-5 疑義空狀態改用 .empty-state 既有樣式

ui-doubt.js:20 的空狀態 className 由不存在的 .no-selection
改為 styles.css:704 既有 .empty-state（斜體灰字、全站統一）。

順手補齊 renderDoubtDetail 測試覆蓋（既有測試只測 statusBadge，
renderDoubtDetail + escapeHtml 未被呼叫），加 4 條斷言涵蓋
null/non-null/missing-fields/HTML-escape 四種分支。

不動 statusBadge 配色、不動契約欄位名、不重繪面板
（DEFER 段落明示「待 Part 2 重做」，本 task 嚴守邊界）。
EOF
)"
```

---

## Acceptance criteria

- `js/ui-doubt.js` 不再含 `class="no-selection"`。
- `js/ui-doubt.js` 含 `class="empty-state"`。
- `tests/ui-doubt.test.js` 9 條全 PASS。
- `npx vitest run --coverage` `ui-doubt.js` 4 項 100%，整體 threshold 全綠。
- `statusBadge` 配色、契約欄位名（`status`/`assignee`/`source_feature`/`anomaly_type`）皆未動（這些屬 DEFER 範圍）。
