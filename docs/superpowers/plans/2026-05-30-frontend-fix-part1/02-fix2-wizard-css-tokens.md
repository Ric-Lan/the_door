# Task 02 — FIX-2: wizard.css 單位收斂（rem → px，border-radius → 6px）（P1）

**Files:**
- Modify: `docs/frontend-local-version-viewer/viewer/wizard.css`
- Create: `docs/frontend-local-version-viewer/viewer/tests/wizard-css-units.test.js`

**根因：** 主檔 `styles.css` 全用 px 字面量寫 font-size；`wizard.css` 卻用 rem，造成兩檔慣例不一致、且 root font-size 一旦被改全站偏移。border-radius 也存在 12px / 8px / 5px / 6px 混雜。**沒有對應 CSS 變數可替換**（`--fs-*` / `--radius-*` 系統不存在；新增屬 Part 2 範圍），故本 task 用 px 字面量收斂與主檔對齊。

**改動性質：** 純 CSS 數值替換，無 DOM / JS 改動。透過新增 static unit test 讀 wizard.css 內容驗證收斂結果。

**Coverage 影響：** wizard.css 不在 v8 coverage 範圍（`include: js/**/*.js`），但新增的 test 檔本身會跑進 vitest runner，需要其自身 100% 覆蓋（無分支邏輯，純讀檔 + 斷言）。

---

## Step-by-step

- [ ] **Step 1: 寫失敗測試（驗 wizard.css 內無 rem、border-radius 統一 6px）**

建立新檔 `docs/frontend-local-version-viewer/viewer/tests/wizard-css-units.test.js`，內容：

```js
import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const cssPath = resolve(__dirname, '../wizard.css');
const css = readFileSync(cssPath, 'utf8');

describe('wizard.css unit hygiene', () => {
  it('contains no rem literals (must use px)', () => {
    // Match any numeric value followed by "rem" (e.g. "1.25rem", "0.8rem")
    const remMatches = css.match(/\d*\.?\d+rem\b/g) || [];
    expect(remMatches).toEqual([]);
  });

  it('all border-radius declarations are 6px', () => {
    // Capture every "border-radius: <value>;" declaration
    const radiusDecls = css.match(/border-radius:\s*[^;]+;/g) || [];
    expect(radiusDecls.length).toBeGreaterThan(0);
    for (const decl of radiusDecls) {
      expect(decl).toMatch(/border-radius:\s*6px\s*;/);
    }
  });

  it('contains expected px font-size values (11/12/13/14/20)', () => {
    // Allowed set = px equivalents of the original rem values, rounded to the
    // standard scale per spec FIX-2 mapping table (0.72→11, 0.78/0.8/0.82→12,
    // 0.875/0.9→14, 1.25→20). Adding a new font-size requires updating both
    // wizard.css and this allowlist intentionally — guards against ad-hoc drift.
    const fontSizeDecls = css.match(/font-size:\s*[^;]+;/g) || [];
    expect(fontSizeDecls.length).toBeGreaterThan(0);
    const allowed = new Set(['11px', '12px', '13px', '14px', '20px']);
    for (const decl of fontSizeDecls) {
      const value = decl.replace(/font-size:\s*/, '').replace(/;$/, '').trim();
      expect(allowed.has(value), `unexpected font-size: ${value}`).toBe(true);
    }
  });
});
```

- [ ] **Step 2: 跑測試確認 3 條全失敗**

```bash
cd docs/frontend-local-version-viewer/viewer
npx vitest run tests/wizard-css-units.test.js --reporter=verbose 2>&1 | tail -25
```

Expected：
- `contains no rem literals` FAIL（會列出現有 rem 值，如 `[ '1.25rem', '0.875rem', '0.72rem', ... ]`）
- `all border-radius declarations are 6px` FAIL（會抓到 `border-radius: 12px;` / `8px;` / `5px;`）
- `contains expected px font-size values` FAIL（會抓到 `0.875rem` 等 rem 字串）

- [ ] **Step 3: 替換 wizard.css 圓角為 6px**

開啟 `docs/frontend-local-version-viewer/viewer/wizard.css`，依下列對照逐一替換（共 5 處 border-radius 需改）：

| 行 | 選擇器 | before | after |
|---|---|---|---|
| 17 | `.wizard-card` | `border-radius: 12px;` | `border-radius: 6px;` |
| 50 | `.wizard-option-btn` | `border-radius: 8px;` | `border-radius: 6px;` |
| 131 | `.wizard-summary` | `border-radius: 8px;` | `border-radius: 6px;` |
| 207 | `.wizard-btn-copy` | `border-radius: 5px;` | `border-radius: 6px;` |
| 216 | `.wizard-error-box` | `border-radius: 8px;` | `border-radius: 6px;` |

（line 96 `.wizard-field input[type="text"]` 已是 6px、line 117 `.wizard-btn-primary` 已是 6px、line 192 `.wizard-agent-params` 已是 6px — 三處不動。）

- [ ] **Step 4: 替換 wizard.css 所有 rem 為 px**

依下列對照逐一替換（共 14 處 font-size 用了 rem）：

| 行 | 選擇器 | before | after |
|---|---|---|---|
| 25 | `.wizard-card h2` | `font-size: 1.25rem;` | `font-size: 20px;` |
| 33 | `.wizard-subtitle` | `font-size: 0.875rem;` | `font-size: 14px;` |
| 70 | `.wizard-option-btn strong` | `font-size: 0.9rem;` | `font-size: 14px;` |
| 76 | `.wizard-option-btn span` | `font-size: 0.8rem;` | `font-size: 12px;` |
| 86 | `.wizard-field label` | `font-size: 0.82rem;` | `font-size: 12px;` |
| 97 | `.wizard-field input[type="text"]` | `font-size: 0.875rem;` | `font-size: 14px;` |
| 118 | `.wizard-btn-primary` | `font-size: 0.875rem;` | `font-size: 14px;` |
| 134 | `.wizard-summary` | `font-size: 0.82rem;` | `font-size: 12px;` |
| 142 | `.wizard-summary dt` | `font-size: 0.72rem;` | `font-size: 11px;` |
| 153 | `.wizard-summary dd` | `font-size: 0.8rem;` | `font-size: 12px;` |
| 168 | `.wizard-step` | `font-size: 0.875rem;` | `font-size: 14px;` |
| 195 | `.wizard-agent-params` | `font-size: 0.78rem;` | `font-size: 12px;` |
| 203 | `.wizard-btn-copy` | `font-size: 0.8rem;` | `font-size: 12px;` |
| 219 | `.wizard-error-box` | `font-size: 0.875rem;` | `font-size: 14px;` |

（line 195 的 0.78rem 嚴格映射到 12.48px ≈ 12px；spec 統一靠 12px 端點即可。）

- [ ] **Step 5: 替換後快速計數自檢（在跑測試前做，可立即定位轉錄錯誤）**

```bash
cd docs/frontend-local-version-viewer/viewer
echo "rem 殘留（預期 0）：" && grep -cE "[0-9]rem" wizard.css
echo "border-radius 非 6px 殘留（預期 0）：" && grep -cE "border-radius:\s*(5|8|12)px" wizard.css
echo "border-radius: 6px 總數（預期 8 = 3 原有 + 5 新轉）：" && grep -cE "border-radius:\s*6px" wizard.css
echo "font-size px 總數（預期 14 = 全部從 rem 轉換而來）：" && grep -cE "font-size:\s*[0-9]+px" wizard.css
```

Expected 四個數字：`0` / `0` / `8` / `14`。

若任一不符：
- `rem 殘留 > 0`：grep 找出 → `grep -nE "[0-9]rem" wizard.css`，逐行對照 step 4 表格補替換。
- `border-radius 非 6px 殘留 > 0`：`grep -nE "border-radius:\s*(5|8|12)px" wizard.css` 定位，對照 step 3 表格修。
- `border-radius: 6px 總數 ≠ 8`：可能漏改了某條 12/8/5px、或誤改了原本不該動的選擇器；grep -n 兩端比對。
- `font-size px 總數 ≠ 14`：表示某條 rem 沒被換掉、或誤新增了 font-size；grep 兩端比對。

定位修正後再跑此 step 直到四個數字全對，才進 step 6。

- [ ] **Step 6: 跑測試確認全綠**

```bash
cd docs/frontend-local-version-viewer/viewer
npx vitest run tests/wizard-css-units.test.js --reporter=basic 2>&1 | tail -10
```

Expected：3 條測試全 PASS。

（若 step 5 已通過卻仍 fail，代表 test 寫錯或 css 有其他語法錯誤；先讀完整測試輸出再修。）

- [ ] **Step 7: 跑全 viewer 測試 + coverage 確認 100%**

```bash
cd docs/frontend-local-version-viewer/viewer
npx vitest run --coverage 2>&1 | tail -25
```

Expected：
- 所有測試 PASS（含上一個 task 的 ui-wizard 新斷言 + 新建的 wizard-css-units 測試）
- Coverage 4 項 threshold 全綠
- pre-existing failures（若有）清單不變

- [ ] **Step 8: Commit**

```bash
git add docs/frontend-local-version-viewer/viewer/wizard.css \
        docs/frontend-local-version-viewer/viewer/tests/wizard-css-units.test.js
git commit -m "$(cat <<'EOF'
fix(frontend): FIX-2 wizard.css 單位收斂為 px

把 wizard.css 內 14 處 rem font-size 全部替換為 px 字面量
（11/12/13/14/20px），與 styles.css 主檔慣例對齊；
5 處 border-radius (5px/8px/12px) 統一為 6px。

無 DOM / JS 改動；新增 wizard-css-units.test.js 以 fs 讀檔
靜態驗證收斂結果（無 rem、radius 皆 6px、font-size 在允許 px 集合內）。

不引入新 CSS 變數（--fs-* / --radius-* 系統屬 Part 2 範圍）。
EOF
)"
```

---

## Acceptance criteria

- `wizard.css` 內 `grep -E "\d+rem"` 零命中。
- `wizard.css` 內 `grep -E "border-radius:\s*(5|8|12)px"` 零命中。
- `wizard-css-units.test.js` 3 條全 PASS。
- `npx vitest run --coverage` 4 項 threshold 全綠。
- 手動：開瀏覽器看 wizard 卡片視覺密度與主 Viewer 卡片一致（圓角同 6px、字級為 px 不再受 root font-size 影響）。
