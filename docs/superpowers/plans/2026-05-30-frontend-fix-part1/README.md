# Frontend Fix Part 1 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修補 viewer 前端 5 個「樣式已存在但渲染端沒接上、或數值偏離既有慣例」的缺陷（FIX-1 P0 + FIX-2/3/4 P1 + FIX-5 P2），不引入新版面設計。

**Architecture:** 純前端修繕。三類動作：(1) JS renderer 補 className 對接既有 CSS（FIX-1/3/4/5）；(2) CSS 檔內 rem→px、border-radius 收斂為 6px（FIX-2）；(3) `.no-selection` → `.empty-state` 對接既有空狀態樣式（FIX-5）。不改 schema、不改狀態機、不改 `data-*` 屬性、不引入新 CSS 變數。

**Tech Stack:** vanilla ES modules + vitest（jsdom）+ v8 coverage（100% lines/functions/branches/statements threshold）+ 既有 CSS 變數系統。

---

## Spec source

[`C:\Users\Ric\Downloads\frontend-fix-spec-part1.md`](file:///C:/Users/Ric/Downloads/frontend-fix-spec-part1.md)（已修正幻覺後版本，2026-05-30）

## 任務檔

| # | 檔 | FIX | 受影響檔 | 預估改動 |
|---|---|---|---|---|
| 01 | `01-fix1-wizard-renderer.md` | FIX-1 (P0) | `js/ui-wizard.js` + `tests/ui-wizard.test.js` | renderer 全分支補 className，~50 行 source + ~15 條 test assertion |
| 02 | `02-fix2-wizard-css-tokens.md` | FIX-2 (P1) | `wizard.css` + 新增 `tests/wizard-css-units.test.js` | rem→px、radius 統一 6px，~30 行 css 替換 + 新 test 檔 |
| 03 | `03-fix3-next-actions-css.md` | FIX-3 (P1) | `js/ui-next-actions.js` + `styles.css` + `tests/ui-next-actions.test.js` | 1 行 className + 7 行新 CSS + 2 條 test |
| 04 | `04-fix4-onboarding-css.md` | FIX-4 (P1) | `js/onboarding.js` + `styles.css` + `tests/onboarding.test.js` | 1 行 className + 9 行新 CSS + 1 條 test |
| 05 | `05-fix5-doubt-empty-state.md` | FIX-5 (P2) | `js/ui-doubt.js` + `tests/ui-doubt.test.js` | 1 個 class 名替換 + 補齊 `renderDoubtDetail` 兩條分支測試（維持 100% coverage） |

## 執行順序

依 spec 附註建議：**01 → 02 → 03 → 04 → 05**。

- 01 與 02 同屬精靈，01 改 DOM、02 改數值；先 01 確保 DOM 帶 className 後，02 的 CSS 收斂才在實際被吃到的選擇器上生效。
- 03 與 04 都重用既有 `.not-analyzed-cmd`，可並行但仍建議序列以避免 styles.css merge 衝突。
- 05 純空狀態，與其他全部解耦，可任何時間做，放最後是為了集中精靈相關 PR 的視覺驗收。

## 共通設計決策（每個 task 都遵守）

1. **TDD 紀律**：每 task「失敗測試 → 最小實作 → 綠燈 → 提交」。
2. **100% coverage 是強制門檻**（`vitest.config.js` `thresholds: 100`）。每個 task 完成後跑 `npx vitest run --coverage` 必須全綠，違者該 task 未完成。
3. **不動 `data-*` 屬性**：所有變更只能「加 / 改 class」或「文字內容」。
4. **顏色／陰影用 token；字級／圓角用 px 字面量**（與 styles.css 主檔慣例對齊）。
5. **不引入新 CSS 變數**（`--fs-*` / `--radius-*` 系統屬 Part 2）。
6. **不改狀態機 / dispatch / 事件綁定邏輯**。
7. **提交粒度**：每 task 一個 commit（DOM 與測試同 commit）；commit 訊息格式 `fix(frontend): FIX-N <短描述>`。

## 環境準備（執行前一次性）

```bash
# 在 viewer 目錄下
cd docs/frontend-local-version-viewer/viewer
npm install      # 安裝 vitest + jsdom + happy-dom
npx vitest run   # 確認 baseline 全綠（pre-existing failures 若有，記錄基線數）
```

如 baseline 已有失敗測試（與本 plan 無關的 pre-existing），記下失敗清單做 regression baseline；本 plan 完成後該清單必須完全不變。

## 與其他 in-flight 工作的關係

- **Edge Noise Projection plan**（`docs/superpowers/plans/2026-05-29-edge-noise-projection/`）：純後端 + prompt 層，與本 plan 物理上零交集，可並行。
- **DEFER 段（疑義面板重做）**：刻意不在本 plan 範圍內。本 plan 的 FIX-5 只動空狀態文案那一行，**不重繪面板**。

## 完成定義

- 5 個 task 都通過各自的 acceptance criteria。
- `npx vitest run --coverage` 全綠，coverage 4 項全 100%。
- pre-existing failures（若有）的清單與基線一致，無新失敗。
- `wizard.css` 內 `grep -E "[0-9]rem|border-radius:\s*(5|8|12)px"` 零命中。
- 對 `wizard.css` 每個 class 選擇器手動 grep `ui-wizard.js`，皆有命中。
- 手動 smoke：`the-door ui <test-target>` 啟動，wizard.html 各頁無瀏覽器預設灰按鈕；空專案 index.html 顯示 onboarding 卡。
