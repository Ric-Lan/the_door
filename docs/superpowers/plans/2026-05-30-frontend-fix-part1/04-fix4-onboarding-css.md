# Task 04 — FIX-4: 空專案 Onboarding 卡接上 .not-analyzed-cmd + 卡片 CSS（P1）

**Files:**
- Modify: `docs/frontend-local-version-viewer/viewer/js/onboarding.js`
- Modify: `docs/frontend-local-version-viewer/viewer/styles.css`（檔尾新增區塊）
- Modify: `docs/frontend-local-version-viewer/viewer/tests/onboarding.test.js`（新增 2 條斷言）

**根因：** `renderOnboardingCard()` 建出 `<div class="onboarding-card"><h2>+<ol><li><strong>+<pre>...` 結構，但 styles.css 內無 `.onboarding-card` 規則，且 `<pre>` 也未掛 `.not-analyzed-cmd` → 卡片無背景與邊框、指令塊無終端樣式。

**範圍說明：** 只做「基本可用」卡片樣式；品牌化首屏（LogoMark、留白構圖）屬 Part 2，本 task 不做。

**XSS known limitation：** `action.title` 仍走 `innerHTML` 插值（pre-existing 風險，後端 next_actions 為信任來源），本 task 不處理；若 Part 2 重做 onboarding 卡，應改 textContent 或顯式 escape。

**Coverage 影響：** `onboarding.js` 邏輯無新分支；既有 2 條 test 已覆蓋「無快照渲染」與「有快照早退」。

---

## Step-by-step

- [ ] **Step 1: 改 `tests/onboarding.test.js` 加 className + CSS rule 斷言**

開啟 `docs/frontend-local-version-viewer/viewer/tests/onboarding.test.js`，目前內容為：

```js
import { describe, it, expect } from "vitest";
import { renderOnboardingCard } from "../js/onboarding.js";

describe("onboarding card", () => {
  it("renders when state.has_snapshots === false", () => {
    const container = document.createElement("div");
    const payload = {
      state: { project_path: "/x", has_snapshots: false, has_dot_the_door: false },
      next_actions: [
        {
          id: "analyze.first_time",
          title: "首次分析",
          cli_command: "the-door analyze /x",
          priority: 1,
          rationale: "r",
        },
      ],
    };
    renderOnboardingCard(container, payload);
    expect(container.querySelector(".onboarding-card")).not.toBeNull();
    expect(container.textContent).toContain("the-door analyze /x");
  });

  it("does NOT render when state.has_snapshots === true", () => {
    const container = document.createElement("div");
    const payload = { state: { has_snapshots: true }, next_actions: [] };
    renderOnboardingCard(container, payload);
    expect(container.querySelector(".onboarding-card")).toBeNull();
  });
});
```

改寫成：

```js
import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { renderOnboardingCard } from "../js/onboarding.js";

const __dirname = dirname(fileURLToPath(import.meta.url));
const stylesPath = resolve(__dirname, "../styles.css");
const styles = readFileSync(stylesPath, "utf8");

describe("onboarding card", () => {
  it("renders when state.has_snapshots === false", () => {
    const container = document.createElement("div");
    const payload = {
      state: { project_path: "/x", has_snapshots: false, has_dot_the_door: false },
      next_actions: [
        {
          id: "analyze.first_time",
          title: "首次分析",
          cli_command: "the-door analyze /x",
          priority: 1,
          rationale: "r",
        },
      ],
    };
    renderOnboardingCard(container, payload);
    expect(container.querySelector(".onboarding-card")).not.toBeNull();
    expect(container.textContent).toContain("the-door analyze /x");
  });

  it("does NOT render when state.has_snapshots === true", () => {
    const container = document.createElement("div");
    const payload = { state: { has_snapshots: true }, next_actions: [] };
    renderOnboardingCard(container, payload);
    expect(container.querySelector(".onboarding-card")).toBeNull();
  });

  it("cli_command pre uses .not-analyzed-cmd terminal style", () => {
    const container = document.createElement("div");
    const payload = {
      state: { has_snapshots: false },
      next_actions: [
        { id: "x", title: "T", cli_command: "the-door analyze /x", priority: 1, rationale: "r" },
      ],
    };
    renderOnboardingCard(container, payload);
    const pre = container.querySelector(".onboarding-card pre");
    expect(pre).not.toBeNull();
    expect(pre.classList.contains("not-analyzed-cmd")).toBe(true);
  });

  it("styles.css contains .onboarding-card rules", () => {
    expect(styles).toMatch(/\.onboarding-card\s*\{/);
    expect(styles).toMatch(/\.onboarding-card\s+h2\s*\{/);
    expect(styles).toMatch(/\.onboarding-card\s+ol\s*\{/);
  });
});
```

- [ ] **Step 2: 跑測試確認新增 2 條失敗**

```bash
cd docs/frontend-local-version-viewer/viewer
npx vitest run tests/onboarding.test.js --reporter=verbose 2>&1 | tail -20
```

Expected：
- 既有 2 條 PASS
- `cli_command pre uses .not-analyzed-cmd` FAIL（pre 無此 class）
- `styles.css contains .onboarding-card rules` FAIL（規則不存在）

- [ ] **Step 3: 改 `js/onboarding.js` 為 `<pre>` 加 className**

開啟 `docs/frontend-local-version-viewer/viewer/js/onboarding.js`，找到 line 15：

```js
    li.innerHTML = `<strong>${action.title}</strong><pre>${action.cli_command || action.mcp_tool || action.viewer_route}</pre>`;
```

改為：

```js
    li.innerHTML = `<strong>${action.title}</strong><pre class="not-analyzed-cmd">${action.cli_command || action.mcp_tool || action.viewer_route}</pre>`;
```

- [ ] **Step 4: 新增 CSS 到 `styles.css` 檔尾**

開啟 `docs/frontend-local-version-viewer/viewer/styles.css`，跳到檔尾（FIX-3 區塊之後）追加：

```css

/* Onboarding card (FIX-4) — used by onboarding.js for empty-project welcome */
.onboarding-card {
  max-width: 560px; margin: 24px auto;
  background: var(--surface); border: 1px solid var(--line);
  border-radius: 6px; padding: 24px 28px;
  box-shadow: var(--shadow);
}
.onboarding-card h2 { font-size: 20px; margin: 0 0 4px; }
.onboarding-card ol {
  margin: 16px 0 0; padding-left: 20px;
  display: flex; flex-direction: column; gap: 14px;
}
.onboarding-card li strong { display: block; font-size: 13px; margin-bottom: 4px; }
```

- [ ] **Step 5: 跑測試確認全綠**

```bash
cd docs/frontend-local-version-viewer/viewer
npx vitest run tests/onboarding.test.js --reporter=basic 2>&1 | tail -10
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
git add docs/frontend-local-version-viewer/viewer/js/onboarding.js \
        docs/frontend-local-version-viewer/viewer/styles.css \
        docs/frontend-local-version-viewer/viewer/tests/onboarding.test.js
git commit -m "$(cat <<'EOF'
fix(frontend): FIX-4 空專案 Onboarding 卡接上 .not-analyzed-cmd + 卡片 CSS

onboarding.js 為 <pre> 加 .not-analyzed-cmd className，
重用 styles.css:1146 既有終端樣式。

styles.css 新增 .onboarding-card 卡片樣式（max-width 560px、
置中、白底邊框、6px 圓角、既有 shadow token）與 h2/ol/li strong
子規則，提供「基本可用」首屏（品牌化屬 Part 2）。

新增 2 條 test；coverage 100%。

XSS known limitation: action.title 仍走 innerHTML 插值（pre-existing
風險，後端 next_actions 為信任來源），本 task 不處理；Part 2 重做
onboarding 卡時應改 textContent 或顯式 escape。
EOF
)"
```

---

## Acceptance criteria

- 空專案載入（`has_snapshots === false`）呈現置中卡片，top-3 指令為終端塊。
- `has_snapshots === true` 時不渲染卡片（既有早退邏輯不動）。
- `styles.css` 含 `.onboarding-card` 主規則與 `h2`/`ol`/`li strong` 子規則。
- `tests/onboarding.test.js` 4 條全 PASS。
- `npx vitest run --coverage` 4 項 threshold 全綠。
- 手動：用空目錄 `the-door ui <empty-dir>` 啟動，index.html 看到置中卡片與終端塊。
