# Stream A — 多語言 L1 抽取 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修復 `node_builder._walk_generic` 對 8 種語言（Rust/Java/Ruby/Go/PHP/C#/C/C++）抽取近乎失效的問題，改為 config-driven 設計。

**Architecture:** 本 Task 文件本身**不重複**`multilang-node-extraction/spec.md` 的設計內容（避免重複施作）。執行模式是「把既有 spec 透過 `superpowers:writing-plans` 轉成可執行 plan 後再實作」。

**Tech Stack:** Python, tree-sitter（既有）, hypothesis（property test，既有專案已用）

**Spec reference:**
- 本流 spec：`<peaceful-bell-8b569a worktree>/.kiro/specs/multilang-node-extraction/spec.md`（未 commit）
- 整合 roadmap：`consolidated-roadmap-2026-05-23/spec.md` § 2

---

### Task 1: 切換到正確的 worktree 並驗證 spec 仍在

**Files:**
- Read: `<peaceful-bell-8b569a>/.kiro/specs/multilang-node-extraction/spec.md`

- [ ] **Step 1: 列出所有 worktree 確認路徑**

```bash
git worktree list
```
Expected: 看到 `claude/peaceful-bell-8b569a` 對應路徑。

- [ ] **Step 2: 在該 worktree 內操作的兩種方式**

選一即可：

**方式 A — 讀檔／看內容**：用絕對路徑透過 Read／Grep tool 直接讀，不需切換 cwd
```
Read("<peaceful-bell-8b569a 絕對路徑>/.kiro/specs/multilang-node-extraction/spec.md")
```

**方式 B — 跑命令（git／pytest）**：在 Bash command 內 inline `cd`，或用 `git -C`
```bash
cd "<peaceful-bell-8b569a 絕對路徑>" && git status
# 或
git -C "<peaceful-bell-8b569a 絕對路徑>" status
```

避免：**不要**在 session 中執行單獨的 `cd` 改變後續命令的 cwd（會讓後續命令不可預期）。

- [ ] **Step 3: 確認 spec 仍在且未 commit**

```bash
ls "<peaceful-bell-8b569a>/.kiro/specs/multilang-node-extraction/spec.md"
cd "<peaceful-bell-8b569a>" && git status --short -- .kiro/specs/multilang-node-extraction/
```
Expected: spec.md 存在；`git status` 顯示為 untracked（??）。

- [ ] **Step 4: 若 spec 不見了**

從 memory 找：`~/.claude/projects/.../memory/handoff_2026_05_22.md` 內第 3 節「產出物：spec」記錄了內容大綱。但這只是 fallback——正常情況 spec 應該還在。

---

### Task 2: 把 spec commit 進 worktree 鎖定基準

**Files:**
- Stage: `<peaceful-bell-8b569a>/.kiro/specs/multilang-node-extraction/spec.md`

- [ ] **Step 1: 在 worktree 內 commit spec**

```bash
git add .kiro/specs/multilang-node-extraction/spec.md
git commit -m "spec: multilang L1 node extraction (codegraph-derived config table)"
```

- [ ] **Step 2: 驗證 commit**

```bash
git log -1 --stat
```
Expected: 只有一個新檔 `spec.md`。

理由：spec 不 commit 就走 writing-plans 風險高（spec 改動的話 plan 會錯位）。先鎖定。

---

### Task 3: 用 writing-plans skill 把 spec 轉成可執行 plan

**Files:**
- Create: `<peaceful-bell-8b569a>/docs/superpowers/plans/2026-05-23-multilang-node-extraction.md`
  - （或使用者偏好路徑：`<peaceful-bell-8b569a>/.kiro/specs/multilang-node-extraction/tasks/*.md`）

- [ ] **Step 1: 在 worktree 內啟動 writing-plans**

在 Claude Code 中執行：
```
/superpowers:writing-plans
```
然後 prompt：「依 `.kiro/specs/multilang-node-extraction/spec.md` 寫實作 plan，遵守 spec 第 7 節的 TDD 要求（先寫 failing Rust impl_item test 再修）」

- [ ] **Step 2: writing-plans 產出後檢視**

```bash
ls -la docs/superpowers/plans/ .kiro/specs/multilang-node-extraction/tasks/ 2>&1
```
Expected: 看到產出檔。

- [ ] **Step 3: 對 plan 跑 code-review**

```
/code-review
```
針對 plan 跑 7 criteria（邏輯 bug / 幻覺 / 過度設計 / 資源浪費 / clean code / 最小架構異動 / TDD），找到問題就 in-place 修。

- [ ] **Step 4: Commit plan**

```bash
git add docs/superpowers/plans/2026-05-23-multilang-node-extraction.md
git commit -m "plan: multilang node extraction implementation"
```

---

### Task 4: 用 subagent-driven-development 執行 plan

**Files:**
- Will create: `the_door/src/the_door/core/extraction/language_configs.py`
- Will modify: `the_door/src/the_door/core/extraction/node_builder.py`（line 369 起的 `_walk_generic`）
- Will add: fixtures + tests 在 `the_door/tests/` 既有結構下

- [ ] **Step 1: 啟動 subagent-driven 執行**

```
/superpowers:subagent-driven-development
```
傳入 plan 路徑，由 dispatcher 逐 task 派 subagent 實作 + 兩階段 review。

- [ ] **Step 2: 監督執行 — 不要打斷**

依專案連跑協定（[[feedback_continuous_run_protocol]]）若使用者明示 token 充足則一次跑完所有 sub-task；否則分階段確認。

- [ ] **Step 3: 全部跑完後驗證**

```bash
cd the_door && pytest -x --tb=short
```
Expected: 既有 test 全綠不退化 + 新增的 multilang fixture test 全綠。

- [ ] **Step 4: 確認既有 python/typescript/javascript 行為不變**

```bash
pytest the_door/tests/extraction/ -k "python or typescript or javascript" -v
```
Expected: 全綠（spec § 5.4 要求位元級不變）。

---

### Task 5: Merge 回 main

**Files:**
- Target: `main` branch

- [ ] **Step 1: 確認 worktree HEAD**

```bash
git log --oneline -10
```
Expected: 看到 spec commit + 多個 implementation commit。

- [ ] **Step 2: Fast-forward merge 或開 PR**

依專案習慣（之前 multi-feature 工作多走 ff-merge）：

```bash
git checkout main
git merge --ff-only claude/peaceful-bell-8b569a
```

若 main 已前進（不能 ff），改 rebase：

```bash
git checkout claude/peaceful-bell-8b569a
git rebase origin/main
# 解衝突
git checkout main && git merge --ff-only claude/peaceful-bell-8b569a
```

- [ ] **Step 3: Push**

```bash
git push origin main
```

- [ ] **Step 4: 刪除 worktree**

```bash
git worktree remove <peaceful-bell-8b569a path>
```

---

## Acceptance

- [ ] Rust 含 `impl` 區塊方法的 fixture 抽到 function（先寫 failing test 再修）
- [ ] Java / Ruby / Go / PHP / C# / C / C++ 各一份小 fixture 抽出至少一個 function 與一個 class
- [ ] python / typescript / javascript 既有 test 全綠不變
- [ ] `language_configs.py` 是 pure data（無 I/O、無副作用）
- [ ] Plan + 實作都 merge 進 main
