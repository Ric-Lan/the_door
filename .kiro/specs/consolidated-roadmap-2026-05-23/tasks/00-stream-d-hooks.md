# Stream D — CLAUDE.md → Hooks 補強 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 CLAUDE.md 內最易被忽略的 3 條規則改用 Claude Code hook 強制執行，避免長對話中漏讀。

**Architecture:** 使用 harness 既有的 hook system（`.claude/settings.json` 的 `hooks` 區塊）；不引入新 dependency。3 條 hook：① `PreToolUse` 阻擋寫入 `prototype/`、② `UserPromptSubmit` 注入 2 行短警告、③ `PreToolUse` 偵測 `the-door serve` 提示改 `ui`。

**Tech Stack:** JSON settings, bash one-liners（hook command 走 jq + grep）

**Spec reference:** `consolidated-roadmap-2026-05-23/spec.md` § 5

---

## ⚠️ Merge semantics（所有 Task 共用）

3 個 hook 都寫入**同一個** `.claude/settings.json`。每個 Task 都必須在不破壞前一個 Task 成果的前提下追加。

**全部完成後的最終 settings.json 結構**（給 reference，不要一次貼進去——逐 Task 用 `jq` 追加）：

```json
{
  "hooks": {
    "PreToolUse": [
      { "matcher": "Edit|Write|NotebookEdit", "hooks": [{ "type": "command", "command": "<prototype guard>" }] },
      { "matcher": "Bash",                    "hooks": [{ "type": "command", "command": "<serve guard>" }] }
    ],
    "UserPromptSubmit": [
      { "hooks": [{ "type": "command", "command": "<inject reminder>" }] }
    ]
  }
}
```

**操作守則**：
1. 每個 Task 結尾用 `jq` 顯示完整 settings.json 確認
2. 不要直接覆寫 settings.json 的整個 `hooks` 物件——用 `jq` 的 `+=`（陣列）或物件 merge
3. 若手動編輯（非 jq），編輯前先 `cat .claude/settings.json` 看當前狀態，編輯後再 `cat` 比對

---

### Task 1: 選擇 settings 目標檔

**Files:**
- Read: `.claude/settings.json`（repo 共享）
- Read: `.claude/settings.local.json`（個人，gitignored）

- [ ] **Step 1: 檢視兩個 settings 檔現況**

Run:
```
ls -la .claude/settings.json .claude/settings.local.json 2>&1
```
Expected: 至少一個存在；不存在的會 `No such file`。

- [ ] **Step 2: 決策**

預設用 **`.claude/settings.json`**（repo 共享，所有 collaborator 都受保護）。例外：若使用者明示 "只給我個人用"，改 `.claude/settings.local.json`。

→ 後續所有 Task 都寫入 `.claude/settings.json`，除非使用者另指定。

- [ ] **Step 3: 若 settings.json 不存在，建立空殼**

```bash
[ -f .claude/settings.json ] || echo '{}' > .claude/settings.json
```

---

### Task 2: PreToolUse hook — 阻擋寫入 prototype/

**Files:**
- Modify: `.claude/settings.json`

- [ ] **Step 1: 確認 prototype/ 路徑存在且確實已廢棄**

Run:
```
ls docs/frontend-local-version-viewer/prototype 2>&1 | head -3
```
Expected: 目錄存在（廢棄但檔還在）。確認後才有保護的必要。

- [ ] **Step 2: 用 jq merge 到既有 settings.json**

```bash
jq '.hooks.PreToolUse = ((.hooks.PreToolUse // []) + [{
  matcher: "Edit|Write|NotebookEdit",
  hooks: [{
    type: "command",
    command: "jq -r \".tool_input.file_path // empty\" | grep -q \"frontend-local-version-viewer/prototype/\" && { echo \"⛔ prototype/ 已廢棄，請改寫 docs/frontend-local-version-viewer/viewer/\" >&2; exit 2; } || exit 0"
  }]
}])' .claude/settings.json > .claude/settings.json.tmp && mv .claude/settings.json.tmp .claude/settings.json
```

`(.hooks.PreToolUse // [])` 保證即使原本沒有 PreToolUse 也不會炸；`+` 是陣列追加不是覆寫。

- [ ] **Step 3: 驗證 hook 觸發**

在 Claude Code 內嘗試對 prototype/ 內任一檔做 Edit，預期 hook 攔下並顯示警告，工具呼叫 abort。

- [ ] **Step 4: 驗證對 viewer/ 不誤觸**

對 `docs/frontend-local-version-viewer/viewer/styles.css` 做 trivial Edit，預期通過。

- [ ] **Step 5: Commit**

```bash
git add .claude/settings.json
git commit -m "hook: block writes to deprecated prototype/ folder"
```

---

### Task 3: UserPromptSubmit hook — 注入 2 行短警告

**Files:**
- Modify: `.claude/settings.json`

- [ ] **Step 1: 用 jq merge UserPromptSubmit hook**

```bash
jq '.hooks.UserPromptSubmit = ((.hooks.UserPromptSubmit // []) + [{
  hooks: [{
    type: "command",
    command: "echo \"⚠ The Door: 前端唯一正式版 = docs/frontend-local-version-viewer/viewer/（不要動 prototype/）；啟動本地伺服器指令是 the-door ui <test-target>，不是 serve。\""
  }]
}])' .claude/settings.json > .claude/settings.json.tmp && mv .claude/settings.json.tmp .claude/settings.json
```

不會動到 Task 2 寫入的 `PreToolUse`。

- [ ] **Step 2: 驗證注入**

開新對話，第一句後檢視 system reminder 區應出現上述 2 行警告。

- [ ] **Step 3: Commit**

```bash
git add .claude/settings.json
git commit -m "hook: inject The Door critical reminders on each prompt"
```

---

### Task 4: PreToolUse hook — 偵測 `the-door serve` 誤用

**Files:**
- Modify: `.claude/settings.json`

- [ ] **Step 1: 用 jq 追加 Bash matcher hook（同 PreToolUse 陣列）**

```bash
jq '.hooks.PreToolUse += [{
  matcher: "Bash",
  hooks: [{
    type: "command",
    command: "jq -r \".tool_input.command // empty\" | grep -qE \"the-door\\\\s+serve\\\\b\" && { echo \"⛔ 指令是 the-door ui <test-target>，不是 serve。請改用 ui 子命令。\" >&2; exit 2; } || exit 0"
  }]
}]' .claude/settings.json > .claude/settings.json.tmp && mv .claude/settings.json.tmp .claude/settings.json
```

⚠️ 用 `+=` 追加到既有 `PreToolUse` 陣列尾端（Task 2 的 Edit/Write/NotebookEdit hook 仍保留）。

- [ ] **Step 1.5: 確認最終結構**

```bash
jq '.hooks | keys, .PreToolUse | length' .claude/settings.json
```
Expected: `["PreToolUse","UserPromptSubmit"]` 然後 `2`（PreToolUse 陣列有兩個物件：Edit/Write hook + Bash hook）。

- [ ] **Step 2: 驗證攔截 serve**

在 Claude Code 內嘗試 Bash `the-door serve ./foo`，預期被擋。

- [ ] **Step 3: 驗證 `the-door ui` 通過**

`the-door ui --help`（或類似 read-only 呼叫），預期通過。

- [ ] **Step 4: Commit**

```bash
git add .claude/settings.json
git commit -m "hook: warn when the-door serve is used (correct command is ui)"
```

---

## Acceptance（全部 4 個 Task 完成後）

- [ ] `.claude/settings.json` 包含 1 個 `UserPromptSubmit` hook + 2 個 `PreToolUse` hook（Edit/Write/NotebookEdit、Bash 各一）
- [ ] 不引入任何 npm/pip dependency
- [ ] 3 條觸發場景都實測過（Task 2 step 3、Task 3 step 2、Task 4 step 2）
- [ ] CLAUDE.md 不變（hook 是補強不是取代）
