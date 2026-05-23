# Stream C — Diff 詳情面板重做（決策檢核點 + 條件性任務）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to track this task. Steps use checkbox (`- [ ]`) syntax for tracking. **This file starts as a decision checkpoint, not a full task list.** The full task list only materializes after Stream B's plan is written.

**Goal:** 決定 worktree `ecstatic-beaver-49806e` 內既有的 diff 詳情面板 3-task plan 是：(a) 已被 Stream B 涵蓋，可整段移除；(b) 仍需獨立執行；(c) 部分併入 B、剩下獨立。

**Architecture:** 本流唯一動作位於 `the_door/src/the_door/core/ui/api_handlers.py`（後端 `/api/diff` 加 `node_details`）+ `viewer/js/ui-detail.js`（重寫 `renderStructuralDiffDetail`）+ `viewer/styles.css`（詳情欄加寬）。但因 Stream B 全面重寫 `ui-detail.js`，前端兩個 task 大概率被涵蓋。

**Tech Stack:** Python（後端）, vanilla JS / CSS（前端）

**Spec reference:**
- `consolidated-roadmap-2026-05-23/spec.md` § 4
- 既有 spec/plan：`<ecstatic-beaver-49806e>/.kiro/specs/frontend-local-version-viewer/{design.md,tasks.md}`

**Prereq:**
- `02-prereq-stoic-spence-land.md` 完成
- `03-stream-b-design-system.md` 的 Task 1–12 至少寫完 plan（不一定要實作完）

---

### Task 1: 取得 ecstatic-beaver 的既有 spec 與 plan 副本

**Files:**
- Read-only: `<ecstatic-beaver-49806e>/.kiro/specs/frontend-local-version-viewer/design.md`
- Read-only: `<ecstatic-beaver-49806e>/.kiro/specs/frontend-local-version-viewer/tasks.md`

- [ ] **Step 1: 列出 ecstatic-beaver worktree**

```bash
git worktree list | grep ecstatic-beaver
```
Expected: 看到路徑與 branch `claude/ecstatic-beaver-49806e`。

- [ ] **Step 2: 把 design + tasks 文件用 Read 工具讀進來**

不要 `cp` 出來——直接從 worktree 路徑 Read，避免兩份副本失同步。

- [ ] **Step 3: 標記三個 task 的具體內容**

依 handoff_2026_05_20_b 記錄：
- Task 1 (backend)：`/api/diff` response 加 `node_details` 欄位
- Task 2 (frontend)：重寫 `renderStructuralDiffDetail`
- Task 3 (CSS)：詳情欄加寬

實際讀 tasks.md 確認每個 task 的具體驗收條件與檔案範圍。

---

### Task 2: 比對 Stream B 已涵蓋多少

**Files:**
- Read-only: `03-stream-b-design-system.md`（同目錄）

- [ ] **Step 1: 對 Stream B 的 Task 8（§ 7 detail panel）逐條核對 ecstatic-beaver Task 2 的子項**

寫一張對照表：

| ecstatic-beaver Task 2 sub-item | Stream B Task 8 step | 是否涵蓋 |
|---|---|---|
| ... | ... | ✅ / ❌ / 部分 |

- [ ] **Step 2: 對 Stream B Task 6/Task 8 的 CSS 改動核對 ecstatic-beaver Task 3（欄寬）**

Stream B 動 `styles.css` 多次，但**沒有**明確列出「詳情欄加寬」。此項 → ❌ 未涵蓋。

- [ ] **Step 3: Stream B 完全沒做後端 Task 1**

Stream B 是純前端流，後端 `/api/diff` 加 `node_details` 不在範圍 → ❌ 未涵蓋。

---

### Task 3: 三選一決策

依 Task 2 對照表結果三選一：

- [ ] **Branch A — 全部移除**：所有 task 都被 B 涵蓋。
  - 動作：把 ecstatic-beaver 的 design.md/tasks.md 內 diff 詳情面板章節刪除（git revert 或編輯）+ commit + close 任何相關 PR
  - 此 branch 機率最低（因為後端 Task 1 必然未涵蓋）

- [ ] **Branch B — 全部獨立執行**：B 沒涵蓋任何東西（前端設計完全不衝突）。
  - 動作：照 ecstatic-beaver tasks.md 跑完 3 個 task
  - 此 branch 機率也低（B 大幅改 ui-detail.js）

- [ ] **Branch C — 部分併入、部分獨立**（最可能）：
  - Task 1（後端 `node_details`）→ 仍要做（B 沒碰後端）
  - Task 2（前端 `renderStructuralDiffDetail`）→ 整段刪除，已被 B Task 8 涵蓋
  - Task 3（詳情欄加寬）→ 仍要做（B 沒明確列），但可以 inline 進 B Task 13 cleanup 階段

→ **預期會進 Branch C**。下面 Task 4 / 5 假設走 Branch C。

---

### Task 4 (Branch C only): 後端 `node_details` 實作

**Files:**
- Modify: `the_door/src/the_door/core/ui/api_handlers.py`
- Test: `the_door/tests/ui/test_api_handlers.py`（依專案結構，名稱可能不同）

- [ ] **Step 1: 找到 `/api/diff` handler 入口**

```bash
grep -n "/api/diff\|node_details" the_door/src/the_door/core/ui/api_handlers.py the_door/src/the_door/core/ui/server.py
```

- [ ] **Step 2: 從 ecstatic-beaver design.md 抄 `node_details` 結構**

依 design.md 內定義的 schema 寫；不要自己重新設計。

- [ ] **Step 3: 寫 failing test（TDD）**

針對 `/api/diff` response shape 寫 contract test：給定固定 snapshot pair → assert `node_details` 存在、結構符合。

- [ ] **Step 4: Fail → 實作 → Pass**

```bash
pytest the_door/tests/ -k "node_details" -x
```

- [ ] **Step 5: Commit**

```bash
git add the_door/src/the_door/core/ui/api_handlers.py the_door/tests/...
git commit -m "api(diff): include node_details payload per spec"
```

---

### Task 5 (Branch C only): 詳情欄加寬

**Files:**
- Modify: `docs/frontend-local-version-viewer/viewer/styles.css`

- [ ] **Step 1: 查既有欄寬**

```bash
grep -n "grid-template-columns\|detail-panel\|minmax(300" docs/frontend-local-version-viewer/viewer/styles.css
```

- [ ] **Step 2: 依 ecstatic-beaver Task 3 改寬**

把 `.workspace` `grid-template-columns` 的 `minmax(300px, 380px)` 改為 ecstatic-beaver Task 3 指定的新寬度（讀 tasks.md 取數）。

- [ ] **Step 3: Visual verify**

開 viewer 看 detail panel 是否寬到不會 wrap 過頭、Source nodes 等 mono 區段不再溢出。

- [ ] **Step 4: Commit**

```bash
git add docs/frontend-local-version-viewer/viewer/styles.css
git commit -m "viewer(detail): widen detail panel column per spec"
```

---

### Task 6: Cleanup — ecstatic-beaver worktree 處置

- [ ] **Step 1: 確認 Branch C 完成後 ecstatic-beaver 內 spec 已過時**

ecstatic-beaver 的 tasks.md Task 2 已被刪除（Branch C 決策），Task 1 / Task 3 已在 main 完成。

- [ ] **Step 2: 在 ecstatic-beaver 內 update spec**

把 tasks.md / design.md 內已落地的章節標 ✅ 並 commit。

- [ ] **Step 3: Merge 或關閉 ecstatic-beaver branch**

```bash
git push origin claude/ecstatic-beaver-49806e
gh pr create --base main --head claude/ecstatic-beaver-49806e --title "spec: mark diff detail panel tasks as landed"
```

或直接 ff-merge spec 更新 + 移除 worktree（依專案 release 習慣）。

---

## Acceptance

- [ ] 決策（Branch A/B/C）有書面紀錄
- [ ] Branch C 路徑下：後端 `node_details` ✅、前端 `renderStructuralDiffDetail` 由 B Task 8 涵蓋 ✅、欄寬調整 ✅
- [ ] ecstatic-beaver worktree 與 spec 同步、無懸而未決的 task
