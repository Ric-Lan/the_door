# Prereq — Land stoic-spence-860a5b onto main

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to track this task. Steps use checkbox (`- [ ]`) syntax for tracking. **This is NOT a feature task — it's an operational prerequisite that must complete before Stream B and Stream C can start.**

**Goal:** 把 worktree `stoic-spence-860a5b` 內未 commit 的 viewer 修正（CLAUDE.md / app.js / ui-detail.js / ui-list.js）以及 2 個 ahead commit 落地到 main，解掉與 `origin/main` 的 4-commit divergence。

**Architecture:** 純 git 操作；不寫程式碼。但因為衝突檔（`ui-detail.js`、`ui-list.js`）正是 Stream B 要重寫的兩支檔，**必須在啟動 Stream B / C 之前完成**，否則會在過期分支上做白工。

**Tech Stack:** git

**Spec reference:** `consolidated-roadmap-2026-05-23/spec.md` § 4.2 + § 6.2 step 3

---

### Task 1: Audit 未 commit 改動

**Files:**
- Read-only: `<stoic-spence-860a5b>/CLAUDE.md`、`js/app.js`、`js/ui-detail.js`、`js/ui-list.js`

- [ ] **Step 1: 確認 worktree HEAD 與 origin/main 的 divergence**

```bash
cd "<stoic-spence-860a5b>"
git fetch origin
git status
git log --oneline origin/main..HEAD
git log --oneline HEAD..origin/main
```
Expected:
- 確認 HEAD ahead 2 commit、behind 4 commit
- 看到 ahead 的 2 個 commit 訊息（驗證是真實工作）

- [ ] **Step 2: 看未 commit 改動的具體 diff**

```bash
git diff -- CLAUDE.md
git diff -- docs/frontend-local-version-viewer/viewer/js/app.js
git diff -- docs/frontend-local-version-viewer/viewer/js/ui-detail.js
git diff -- docs/frontend-local-version-viewer/viewer/js/ui-list.js
```

審視每處改動：
- 是否仍與當前 main 設計方向一致？
- 是否與 Stream B 預計的 § 7 detail panel 改動衝突或重複？

- [ ] **Step 3: 把判斷紀錄寫入 commit message draft（之後 Task 3 用）**

開一個臨時 markdown 檔記錄：哪些 hunk 要保留、哪些要捨棄、為什麼。如果 100% 保留就跳過寫紀錄。

---

### Task 2: Stage + commit 未 commit 改動

**Files:**
- Stage: 4 個改動檔
- 不要 stage: `_rewrite_snapshots.py`（untracked，看內容判斷）、`node_modules/`（gitignored）、`docs/superpowers/plans/2026-05-19-llm-natural-language-prompt-enforcement.md`（untracked，看 [[handoff_2026_05_20_b]] 知這是已過時的 plan）

- [ ] **Step 1: 決定 untracked 檔的處置**

```bash
git status --short
```

對每個 untracked file 決策：
- `_rewrite_snapshots.py` → 看內容；若是一次性腳本 → 不 commit（留檔或刪）
- `docs/superpowers/plans/2026-05-19-...` → 已過時（per handoff），不 commit
- `node_modules/` → 確認已在 .gitignore，不 commit

- [ ] **Step 2: Stage 要保留的改動**

```bash
git add CLAUDE.md docs/frontend-local-version-viewer/viewer/js/app.js
git add docs/frontend-local-version-viewer/viewer/js/ui-detail.js
git add docs/frontend-local-version-viewer/viewer/js/ui-list.js
```

如果某 hunk 要捨棄，用 `git restore -- <file>` 先還原該檔再 patch-add：
```bash
git restore -- docs/frontend-local-version-viewer/viewer/js/ui-detail.js
git add -p docs/frontend-local-version-viewer/viewer/js/ui-detail.js
```

- [ ] **Step 3: Commit**

```bash
git commit -m "viewer: #3 修正（內容依 Task 1 audit 摘要填入）"
```

訊息要具體寫出修了什麼 UX 問題，方便日後 git blame 追溯。

---

### Task 3: Rebase 到最新 origin/main

**Files:**
- Branch: `claude/stoic-spence-860a5b`

- [ ] **Step 1: 確認當前 main HEAD**

```bash
git log origin/main --oneline -5
```
Expected: 看到包含 `v1.2.1` tag 的 commit `0b353df` 或更新。

- [ ] **Step 2: Rebase**

```bash
git rebase origin/main
```

若無衝突 → 直接成功。  
若有衝突 → 依下方 Step 3 處理。

- [ ] **Step 3: 解衝突**

對每個衝突檔：
1. `git status` 看哪些檔卡住
2. 編輯衝突檔，保留正確版本
3. `git add <file>`
4. `git rebase --continue`

衝突最可能發生在 `js/ui-detail.js` / `js/ui-list.js` / `CLAUDE.md`（因為 main 上的 4 個 behind commit 可能也動過這些檔）。處理原則：**保留 main 上的最新行為 + 套用本分支的 UX 修正**，必要時手工合併。

- [ ] **Step 4: 驗證 rebase 後 test 仍綠**

```bash
cd docs/frontend-local-version-viewer/viewer
npx vitest run
```
Expected: 全綠。若有 fail，rebase 過程中保留了壞東西，要回去重做。

- [ ] **Step 5: 後端 test 也要綠**

```bash
cd <repo root>
pytest -x --tb=short
```
Expected: 全綠。

---

### Task 4: Push + 開 PR

**Files:**
- Remote: `origin`

- [ ] **Step 1: Force push（rebase 後必須 force）**

```bash
git push --force-with-lease origin claude/stoic-spence-860a5b
```

`--force-with-lease` 比 `--force` 安全：若遠端有別人新 push 會擋。

- [ ] **Step 2: 開 PR**

```bash
gh pr create --base main --head claude/stoic-spence-860a5b \
  --title "viewer: 3 個 UX 修正" \
  --body "$(cat <<'EOF'
## Summary
- 修正 viewer #3 系列 UX 問題（具體列表依 Task 2 commit 訊息）
- 為 Stream B（設計系統套用）與 Stream C（diff 詳情面板）的前置

## Test plan
- [x] viewer vitest 全綠
- [x] backend pytest 全綠
- [ ] PR review 後 ff-merge
EOF
)"
```

- [ ] **Step 3: 等 PR review**

不要繞過 review 直接 merge。

---

### Task 5: Merge 後 cleanup

**Files:**
- Local: 移除 worktree

- [ ] **Step 1: Merge 後 fetch main**

```bash
git fetch origin
git checkout main
git pull --ff-only
```

- [ ] **Step 2: 移除 worktree（branch 已 merged）**

```bash
cd <repo root>
git worktree remove <stoic-spence-860a5b path>
git branch -d claude/stoic-spence-860a5b
```

- [ ] **Step 3: 通知 Stream B / C 可以啟動**

更新 `consolidated-roadmap-2026-05-23/spec.md` 把 § 1 表的 B/C 行的「前置：stoic-spence #3 落地 main」標 ✅，commit 一次。

---

## Acceptance

- [ ] `origin/main` 包含 stoic-spence 內所有要保留的改動
- [ ] viewer vitest + backend pytest 在 main 上全綠
- [ ] worktree 已刪、branch 已 prune
- [ ] consolidated-roadmap-2026-05-23/spec.md § 1 表更新標 ✅
