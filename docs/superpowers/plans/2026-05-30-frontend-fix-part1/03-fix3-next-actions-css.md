# Task 03 — FIX-3: 「建議的下一步」指令塊接上終端樣式 + 區塊 CSS（P1）

**Files:**
- Modify: `docs/frontend-local-version-viewer/viewer/js/ui-next-actions.js`
- Modify: `docs/frontend-local-version-viewer/viewer/styles.css`（檔尾新增區塊）
- Modify: `docs/frontend-local-version-viewer/viewer/tests/ui-next-actions.test.js`（新增 2 條斷言）

**根因：** `appendNextActionsSection()` 建出 `<section class="next-actions-section"><ol><li><strong>+<pre>...` 結構，但 styles.css 內無 `.next-actions-section` 規則，且 `<pre>` 也未掛 `.not-analyzed-cmd` → 只吃通用 `pre` 樣式，無終端外觀、無間距節奏。`.not-analyzed-cmd` 既有於 `styles.css:1146`（深底淺字終端塊）。

**改動性質：** 1 行 className + 7 行新 CSS + 2 條 test 斷言。`ui-detail.js` 三處 call site (lines 271/301/404) 共用此 `appendNextActionsSection`，改一處即全 cover。

**Coverage 影響：** `ui-next-actions.js` 內邏輯無新分支，既有 2 條 test 已覆蓋「有資料」與「空資料」兩條 path；新增的 2 條 test 是輔助斷言不增加 source 分支。

---

## Step-by-step

- [ ] **Step 1: 改 `tests/ui-next-actions.test.js` 加 className + CSS rule 斷言**

開啟 `docs/frontend-local-version-viewer/viewer/tests/ui-next-actions.test.js`，目前內容（line 1-22）為：

```js
import { describe, it, expect } from "vitest";
import { appendNextActionsSection } from "../js/ui-next-actions.js";

describe("ui-next-actions", () => {
  it("renders 建議的下一步 section when next_actions present", () => {
    const container = document.createElement("div");
    const feature = {
      next_actions: [
        { id: "x", title: "T", cli_command: "ls", priority: 1, rationale: "r" },
      ],
    };
    appendNextActionsSection(container, feature);
    expect(container.querySelector(".next-actions-section")).not.toBeNull();
    expect(container.textContent).toContain("ls");
  });

  it("renders nothing when next_actions empty", () => {
    const container = document.createElement("div");
    appendNextActionsSection(container, { next_actions: [] });
    expect(container.querySelector(".next-actions-section")).toBeNull();
  });
});
```

改寫成：

```js
import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { appendNextActionsSection } from "../js/ui-next-actions.js";

const __dirname = dirname(fileURLToPath(import.meta.url));
const stylesPath = resolve(__dirname, "../styles.css");
const styles = readFileSync(stylesPath, "utf8");

describe("ui-next-actions", () => {
  it("renders 建議的下一步 section when next_actions present", () => {
    const container = document.createElement("div");
    const feature = {
      next_actions: [
        { id: "x", title: "T", cli_command: "ls", priority: 1, rationale: "r" },
      ],
    };
    appendNextActionsSection(container, feature);
    expect(container.querySelector(".next-actions-section")).not.toBeNull();
    expect(container.textContent).toContain("ls");
  });

  it("renders nothing when next_actions empty", () => {
    const container = document.createElement("div");
    appendNextActionsSection(container, { next_actions: [] });
    expect(container.querySelector(".next-actions-section")).toBeNull();
  });

  it("each cli_command pre uses .not-analyzed-cmd terminal style", () => {
    const container = document.createElement("div");
    appendNextActionsSection(container, {
      next_actions: [
        { id: "x", title: "T", cli_command: "the-door analyze .", priority: 1 },
      ],
    });
    const pre = container.querySelector(".next-actions-section pre");
    expect(pre).not.toBeNull();
    expect(pre.classList.contains("not-analyzed-cmd")).toBe(true);
  });

  it("styles.css contains .next-actions-section rules", () => {
    expect(styles).toMatch(/\.next-actions-section\s*\{/);
    expect(styles).toMatch(/\.next-actions-section\s+h3\s*\{/);
    expect(styles).toMatch(/\.next-actions-section\s+ol\s*\{/);
  });
});
```

- [ ] **Step 2: 跑測試確認新增 2 條失敗**

```bash
cd docs/frontend-local-version-viewer/viewer
npx vitest run tests/ui-next-actions.test.js --reporter=verbose 2>&1 | tail -20
```

Expected：
- 既有 2 條 PASS
- `each cli_command pre uses .not-analyzed-cmd` FAIL（className 未設）
- `styles.css contains .next-actions-section rules` FAIL（CSS 規則不存在）

- [ ] **Step 3: 改 `js/ui-next-actions.js` 加 className**

開啟 `docs/frontend-local-version-viewer/viewer/js/ui-next-actions.js`，找到 line 17-18：

```js
    const pre = document.createElement("pre");
    pre.textContent = action.cli_command || action.mcp_tool || action.viewer_route || "";
```

改為：

```js
    const pre = document.createElement("pre");
    pre.className = "not-analyzed-cmd";
    pre.textContent = action.cli_command || action.mcp_tool || action.viewer_route || "";
```

- [ ] **Step 4: 新增 CSS 到 `styles.css` 檔尾**

開啟 `docs/frontend-local-version-viewer/viewer/styles.css`，跳到檔尾（最後一行後）追加：

```css

/* Next actions section (FIX-3) — used by ui-next-actions.js across L1/L2/L3/diff details */
.next-actions-section { margin-bottom: 16px; }
.next-actions-section h3 {
  margin: 0 0 8px; font-size: 11px; color: var(--muted);
  text-transform: uppercase; letter-spacing: .05em;
}
.next-actions-section ol {
  margin: 0; padding-left: 20px;
  display: flex; flex-direction: column; gap: 12px;
}
.next-actions-section li strong {
  display: block; font-size: 13px; color: var(--text); margin-bottom: 4px;
}
.next-actions-section li .not-analyzed-cmd { margin-top: 2px; }
```

- [ ] **Step 5: 跑測試確認全綠**

```bash
cd docs/frontend-local-version-viewer/viewer
npx vitest run tests/ui-next-actions.test.js --reporter=basic 2>&1 | tail -10
```

Expected：4 條測試全 PASS。

- [ ] **Step 6: 跑全 viewer 測試 + coverage 確認 100%**

```bash
cd docs/frontend-local-version-viewer/viewer
npx vitest run --coverage 2>&1 | tail -25
```

Expected：所有測試 PASS、4 項 threshold 全綠、pre-existing failures 不變。

- [ ] **Step 7: Commit**

```bash
git add docs/frontend-local-version-viewer/viewer/js/ui-next-actions.js \
        docs/frontend-local-version-viewer/viewer/styles.css \
        docs/frontend-local-version-viewer/viewer/tests/ui-next-actions.test.js
git commit -m "$(cat <<'EOF'
fix(frontend): FIX-3 建議的下一步指令塊接上 .not-analyzed-cmd + 區塊 CSS

ui-next-actions.js 為 <pre> 加 .not-analyzed-cmd className，
重用 styles.css:1146 既有終端樣式（深底淺字、monospace、可選取）。

styles.css 新增 .next-actions-section / h3 / ol / li strong 規則，
提供區塊間距節奏與標題小字 uppercase。

新增 2 條 test（pre className 與 CSS rule 存在）；coverage 100%。
EOF
)"
```

---

## Acceptance criteria

- 注入含 `next_actions` 的 feature 後，`<pre>` 元素帶 `.not-analyzed-cmd` className 並呈深色終端外觀。
- `styles.css` 含 `.next-actions-section` 主規則與 `h3`/`ol`/`li strong` 子規則。
- `tests/ui-next-actions.test.js` 4 條全 PASS。
- `npx vitest run --coverage` 4 項 threshold 全綠。
- 手動：開啟有 `next_actions` 的 feature detail panel，看到深色終端塊與項目間 12px 間距。
