# Wizard 更新分析流程（引導式 + 相似度分流）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 wizard 的「更新分析」從直跳確認頁，改成引導式分岔流程：A 重生現有版本解析 / B 引入新資料 → 結構比對指示 → 相似度判讀 → 當版本（出指令卡）或當新專案（導回首頁）。

**Architecture:** 純前端引導，零新 HTTP endpoint。所有「執行」步驟由 wizard 產生指令卡交給使用者的 agent 跑（agent-as-LLM）。新增狀態接進既有 `ui-wizard.js` 的 pure reducer（`transition`）與 `renderPage`，沿用既有 vitest 測試模式。唯一新增的後端互動是呼叫**既有**的 `GET /api/snapshots` 唯讀接口。

**Tech Stack:** Vanilla ES modules（`docs/frontend-local-version-viewer/viewer/js/ui-wizard.js`）、vitest、jsdom。

**Spec:** [`docs/superpowers/specs/2026-05-31-wizard-update-flow-guidance-design.md`](../../specs/2026-05-31-wizard-update-flow-guidance-design.md)

---

## 唯一正式版路徑（務必遵守）

- 前端唯一正式版：`docs/frontend-local-version-viewer/viewer/`
- ⛔ 不要動 `docs/frontend-local-version-viewer/prototype/`
- 所有改動集中在 `viewer/js/ui-wizard.js` + `viewer/tests/`

## 測試怎麼跑

`node_modules` 在主 repo 根的 `docs/frontend-local-version-viewer/viewer/`。在該目錄下用 vitest：

```bash
cd docs/frontend-local-version-viewer/viewer
./node_modules/.bin/vitest.cmd run --reporter=verbose 2>&1 | tail -30
```

若 worktree 無 `node_modules`，到主 repo 的 viewer 目錄跑（兩處檔案內容相同）。
**基準線：853 JS passed + 8 pre-existing failures（`graph.test.js`×5 + `ui-detail.test.js`×3，與本流程無關，不要修）。**

---

## 檔案地圖

| 檔案 | 責任 | 動到的 Task |
|---|---|---|
| `viewer/js/ui-wizard.js` | reducer `transition` + `renderPage` + `createApi` + 純 helper | 全部 |
| `viewer/tests/ui-wizard.test.js` | 既有 reducer/render 測試（含要改的舊斷言） | 01–06 |
| `viewer/tests/wizard-update-flow.test.js`（新建） | 本流程新狀態/頁面的測試 | 02–06 |
| `viewer/tests/wizard-phasebar.test.js` | 既有 rail 階段測試（要調整） | 06 |

## 新增的狀態 / 動作 / 頁面（跨 task 一致命名，請勿改名）

**新 state 欄位**（加進 `getInitialState`）：
- `updateFlow: null` — `'regen'` | `'new_data'`，標記更新分支
- `regenRef: null` — A 路選定要重生的版本識別字串
- `newDataPath: ''` — B 路新資料資料夾路徑
- `baselineRef: null` — B 路選定的比較基準識別字串
- `knownVersionIds: []` — 進 B 路前已知的 version_id 集合（偵測新版本用）
- `detectedRef: null` — 偵測頁確認到的新版本識別字串

**新 page 常數**（`state.page` 值）：
`PAGE_UPDATE_MODE` · `PAGE_REGEN_GUIDE` · `PAGE_NEW_DATA` · `PAGE_SIMILARITY_GUIDE` · `PAGE_SIMILARITY_DECISION` · `PAGE_VERSION_GUIDE` · `PAGE_VERSION_DETECT` · `PAGE_TRANSLATE_CHOICE`

**新 action type**：
`PICK_REGEN` · `SET_REGEN_REF` · `PICK_NEW_DATA` · `SET_NEW_DATA_PATH` · `SET_BASELINE` · `SET_KNOWN_VERSIONS` · `NEXT_FROM_NEW_DATA` · `NEXT_FROM_SIM_GUIDE` · `DECIDE_VERSION` · `DECIDE_NEWPROJECT` · `NEXT_FROM_VERSION_GUIDE` · `VERSION_DETECTED` · `DETECT_RESCAN` · `GOTO_TRANSLATE_CHOICE`

**新 helper / api**：
- `resolveSnapshotRef(snapshot)` — pure，`git_tags[0] → label → version_id`（**不可**用 `layers.js` 的 `_snapLabel`，它停在 `label→null`）
- `createApi().getSnapshots()` — `GET /api/snapshots`，回 `{ snapshots: [...] }`

---

## Task 清單（依內容分類）

| Task | 內容分類 | 依賴 |
|---|---|---|
| 01 | 純 helper + API client（無 UI） | 無 |
| 02 | 更新方式分岔頁 + reducer 改接（移除直跳確認） | 01 |
| 03 | A 路：重生指示頁 | 01, 02 |
| 04 | B 路：新資料路徑頁 + baseline 選擇 + 記下已知版本集合 | 01, 02 |
| 05 | B 路：結構比對指示頁 + 相似度判讀/決策頁 | 04 |
| 06 | B 路：建立新版本指示頁（snapshot_write）+ rail 階段 | 05 |
| 07 | B 路：偵測新版本頁（唯讀掃描） | 06 |
| 08 | B 路：翻譯與否分岔頁 → Viewer | 07 |

**Critical path：** 01 → 02 → 04 → 05 → 06 → 07 → 08。Task 03（A 路）只依賴 01+02，可與 04+ 並行。

## 完整流程（驗收時對照）

```
PAGE_ACTION ─更新分析→ PAGE_UPDATE_MODE
   ├─A→ PAGE_REGEN_GUIDE（出重生指令卡，終點）
   └─B→ PAGE_NEW_DATA → PAGE_SIMILARITY_GUIDE → PAGE_SIMILARITY_DECISION
            ├─當版本→ PAGE_VERSION_GUIDE（出 snapshot_write 指令）
            │           → PAGE_VERSION_DETECT（唯讀偵測新快照）
            │             → PAGE_TRANSLATE_CHOICE（翻譯指令 + 進 Viewer）→ /index.html
            └─當新專案→ 導回 /wizard.html 首頁的切換/首次分析流程
```
