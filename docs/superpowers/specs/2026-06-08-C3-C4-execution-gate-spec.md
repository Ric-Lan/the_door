# C3+C4 spec：執行序 blocking-hook gate（snapshot_write 前置 ＋ 原生 code-exec 封口）

> **日期**：2026-06-08　**狀態**：spec（待雙審 → plan → 雙審 → inline TDD → ff-merge）
> **承接**：丙案種子 §6 垂直試點、§9.2（真逃生口）、§10.1（C0 實證）、§10.7 表（C3/C4）。
> **co-require**：C3 與 C4 **同一刀**（種子 §10.7.2「C4 與 C3 同時」）——只 gate MCP 順序不堵原生 code-exec＝沒堵逃生口。
> **性質**：純加法（新增 hook 腳本＋settings.json 註冊＋測試）。不改 the_door production code。

---

## 1. 命題與目標

The Door 的「正確操作順序」目前是 CLAUDE.md 散文（軟層，agent 會漂移/繞道）。丙案把控制流外部化為
**PreToolUse blocking hook（exit 2 物理 deny）**。本刀做**第一個可驗 gate ＋ 封一個逃生口**：

- **C3**：gate `mcp__the-door__snapshot_write`——除非目標 codebase 已有 `edge-residue.json` artifact，否則 **deny**，stderr 教 agent「先呼叫 `edge_residue`」。強制「先產雜訊料 → 才落 L1」的序（T2 已備好該 artifact 與工具）。
- **C4**：gate `Bash`——deny 臨時 `python -c` / 獨立 `.py` 腳本執行（種子 §9.2 實證的**真逃生口**：agent 寫 `_noise_inspect.py` 之類繞過 MCP 工具）。允許正當開發/CLI（`python -m pytest`、`pip`、`pytest`、`git`、`the-door`、`npx`）。

**為何 co-require**：C3 只擋 MCP 順序；若不同時封 C4，agent 可寫 `python -c "from the_door...SnapshotStore..."` 直接落盤、繞過整個 gate（種子 §9.2/§10.2.2）。兩者合一才閉環。

**非目標**：不做 C2（checklist schema）、C5（README）、PostToolUse 蓋章；不做 node-coverage/currency 檢查（C3 首閘只驗 artifact **存在性**，承種子 §3 偏差，見 §7）。

---

## 2. 背景與驗證事實（spike 已對真實環境驗畢）

| # | 事實 | 依據 |
|---|---|---|
| 2.1 | 機制成立：PreToolUse matcher 命中 → `exit 2` 物理 deny → stderr 回灌 LLM；中途加 hook 即時生效 | C0 spike（種子 §10.1，實機通過） |
| 2.2 | MCP 精確工具名可當 matcher（`mcp__the-door__snapshot_write`） | C0（測 `mcp__the-door__project_list`，同 matcher 欄位） |
| 2.3 | 既有 `.claude/settings.json` 已有 PreToolUse hook 範式：`matcher` + `command`（bash）+ `exit 2`/`>&2` | `.claude/settings.json`（prototype-block、serve-block） |
| 2.4 | 🔴 **`jq` 系統性缺席**（`which/where/常見路徑` 全無）⟹ 既有兩條 **jq-based hook 實為靜默失效**（jq 缺→pipeline 空→grep 不中→`exit 0`）。本刀**不得依賴 jq** | spike：`which jq`→none；`where jq`→none |
| 2.5 | `python` 可用（`/c/Users/Ric/AppData/Local/Programs/Python/Python312/python`）⟹ 用 python 解析 hook stdin JSON（取代 jq） | spike：`which python`→存在 |
| 2.6 | PreToolUse stdin JSON 含 `tool_input`（既有 serve-hook 讀 `.tool_input.command`，本刀讀 `.tool_input.codebase_path`/`.command`） | `.claude/settings.json` serve-hook |
| 2.7 | C3 邏輯實證（native Windows path）：artifact 缺→exit 2、在→exit 0、無 codebase_path→exit 0（fail-open） | spike：`c3.py` 三案通過 |
| 2.8 | C4 邏輯實證：`python -c`/`python x.py`/`python ./a.py`→deny；`python -m pytest`/`pytest`/`pip`/`git`/`npx`/`the-door`→allow | spike：`c4.py` 11 案通過 |
| 2.9 | hook 的 python＝Windows-python；MCP `snapshot_write` 的 `codebase_path` 是 Windows 路徑 ⟹ `os.path.isfile` 解析得到（MSYS `/tmp` 路徑才解析不了，但那不會出現在 MCP tool_input） | spike：MSYS path 失敗、Windows path 成功 |
| 2.10 | `snapshot_write` TOOL_SCHEMA required `codebase_path` ⟹ C3 必能從 tool_input 取得路徑 | `snapshot_write_tool.py:20-24`（T2 spec §4d 已驗） |

**結論**：唯一原設計未知（jq 可行性）被**證偽**並以 python 取代；其餘皆實證。設計落在已驗接縫上。

---

## 3. 設計

### 3.1 hook 腳本（committed，jq-free，python）

新增目錄 `.claude/hooks/`，兩個單一職責腳本：

**`.claude/hooks/c3_gate_snapshot_write.py`**（PreToolUse，matcher＝`mcp__the-door__snapshot_write`）
- 讀 stdin JSON → `tool_input.codebase_path`。
- 無路徑或 JSON 解析失敗 → `exit 0`（fail-open，不擋無辜）。
- `<codebase_path>/.the-door/edge-residue.json` 存在 → `exit 0`；否則 stderr 寫教學訊息（指回 `edge_residue` 工具）→ `exit 2`。

**`.claude/hooks/c4_block_native_exec.py`**（PreToolUse，matcher＝`Bash`）
- 讀 stdin JSON → `tool_input.command`。
- 正則 `\bpython[0-9.]*\s+(-c\b|[^-\s][^\s]*\.py\b)` 命中 → deny（`exit 2`＋stderr 教學）；否則 `exit 0`。
- 允許：`python -m ...`（pytest/the_door/pip）、`pytest`、`pip`、`git`、`npx`、`the-door`、無 python 的指令。

> **fail-open 原則**：兩腳本對「無法判定」一律 `exit 0`。gate 的價值在擋住**明確違規**，不在擋住一切；誤擋會 brick 工作流（比漏擋更糟），承種子「剛性桿只承載明確的執行序壓應力」。

### 3.2 settings.json 註冊（`.claude/settings.json`，加 2 條 PreToolUse）

> 🔴 **指令層守衛（雙審 critical 修）**：裸 `python "$X/script.py"` 在路徑未展開/腳本缺失/python 不在 hook-shell PATH 時會 **exit≠0**；掛在 `Bash` matcher 上＝**deny 全部 bash＝brick**。故指令外層**先驗 python 與腳本存在，缺則 `exit 0`（真 fail-open）；存在才執行並忠實傳遞腳本 exit code**。**嚴禁** `python ... || exit 0`（會把真 deny 的 exit 2 吞成 0）。

```json
{ "matcher": "mcp__the-door__snapshot_write",
  "hooks": [{ "type": "command",
    "command": "f=\"$CLAUDE_PROJECT_DIR/.claude/hooks/c3_gate_snapshot_write.py\"; if command -v python >/dev/null 2>&1 && [ -f \"$f\" ]; then python \"$f\"; else exit 0; fi" }] },
{ "matcher": "Bash",
  "hooks": [{ "type": "command",
    "command": "f=\"$CLAUDE_PROJECT_DIR/.claude/hooks/c4_block_native_exec.py\"; if command -v python >/dev/null 2>&1 && [ -f \"$f\" ]; then python \"$f\"; else exit 0; fi" }] }
```
- `$CLAUDE_PROJECT_DIR`＝Claude Code 為 hook 設的專案根（worktree 內＝worktree 根；腳本已 committed、兩處皆在）。未展開時 `[ -f ]` 為假 → `exit 0`（不 brick）。
- `if ... then python "$f"; else exit 0; fi` 結構讓 python 的 exit code（0 allow／2 deny）**原樣冒泡**，僅在「python 或腳本不可用」時才 fail-open。
- C4 與既有 serve-block 同為 `Bash` matcher，兩條並存各自獨立跑（serve-block 雖 jq-dead 但無害；見 §5 findings）。

### 3.3 不動
- the_door production code、provider、viewer：**不碰**。
- 既有 jq hooks：**本刀不改**（見 §5 finding F1，列為建議後續，避免本刀擴面）。

---

## 4. 範圍邊界

**In**：2 個 python hook 腳本、settings.json 2 條註冊、piped-JSON 單元測試。
**Out**：
- ❌ C2 checklist schema／C5 README／PostToolUse 蓋章。
- ❌ node-coverage／currency（stale）檢查（C3 首閘只驗存在性，§7 偏差）。
- ❌ gate `snapshot_create`/`snapshot_patch`（pilot 只 gate `snapshot_write`＝agent-as-LLM L1 落盤口）。
- ❌ 修既有 jq hooks（F1 列後續）。
- ❌ gate `Write`（封 .py 寫入會擋掉 the_door 自身開發；C4 只封**執行**，承種子「gate code-exec」）。

---

## 5. 已發現問題 / findings（執行時必須承認）

- **F1 🔴（jq 缺席→既有 hooks 靜默失效）**：`.claude/settings.json` 兩條 jq-based PreToolUse（prototype-block、serve-block）在本機**從未真正生效**（2.4）。本刀的 C3/C4 改用 python ⟹ 真能擋。**建議另刀**把既有兩條也轉 python（小、同機制），讓 repo 的守衛名實相符。本刀不含（避免擴面＋改既有行為）。
- **F2（C4 在本 dev repo 也會擋 `python -c`）**：這是 gate 的**本意**（agent 不該寫臨時 python 繞工具）；開發驗證改用 `python -m pytest` / Read 工具 / MCP 工具。已確認本刀剩餘步驟（pytest、git、npx）皆不受 C4 影響（2.8）。可逆（revert commit）。
- **F3（C3 本 session 無法 live-fire）**：the-door MCP server 本 session 斷線 ⟹ C3 不能經真實 `snapshot_write` 觸發驗證。以**腳本 piped-JSON 單元測**＋C0 機制實證替代；live e2e 待 MCP 重連另行抽驗。
- **F4（Bash matcher 雙 hook 順序）**：C4 與 serve-block 同 matcher；Claude Code 對同 matcher 多 hook 全跑、任一 exit 2 即 deny。C4 獨立正確即可，不依賴 serve-block。

---

## 6. 驗收 / TDD（紅→綠）

測試＝**腳本邏輯的 piped-JSON 黑箱測**（subprocess 餵 stdin、斷言 exit code＋stderr）。置於 `the_door/tests/unit/hooks/test_execution_gates.py`（隨既有 pytest 跑、納入零回歸護欄）。腳本以 repo-root 相對定位（`Path(__file__).parents[4]/".claude/hooks"`）。

| # | 測試 | 斷言 |
|---|---|---|
| G-1 | C3 artifact 缺 | exit 2、stderr 含 `edge_residue` |
| G-2 | C3 artifact 在 | exit 0 |
| G-3 | C3 無 codebase_path | exit 0（fail-open） |
| G-4 | C3 stdin 非 JSON | exit 0（fail-open，不擋） |
| G-5 | C4 `python -c "..."` | exit 2、stderr 含 C4 訊息 |
| G-6 | C4 `python foo.py` / `python ./a/b.py` | exit 2 |
| G-7 | C4 `python -m pytest ...`／`pytest`／`pip install`／`git`／`npx`／`the-door ui` | exit 0（逐一） |
| G-8 | C4 stdin 非 JSON / 無 command | exit 0 |
| G-9（settings 完整性） | `.claude/settings.json` 可解析、含 C3/C4 兩 matcher、command 字串引用存在的腳本檔 | JSON load＋matcher 集合斷言＋從 command 抽路徑驗檔存在 |
| G-10（指令字串守衛，雙審 warning 修） | 用 `bash -c` 跑 §3.2 真實 command 字串（設 `CLAUDE_PROJECT_DIR`＝repo root）：deny 案→exit 2、allow 案→exit 0、**腳本路徑不存在時→exit 0（fail-open，不 brick）** | subprocess `bash -c`＋環境變數；三斷言。若環境無 bash 則 `pytest.skip`（記原因） |

**零回歸**：`pytest -q` 全綠（新增測試、不動 production）。

---

## 7. Forward-coherence（與種子 §3、後續刀）

- 🔴 **與種子 §3 偏差（承 T2 spec §7、不可隱瞞）**：種子要 gate 驗「artifact 存在**且涵蓋本批節點**」；本刀 artifact 版本-less、無 coverage manifest ⟹ **C3 首閘只做存在性**。stale artifact 仍會過閘。**這是 pilot 有意簡化**（先證機制能擋）；coverage＋currency 待 C2（checklist schema）補 `version_id`＋node-coverage 時升級。**C2 spec 須承接此偏差。**
- **對 C5（README）**：C3/C4 的 deny stderr 即「違規當下教學」位置；C5 之後讓 stderr 指回 per-version README（種子 §10.6「強制力在 deny、README 是指回處」）。
- **對 T5-A**：C3/C4 證「gate 機制可擋＋封逃生口」後，移除 provider（T5-A/T5-P）才有「結構已強制單一路徑」的底氣。

---

## 8. 雙審結果（concept --design ＋ 5 軸；已 inline 修畢）
**已修：**
- ✅ **critical（指令層 fail-CLOSED→brick 全 Bash）**：§3.2 指令加 `command -v python && [ -f "$f" ]` 守衛、缺則 `exit 0`，以 `if/then/else` 忠實傳遞 python exit（嚴禁 `|| exit 0` 吞 deny）。
- ✅ **warning（未驗指令字串）**：§6 加 G-10，用 `bash -c` 跑真實 command 字串驗 deny/allow/腳本缺→fail-open。
- ✅ **suggestion（fail-open 取捨）**：§3.1 已明記「誤擋 brick＞漏擋」；C3 維持 fail-open，coverage 待 C2。

**仍為 pilot 容許/後續（非阻擋）：**
- C4 正則漏縫（`python -u foo.py`＝flag 在 script 前不擋）——種子認 Bash-parse 必有縫，pilot 容許；可後續補強。
- `$CLAUDE_PROJECT_DIR` 展開：已用 `[ -f ]` 守衛兜底（未展開→fail-open，不 brick）；G-10 另驗 fail-open。
- F1：既有 2 條 jq hook 轉 python＝**另刀**（本刀嚴守 C3/C4 範圍、不改既有行為）。
