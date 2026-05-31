# Wizard Visual v2 — Plan

Wizard 視覺第二輪修正。第一輪 port（v1.5.1 commit `5d9125f`）已補上 icon library、
eyebrow、lede、opt icon-cards、switch-zone，但布局仍不正確。本 plan 修正根本原因。

## 設計真實來源（按優先順序）

1. `docs/frontend-local-version-viewer/viewer/styles.css` — **最高優先**
2. `docs/frontend-local-version-viewer/part2-prototype/flow.css` — 視覺參考
3. `C:\Users\Ric\Downloads\frontend-onboarding-flow-spec-part2 (1).md` — **本 plan 的 spec**（含 §1.5 版型數值）
4. `C:\Users\Ric\Downloads\品牌視覺指南 (AI Agent版) (1).md` — 合規驗收層

> 「spec」下面提到的數值均來自上述 (3)，已在 Think Tank 分析中確認。

## 根本原因（已核對原始碼）

右側空白太多的根本原因是 `wizard.css:394–405`：
- `.wizard-content` 缺 `align-items:center`，且用了 `position:relative; overflow:hidden`
  導致內層 `.wizard-screen` 採 `position:absolute; inset:0`，內容撐滿整個 content 區寬
- `.wizard-screen` 沒有 `max-width:560px` cap，內容散開

修法見 Task 01。

## Task 列表

| Task | 檔案 | 說明 | 依賴 |
|---|---|---|---|
| [01](task-01-css-layout-fix.md) | `wizard.css` | CSS 布局根本修正 + token 清理 | 無 |
| [02](task-02-modal-css-cleanup.md) | `styles.css` | 8.6 modal 一致化：清除舊 chip CSS | 無（可並行） |

## 不在本 plan 範圍

- 後端 `progress` 欄位補充（8.1 決定：誠實降級，不做 feed）
- Faux browser chrome（8.3 決定：否）
- 穿門轉場（8.2 決定：A 方案，已有 `wizardThresholdOut` + `viewerIn`，現況已實作完畢）
- `wizard.html` shell 結構（§2 要求已在 v1.5.1 實作）

## 驗收（全部 task 完成後）

```
[ ] 精靈右欄有 max-width 560px 內容欄，兩側空白平均
[ ] 精靈右欄無右側大空白（主要視覺 bug 消失）
[ ] wizard.css 內無任何 var(--radius-card) 使用（grep 驗證）
[ ] wizard.css 內無任何 var(--term-bg) / var(--term-fg) / var(--term-toolbar) 使用
[ ] JS 測試全綠（853 passed，8 pre-existing failures 不動）
```
