# Task 01 — Wizard CSS 布局根本修正

## 目標

修正 wizard 右側大空白問題，並清除 wizard.css 中所有 unresolved CSS token。

## 設計來源（必讀，避免幻覺）

- **spec §1.5.1–1.5.3**：`frontend-onboarding-flow-spec-part2 (1).md` — 版型數值
- **spec §1.4**：token 替換清單（`var(--radius-card)` 等不存在的 token）
- **spec §1.5.5**：`.wizard-card` 最終形態
- **`viewer/styles.css`**：真實存在的 token 清單（`--accent`、`--line`、`--surface` 等）

## 前置確認

在開工前，grep 驗證以下 token 確實存在於 `viewer/styles.css`（避免寫入新的幻覺 token）：

```bash
grep -n "var(--surface)" docs/frontend-local-version-viewer/viewer/styles.css | head -3
grep -n "var(--line)" docs/frontend-local-version-viewer/viewer/styles.css | head -3
grep -n "var(--rail-bg)" docs/frontend-local-version-viewer/viewer/styles.css | head -3
```

`--rail-bg`/`--rail-bg-2`/`--rail-line`/`--rail-text`/`--rail-muted`/`--rail-dim` 應在 `styles.css :root` 找到（task 2 from Part 2 plan commit `299c166` 已加入）。

## 改動清單

全部改動集中在一個檔案：`docs/frontend-local-version-viewer/viewer/wizard.css`

### Step 1 — 修正 `.wizard-content`（spec §1.5.2）

**現況**（wizard.css 約第 394–399 行）：
```css
.wizard-content {
  flex: 1;
  position: relative;
  overflow: hidden;
  background: var(--surface);
}
```

**改為**：
```css
.wizard-content {
  flex: 1; min-width: 0;
  display: flex; flex-direction: column; align-items: center;
  overflow-y: auto;
  background: var(--surface);
}
```

> 理由：`align-items:center` 是消除右側空白的關鍵（spec §1.5.1 明文）。
> `position:relative; overflow:hidden` 移除，讓 `.wizard-screen` 可用正常流定位。
>
> **scroll 可行性說明**：`overflow-y:auto` 在此有效，因為 `.wizard-shell { position:absolute; inset:0 }`
> 給了整個 shell 固定高度（由 `#wizard-mount { height:100vh }` 撐起），`.wizard-content { flex:1 }`
> 繼承該固定高度，scroll container 成立。若未來 `wizard.html` 的 `#wizard-mount` 高度設定
> 被移除，需回頭在 `.wizard-content` 補 `height:100%`。

### Step 2 — 修正 `.wizard-screen`（spec §1.5.2）

**現況**（wizard.css 約第 400–405 行）：
```css
.wizard-screen {
  position: absolute; inset: 0;
  padding: 52px 56px;
  display: flex; flex-direction: column;
  overflow-y: auto;
}
```

**改為**：
```css
.wizard-screen {
  width: 100%; max-width: 560px;
  padding: 56px 40px 40px;
  display: flex; flex-direction: column;
  min-height: 100%;
}
```

> 理由：`position:absolute; inset:0` 使內容撐滿 content 寬（沒有 cap）。
> `max-width:560px` + 上層 `align-items:center` = 置中的定寬欄，空白消失。
> `padding` 從 `52px 56px` 改為 `56px 40px 40px`（spec §1.5.2 說明：原型 56px 左右 padding 是空白的幫兇之一）。
> `overflow-y` 移到 `.wizard-content` 那層，此處移除。
> `min-height:100%` 確保短頁面仍可把 `.wizard-actions` 推到底（配合 `margin-top:auto`）。

### Step 3 — 補齊 `.wizard-card` 殘留屬性（spec §1.5.5）

**前置確認**：先 grep 確認現況：
```bash
grep -A 8 "wizard-shell .wizard-card" docs/frontend-local-version-viewer/viewer/wizard.css
```

預期找到 wizard.css 第 529 行已有：
```css
.wizard-shell .wizard-card {
  background: transparent;
  border: none;
  box-shadow: none;
  max-width: none;
  padding: 0;
  width: 100%;
}
```

**只需補一個缺失屬性**：在此 rule 內加入 `border-radius: 0;`

```css
.wizard-shell .wizard-card {
  background: transparent;
  border: none;
  box-shadow: none;
  max-width: none;      /* .wizard-screen 已負責 cap，此處刻意解除雙層限制 */
  padding: 0;
  width: 100%;
  border-radius: 0;     /* ← 新增：清除 FIX-1 的 6px 殘留 */
}
```

> ⚠️ **不要新增第二個 `.wizard-shell .wizard-card` block**，這個 rule 已存在。
> FIX-1 原區塊（wizard.css 第 14–22 行）不動，以免測試斷言斷掉。

### Step 4 — Rail 寬度調整（spec §1.5.1）

找 `.wizard-rail { width: 312px` 這一行，改為：
```css
.wizard-rail {
  width: 300px;   /* spec §1.5.1: 312 → 300, 對齊設計系統 minmax(300px,380px) 慣例 */
  flex-shrink: 0;
  /* 其餘不動 */
```

### Step 5 — 替換所有 `var(--radius-card)` → `6px`（spec §1.4）

用 replace_all 把 wizard.css 中全部 `var(--radius-card)` 換成 `6px`。
共 **8 處**（grep 確認在 wizard.css 第 426、486、571、610、686、705、762、815 行附近）。

驗收：
```bash
grep -n "radius-card" docs/frontend-local-version-viewer/viewer/wizard.css
# 預期輸出：空（零命中）
```

### Step 6 — 內容間距修正（spec §1.5.3）

以下三個小修正，grep 找到對應行後修改：

| 目標 | 現況 | 改為 | 來源 |
|---|---|---|---|
| `.wizard-eyebrow { margin }` | `margin: 0 0 12px` | `margin: 0 0 10px` | spec §1.5.3 eyebrow→h2 10px |
| `.wizard-options { gap }` | `gap: 10px` | `gap: 12px` | spec §1.5.3 option card 間距 12px |
| `.wizard-options { margin-bottom }` | `margin-bottom: 20px` | 移除此行，改在 `.wizard-actions` 加 `margin-top: auto; padding-top: 30px` | spec §1.5.3 action 列推到底 |

> `.wizard-actions` 若不存在，先 grep 確認 wizard.css 有無此 class，沒有則加：
> ```css
> .wizard-actions { margin-top: auto; padding-top: 30px; display: flex; align-items: center; }
> ```

## 測試

### 自動測試

改完後執行：
```bash
cd docs/frontend-local-version-viewer/viewer
npx jest --testPathPattern="wizard" 2>&1 | tail -20
```

預期：全部既有 wizard test 通過（853 JS passed 中的 wizard 部分不減）。

若有測試斷言 CSS property，找到對應 test 檔更新斷言數值（不是把測試改成跳過）。

### Token 驗收

```bash
grep -n "var(--radius-card)\|var(--term-bg)\|var(--term-fg)\|var(--term-toolbar)" \
  docs/frontend-local-version-viewer/viewer/wizard.css
# 預期：空輸出（零命中）
```

### 布局驗收（目視）

啟動伺服器前先確認 editable install 正確：
```bash
pip show the-door | grep Editable
# 應指向當前 worktree，否則 pip install -e ./the_door
```

啟動：
```
the-door ui "C:\Users\Ric\Desktop\test-targets\the-door-v105" --no-browser --port 8765
```

開啟瀏覽器 http://localhost:8765/wizard.html，確認：
- [ ] 左 300px 深 teal rail + 右側白色內容區
- [ ] 右側內容欄 max-width 約 560px，兩側空白平均（不再偏左）
- [ ] 無舊式有框白卡（`.wizard-card` 不可見邊框）

## Done when

- [ ] Step 1–6 全部改完
- [ ] `grep var(--radius-card) wizard.css` 零命中
- [ ] JS wizard tests 通過
- [ ] 目視確認右側空白消失
- [ ] Browser console 快速驗證：`getComputedStyle(document.querySelector('.wizard-screen')).maxWidth === '560px'`（應回傳 `true`）
