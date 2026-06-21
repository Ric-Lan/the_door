# 動手前三問：執行紀律閘門 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增 C5 PreToolUse hook（攔截 Bash 工具的 grep/cat/find 等讀檔替代命令），並在 CLAUDE.md 植入「動手前三問」規則區塊，固化三種執行失誤的防護。

**Architecture:** 兩組件獨立部署：C5 hook 是純 Python 腳本，透過 PreToolUse 機制在每次 Bash 工具呼叫前執行，fail-open（解析失敗即放行）；CLAUDE.md 三問區塊是 context-always-loaded 規則，依賴 Claude Code 每次載入 CLAUDE.md 的機制。兩者皆針對本專案（`.claude/` 層），不影響其他專案。

**Tech Stack:** Python 3（hook 腳本）、JSON（settings.json 修改）、Markdown（CLAUDE.md）

---

## 環境速查（實作前確認）

| 項目 | 路徑 |
|---|---|
| 現有 C4 hook | `.claude/hooks/c4_block_native_exec.py` |
| Hook 設定檔 | `.claude/settings.json` |
| 目標文件 | `CLAUDE.md`（repo root）|
| Spec | `docs/superpowers/specs/2026-06-21-action-discipline-gates-design.md` |

**C4 在 settings.json 的位置**：`PreToolUse` 陣列第二個 `"matcher": "Bash"` 項目（第一個是 `block_the_door_serve.py`）。C5 加在 C4 之後，成為第三個 Bash 項目，同時也是整個 PreToolUse 陣列的最後一項。

---

## Task 1：建立 C5 hook 腳本

**Files:**
- Create: `.claude/hooks/c5_tool_selection.py`

- [ ] **Step 1：建立 `.claude/hooks/c5_tool_selection.py`**

  完整內容（逐字複製自 spec）：

  ```python
  #!/usr/bin/env python3
  """C5 gate: block shell commands that have dedicated Claude Code project tools.

  PreToolUse hook on Bash. Denies: grep/rg (→ Grep), cat/head/tail (→ Read),
  find (→ Glob). Fail-open on unparseable input. Allows everything else.
  """
  import json
  import sys
  import re

  _BLOCKED = {
      "grep": "Grep 工具（pattern, path, output_mode）",
      "rg":   "Grep 工具（pattern, path, output_mode）",
      "cat":  "Read 工具（file_path, offset, limit）",
      "head": "Read 工具（file_path, offset, limit）",
      "tail": "Read 工具（file_path, offset, limit）",
      "find": "Glob 工具（pattern, path）",
  }

  # matches optional leading KEY=VALUE env-var assignments, captures first real token
  _FIRST_TOKEN = re.compile(r"^(?:[A-Z_][A-Z0-9_]*=\S*\s+)*(\S+)", re.IGNORECASE)


  def _deny(msg: str) -> int:
      try:
          sys.stderr.buffer.write(msg.encode("utf-8"))
          sys.stderr.buffer.flush()
      except Exception:
          try:
              sys.stderr.write(msg)
          except Exception:
              pass
      return 2


  def main() -> int:
      try:
          data = json.load(sys.stdin)
      except Exception:
          return 0
      cmd = (data.get("tool_input") or {}).get("command") or ""
      m = _FIRST_TOKEN.match(cmd.strip())
      if not m:
          return 0
      tok = m.group(1).lower()
      # Strip path prefix (e.g. /usr/bin/grep → grep)
      tok = tok.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
      if tok not in _BLOCKED:
          return 0
      redirect = _BLOCKED[tok]
      return _deny(
          f"⛔ C5 工具選擇攔截：偵測到 `{tok}`。\n"
          f"→ 請改用 {redirect}。\n"
          f"Bash 只用於：git、curl、npm/npx、pip、the-door、pytest、rm、mkdir "
          f"等無對應專案工具的操作。\n"
      )


  if __name__ == "__main__":
      sys.exit(main())
  ```

⚠️ **C4 限制**：`python xxx.py` 會被 C4 攔截，無法在 Bash 工具內直接呼叫 hook 腳本做冒煙測試。行為驗證移到 Task 2 完成後進行（見 Task 2 Step 3）。

---

## Task 2：在 settings.json 註冊 C5

**Files:**
- Modify: `.claude/settings.json`

- [ ] **Step 1：在 PreToolUse 陣列末尾（C4 項目之後）新增 C5 hook 項目**

  當前 `.claude/settings.json` 的 PreToolUse 陣列最後是（lines 41–48）：

  ```json
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "f=\"$CLAUDE_PROJECT_DIR/.claude/hooks/c4_block_native_exec.py\"; if command -v python >/dev/null 2>&1 && [ -f \"$f\" ]; then python \"$f\"; else exit 0; fi"
          }
        ]
      }
    ],
  ```

  用 Edit 工具將上面這段替換為：

  ```json
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "f=\"$CLAUDE_PROJECT_DIR/.claude/hooks/c4_block_native_exec.py\"; if command -v python >/dev/null 2>&1 && [ -f \"$f\" ]; then python \"$f\"; else exit 0; fi"
          }
        ]
      },
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "f=\"$CLAUDE_PROJECT_DIR/.claude/hooks/c5_tool_selection.py\"; if command -v python >/dev/null 2>&1 && [ -f \"$f\" ]; then python \"$f\"; else exit 0; fi"
          }
        ]
      }
    ],
  ```

  ⚠️ 注意：C4 項目末尾的 `}` 後面新增逗號（`,`），C5 新增項目為最後一項（無尾逗號），PreToolUse 陣列閉括號 `]` 保持不動。

- [ ] **Step 2：確認 JSON 合法**

  ```powershell
  python -m json.tool .claude/settings.json
  ```

  期望：輸出格式化後的完整 JSON，無報錯（若報 `JSONDecodeError` 則逗號/括號有誤，退回 Step 1）。

- [ ] **Step 3：行為驗證（C5 已在 hook 路徑上，不需重啟）**

  透過 Bash 工具執行以下兩條命令，確認 C5 生效：

  ```bash
  grep foo bar.txt
  ```
  期望：stderr 顯示「⛔ C5 工具選擇攔截：偵測到 `grep`」，工具回報 blocked（exit 2）。

  ```bash
  git log --oneline -5
  ```
  期望：正常執行並輸出最近 5 筆 commit（exit 0，無攔截訊息）。

---

## Task 3：在 CLAUDE.md 插入「動手前三問」區塊

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1：在 `## ⚠️ 開發環境速查` 之前插入三問區塊**

  用 Edit 工具，`old_string` 精確匹配：

  ```
  ## ⚠️ 開發環境速查（必讀，任何操作前確認）
  ```

  `new_string` 為（三問區塊 + 原標題）：

  ```
  ## ⛔ 動手前三問（每次規劃行動前強制自問）

  ### 閘門 1：工具選擇
  我要做的事是「讀檔 / 搜字串 / 找檔案 / 寫檔」嗎？
  - 是 → Read / Grep / Glob / Write / Edit，不用 Bash
  - 不確定 → 先列出要做的事，逐項對照工具，再動手

  ### 閘門 2：relation_type 標記（寫 snapshot_write relations 參數前必問）
  這條依賴，AST 能靜態追蹤到呼叫路徑嗎？
  - 能（同語言、直接 import / call 可追蹤）→ `static`
  - 不能（HTTP 邊、跨語言、透過資料檔解耦、v 版本架構移除直連）→ `inferred`，附 `inferred_reason`
  - **「功能上有依賴」≠「AST 可追蹤」——這是兩件事，分開判斷**

  ### 閘門 3：破壞性操作順序（執行 rm / 覆蓋 / reset 前必問）
  替代品已寫入且驗證通過了嗎？
  - 是 → 可以刪舊的
  - 否 → 先建後刪，不反過來
  - 「刪掉才能繼續」不是理由，是操作順序規劃的失誤

  ## ⚠️ 開發環境速查（必讀，任何操作前確認）
  ```

- [ ] **Step 2：目視確認插入正確（使用 Read 工具，不用 cat）**

  使用 Read 工具（`file_path: CLAUDE.md, limit: 50`）讀前 50 行，確認：
  - `## ⛔ 動手前三問` 出現在 `## ⚠️ 開發環境速查` 之前
  - 三個閘門的措辭與 spec 原文逐字一致（無截斷、無重複）
  - `## 🚫 硬規則` 區塊在最前，三問在中，開發環境速查在後

---

## Task 4：Commit

**Files:** `.claude/hooks/c5_tool_selection.py`、`.claude/settings.json`、`CLAUDE.md`、`docs/superpowers/specs/2026-06-21-action-discipline-gates-design.md`

- [ ] **Step 1：確認 git status 只包含預期的四個檔案**

  ```powershell
  git status
  ```

  期望：僅 `.claude/hooks/c5_tool_selection.py`（新增）、`.claude/settings.json`、`CLAUDE.md`、`docs/superpowers/specs/2026-06-21-action-discipline-gates-design.md` 出現在 modified / untracked。

- [ ] **Step 2：Stage 並 Commit**

  ```powershell
  git add .claude/hooks/c5_tool_selection.py .claude/settings.json CLAUDE.md docs/superpowers/specs/2026-06-21-action-discipline-gates-design.md
  git commit -m "feat(discipline): add C5 tool-selection hook + 動手前三問 CLAUDE.md gates"
  ```

  期望：commit 成功，無 hook 報錯。

---

## Self-Review Checklist（計畫撰寫者自查）

- [x] **Spec coverage**
  - C5 hook 腳本內容：Task 1 Step 1 ✓（逐字複製）
  - settings.json 註冊 C5（C4 之後）：Task 2 Step 1 ✓
  - CLAUDE.md 三問插入（開發環境速查之前）：Task 3 Step 1 ✓
  - JSON 語法確認（`python -m json.tool`，C4 放行）：Task 2 Step 2 ✓
  - C5 行為驗證（grep 擋 / git 放，透過 Bash 工具）：Task 2 Step 3 ✓
  - CLAUDE.md 插入位置目視確認（Read 工具，非 cat）：Task 3 Step 2 ✓
  - Commit：Task 4 ✓

- [x] **Placeholder scan：無 TBD / TODO / 類似 Task N 等佔位符**

- [x] **Type consistency：無跨 Task 的名稱不一致**
