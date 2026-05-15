# 任務文件目錄

## 文件整理規則

### 資料夾結構

```
viewer/
  REFACTOR-SPEC.md        ← 主索引：背景、TDD 全局規則、依賴圖、行數表、實作順序（含任務連結）
  tasks/
    README.md             ← 本文件：文件整理規則 + 任務清單
    00-infra.md           ← 步驟 0：測試基礎設施（package.json / vitest / setup）
    01-state-dom.md       ← 步驟 1：state.js + dom.js
    02-api-viewmodel.md   ← 步驟 2：api.js + viewmodel.js
    03-graph.md           ← 步驟 3：graph.js
    04-ui-topbar-list.md  ← 步驟 4：ui-topbar.js + ui-list.js
    05-ui-detail.md       ← 步驟 5：ui-detail.js
    06-ui-modal.md        ← 步驟 6：ui-modal.js
    07-ui-notes-diffexpl.md ← 步驟 7：ui-notes.js + ui-diff-explanation.js
    08-layers.md          ← 步驟 8：layers.js
    09-app-orchestrator.md ← 步驟 9：新 app.js（thin orchestrator）
    10-wiring-cleanup.md  ← 步驟 10–11：index.html 切換 + 舊檔刪除
  tests/
    setup.js              ← 全域 jsdom HTML fixture
    *.test.js             ← 各模組測試（命名與 js/ 對應）
  js/
    *.js                  ← ES modules（實作）
```

### 文件類型說明

| 類型 | 位置 | 用途 |
|---|---|---|
| **主索引** | `REFACTOR-SPEC.md` | 全局規則、依賴關係、任務清單，AI 每次對話優先讀此 |
| **任務文件** | `tasks/NN-*.md` | 每個步驟的完整規格，AI 執行特定步驟時只需讀對應任務文件 |
| **測試文件** | `tests/*.test.js` | Vitest 測試，每個模組一個檔案 |
| **實作模組** | `js/*.js` | ES module 實作，每個模組一個檔案 |

### 命名規則

- 任務文件：`NN-<slug>.md`，NN 為兩位數步驟編號，slug 為模組名縮寫
- 測試文件：`<module>.test.js`，與 `js/<module>.js` 名稱一一對應
- 實作模組：`<module>.js`，與 REFACTOR-SPEC.md 模組清單一致

### AI 讀文件的正確順序

1. 對話開始 → 讀 `REFACTOR-SPEC.md`（全局規則與任務清單）
2. 執行某步驟 → 只讀對應 `tasks/NN-*.md`，不需重讀整份 spec
3. 跨步驟參考 → 只讀需要的任務文件，不全部載入

---

## 任務清單

| 步驟 | 文件 | 涵蓋模組 | 狀態 |
|---|---|---|---|
| 0 | [00-infra.md](./00-infra.md) | 測試基礎設施 | ⬜ |
| 1 | [01-state-dom.md](./01-state-dom.md) | state.js, dom.js | ⬜ |
| 2 | [02-api-viewmodel.md](./02-api-viewmodel.md) | api.js, viewmodel.js | ⬜ |
| 3 | [03-graph.md](./03-graph.md) | graph.js | ⬜ |
| 4 | [04-ui-topbar-list.md](./04-ui-topbar-list.md) | ui-topbar.js, ui-list.js | ⬜ |
| 5 | [05-ui-detail.md](./05-ui-detail.md) | ui-detail.js | ⬜ |
| 6 | [06-ui-modal.md](./06-ui-modal.md) | ui-modal.js | ⬜ |
| 7 | [07-ui-notes-diffexpl.md](./07-ui-notes-diffexpl.md) | ui-notes.js, ui-diff-explanation.js | ⬜ |
| 8 | [08-layers.md](./08-layers.md) | layers.js | ⬜ |
| 9 | [09-app-orchestrator.md](./09-app-orchestrator.md) | js/app.js（新） | ⬜ |
| 10–11 | [10-wiring-cleanup.md](./10-wiring-cleanup.md) | index.html + 刪舊檔 | ⬜ |
