# The Door — 動手前三問：執行紀律閘門設計

**目的**：攔截三種已知失誤模式在執行中途復發。
**適用範圍**：The Door 專案層（`.claude/`、`CLAUDE.md`），不影響其他專案。

---

## 問題與機制對照

| 失誤模式 | 機制 | 強制程度 | 觸發時機 |
|---|---|---|---|
| 工具選擇：用 Bash 做讀檔/搜字/找檔 | C5 PreToolUse hook | 強制攔截（exit 2） | 每次 Bash 工具呼叫前 |
| 語意混淆：把概念依賴誤標 `static` | CLAUDE.md 閘門 2 | 規則約束（context 常駐） | agent 組裝 `relations` 參數時 |
| 操作順序：替代品未驗證就執行破壞 | CLAUDE.md 閘門 3 | 規則約束（context 常駐） | agent 計畫刪除/覆蓋操作時 |

---

## 組件 1：C5 Hook（工具選擇攔截）

### 新增檔案：`.claude/hooks/c5_tool_selection.py`

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

### 設計決策

- **偵測方式**：取命令第一個非環境變數 token，跳過 `KEY=VALUE` 前綴（如 `PYTHONUTF8=1 python -m pytest` → 第一 token 是 `python`，不在封鎖清單，放行）
- **路徑前綴**：剝除 `/usr/bin/grep` 的路徑部分，只比對執行檔名
- **管線內 grep**（如 `ls | grep foo`）：hook 只看整條命令第一 token（`ls`），不封鎖——可接受，日後有需要再收緊
- **Fail-open**：JSON 解析失敗或命令為空 → exit 0，不阻擋正常工作
- **與 C4 並存**：C4 = 攔截 `python -c` 和臨時 .py 腳本（位於 PreToolUse Bash matcher 第一筆）。C5 掛在 C4 之後（第二筆），攔截 shell 工具。兩個 hook 各自獨立不干擾。

### 註冊到 `.claude/settings.json`

在 `hooks.PreToolUse` 陣列中，緊接在 C4 的 Bash 項目**之後**新增一筆：

```json
{
  "matcher": "Bash",
  "hooks": [
    {
      "type": "command",
      "command": "f=\"$CLAUDE_PROJECT_DIR/.claude/hooks/c5_tool_selection.py\"; if command -v python >/dev/null 2>&1 && [ -f \"$f\" ]; then python \"$f\"; else exit 0; fi"
    }
  ]
}
```

---

## 組件 2：CLAUDE.md 三閘門區塊

### 插入位置

`CLAUDE.md` 中，`## ⚠️ 開發環境速查（必讀，任何操作前確認）` 區塊**之前**。

### 插入文字（精確，不可改措辭）

```markdown
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

```

---

## 不做的事（邊界）

- **不在 `mcp__the-door__snapshot_write` 加 hook**：工具層不判斷傳入語意對錯，那是 agent 責任（閘門 2 負責）
- **不封鎖 `rm`**：問題是順序脈絡，hook 無法判斷「有沒有先建好替代品」，交給閘門 3
- **不加 `echo >` 偵測**：echo 用途多、難以可靠區分，過度攔截副作用大
- **不寫獨立 skill 檔**：三問已在 CLAUDE.md 常駐，不需另存 skill 再依賴 agent 記得呼叫

---

## 實作清單（給 Claude Code）

1. 新增 `.claude/hooks/c5_tool_selection.py`（內容如上方程式碼區塊）
2. 修改 `.claude/settings.json`：在 PreToolUse 陣列中、C4 Bash 項目之後新增 C5 的 Bash hook 項目（格式與 C4 相同）
3. 修改 `CLAUDE.md`：在 `## ⚠️ 開發環境速查` 之前插入「動手前三問」區塊（文字如上）
4. 確認 `.claude/settings.json` JSON 語法合法（逗號、括號無誤）
5. 手動觸發一次 `grep` 命令驗證 C5 攔截訊息正確輸出；再觸發 `git log` 確認放行
6. 目視確認 CLAUDE.md：三問插入位置正確（`## ⚠️ 開發環境速查` 之前），逐字對照 spec 原文，確認措辭無失真
