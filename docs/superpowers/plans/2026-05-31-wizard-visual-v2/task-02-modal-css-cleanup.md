# Task 02 — Modal 進度一致化確認（8.6 A 狀態核查）

## 目標

確認開放問題 8.6（spec §5.5）的 (A) 一致化方案是否已由 Part 2 Task 8 完成。
**本 task 優先是確認，不是執行**。若已完成則標記 Done 即可。

## 設計來源

- **spec §5.5**：`frontend-onboarding-flow-spec-part2 (1).md`
- **Part 2 Task 8**：commit `cd7afab` — modal 改用 `progress-view.js` 共用模組
- **`viewer/js/ui-modal.js:35–51`**：`renderPipelineProgress` 現況

## 前置核查（執行前先做）

### 核查 A — `ui-modal.js` 是否已使用 `renderProgressInnerHTML`

```bash
grep -n "renderProgressInnerHTML" docs/frontend-local-version-viewer/viewer/js/ui-modal.js
```

**預期**：第 43 行附近有 1 筆命中。
- 有 → 邏輯層已一致，繼續核查 B。
- 零命中 → Task 8 沒有正確 merge，**停止**，先查 git log 確認原因。

### 核查 B — `styles.css` 是否有舊 chip CSS 待清理

```bash
grep -n "steps-list\|step-item\|step-completed\|step-failed\|step-skipped\|step-error" \
  docs/frontend-local-version-viewer/viewer/styles.css
```

**預期**：零命中（已核對，舊 chip CSS 不在 styles.css 中）。
- 零命中 → CSS 層面乾淨，繼續核查 C。
- 有命中 → 執行下方「清理步驟」。

### 核查 C — `index.html` 的 `#steps-list` 結構

```bash
grep -n "steps-list\|pipeline-progress" \
  docs/frontend-local-version-viewer/viewer/index.html
```

**預期**：`index.html:84` 有 `<ul id="steps-list" class="steps-list"></ul>`。

> **說明**：`renderPipelineProgress` 用 `stepsListEl.replaceWith(newDiv)` 把這個 `<ul>` 整個
> 換成 `<div id="steps-list">`，再填入 `renderProgressInnerHTML` 產出的 HTML。
> 因此 `class="steps-list"` 在 HTML 初始值中存在但不影響運行（頁面載入後立即被替換）。
> 這個行為是正確的，不需要改 `index.html`。

## 清理步驟（僅在核查 B 有命中時執行）

若 `styles.css` 仍有舊 chip class 定義：

1. 先確認這些 class 未被任何 `.js` 或 `.html` 引用：
   ```bash
   grep -rn "step-item\|step-completed\|step-failed\|step-skipped\|step-error" \
     docs/frontend-local-version-viewer/viewer/
   # 預期：僅在 styles.css 出現，不在 .js/.html 出現
   ```

2. 確認後從 `styles.css` 移除這些 class 的定義。

3. 執行測試：
   ```bash
   cd docs/frontend-local-version-viewer/viewer
   npx jest --testPathPattern="modal|progress" 2>&1 | tail -10
   ```

## Done when

- [ ] 核查 A：`renderProgressInnerHTML` 在 `ui-modal.js` 有命中
- [ ] 核查 B：`styles.css` 舊 chip CSS 零命中（或已清除）
- [ ] 核查 C：`index.html` 結構符合預期（`#steps-list` 存在，由 `replaceWith` 管理）
- [ ] JS tests 通過（若有執行清理步驟）

> **預期結果**：三項核查全部通過後，本 task 標記 Done，**不需要額外代碼改動**。
