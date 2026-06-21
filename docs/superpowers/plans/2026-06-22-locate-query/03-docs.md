# Phase 3 — 文件

> 父計畫：[../2026-06-22-locate-query-plan.md](../2026-06-22-locate-query-plan.md)
> 前置：Phase 1、2 完成。文件描述的行為須與已實作一致。

硬性需求（使用者指定）：文件**開頭就標明這是 secondary、非主打**，並明列兩條限制，
讓使用者理解。

---

### Task 8: `docs/locate-query.md` + CLAUDE.md 工具表

**Files:**
- Create: `docs/locate-query.md`
- Modify: `CLAUDE.md`（「Commands & MCP tool reference」表格加一列）

- [ ] **Step 1: 寫 `docs/locate-query.md`**

建 `docs/locate-query.md`，完整內容如下：

````markdown
# Locate Query — symbol 定位點查

> ⚠️ **這是 The Door 的輔助便利功能（secondary），不是主打。**
> The Door 的主打是「功能語意翻譯」（L1/L2 功能、專案簡介、版本敘述）。
> 本功能讓你**順手用同一份產出**（`extract_structure` 已寫好的
> `.the-door/structure-view/`）做程式碼定位，省去 AI 反覆 grep/Read 的 token。
> 它不另存資料、不另建索引，與主打路徑共用同一份結構產出。

## 兩條限制（請先理解）

1. **資料非即時。** 定位查的是上一次 `extract_structure` 落下的結構快照。改了程式碼
   後，需**重跑 `extract_structure`** 這份資料才會更新。每次查詢回應都帶一個
   `freshness` 欄位（`fresh` / `stale` / `unknown`）提示資料新不新；
   `stale` 會列出有哪些檔自上次抽取後變動過。
   （技術註：`freshness` 比對的是當前 source 與上次 `edge_residue` 蓋章時的
   檔案指紋，作為「結構是否過時」的**近似**訊號，非精確保證。）

2. **名稱比對，非語意搜尋。** `search` 對 symbol 名稱與 node_id（`file::symbol`）
   做子字串比對，**不理解自然語言意圖**。問函式名、檔名找得到；不能用一句模糊描述
   做語意搜尋。

## 兩個動作

### search — 找 symbol

- MCP：`locate(codebase_path, action="search", query="...", limit=20)`
- CLI：`the-door locate search <query> [--codebase-path .] [--limit 20]`

回符合 `query`（比對 name 與 node_id）的清單，**名稱命中排在純路徑命中之前**，
其次按被呼叫次數（in_degree）降冪。每筆含 `node_id` / `file` / 行號 / `in_degree`
/ `match_kind`（`name` 或 `path`）。

### node — 看單一節點

- MCP：`locate(codebase_path, action="node", node_id="auth.py::authenticate_user")`
- CLI：`the-door locate node <node_id> [--codebase-path .]`

回該節點的位置（file:line）、`callers`（誰呼叫它）、`callees`（它呼叫誰）。
先用 `search` 找到正確 `node_id` 再 `node` 查詳情。

## 與主打路徑的關係

`extract_structure` → 結構產出 `.the-door/structure-view/`：
- **主打**：你（agent-as-LLM）讀它 → 產 L1 功能 → `snapshot_write`。
- **本功能（輔助）**：`locate` 直接點查同一份結構，不經 LLM、不產敘述。

兩者共用同一份產出，互不干擾。
````

- [ ] **Step 2: 改 CLAUDE.md 工具表**

在 `CLAUDE.md` 的「## Commands & MCP tool reference」表格中，於 `system_status` 那一列
之後，加入這一列（維持表格欄位：`| Command / Tool | Use when |`）：

```markdown
| `locate` MCP / `the-door locate` CLI | （Secondary，非主打）對既有 structure-view 做 symbol 定位點查：`action=search` 用名稱/路徑找 symbol、`action=node` 看單節點 callers/callees。資料非即時（改碼後重跑 extract_structure）、名稱比對非語意搜尋。詳 [`docs/locate-query.md`](docs/locate-query.md)。 |
```

- [ ] **Step 3: 驗證文件連結與 Markdown 正確**

Run: `python -m pytest tests/ -k "claude_md or docs" -v`
Expected: 若無對應 lint 測試則為「no tests ran」——此時改以人工確認：
`docs/locate-query.md` 與 CLAUDE.md 新列無斷裂表格、連結路徑存在。

> 此 Task 無自動化斷言（純文件）。確認方式：開啟兩檔目視，或
> `the-door locate --help` 輸出與文件描述一致。

- [ ] **Step 4: Commit**

```bash
git add docs/locate-query.md CLAUDE.md
git commit -m "docs(locate): add locate-query guide + CLAUDE.md tool row (secondary)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### 收尾：全套件回歸

- [ ] **Step 1: 跑全測試套確認無回歸**

Run: `python -m pytest tests/ -q`
Expected: 全 PASS（含新增的 locator / locate_tool / locate_cmd 測試）。
已查核：`tests/unit/mcp/test_server_tool_registry.py` 只驗 `_build_tools()` 與
`REGISTERED_TOOL_NAMES` 內部一致（自動衍生，加 `locate` 自動通過）；
`tests/unit/mcp/test_tools.py` 無「工具總數」硬斷言。故新增 `locate` **不應**讓既有測試
變紅；若有非預期紅燈，先排查是否自己改錯接線，而非直接改既有斷言。

- [ ] **Step 2: 確認沒動到禁區**

`git diff --stat main` 應只含：`core/structure_view/locator.py`、`mcp/tools/locate_tool.py`、
`mcp/server.py`、`cli/locate_cmd.py`、`cli/main.py`、`docs/locate-query.md`、`CLAUDE.md`、
新測試檔。**不應**出現：任何 `models/`、`extract_structure`、契約版號、gate hook、前端 viewer 檔案。

---

## Phase 3 自審

- **spec §6 文件**：Task 8 開頭標 secondary + 兩條限制（含 §5.3 近似聲明）、CLAUDE.md 一列。✓
- **非主打表述**：`docs/locate-query.md` 首段與 CLAUDE.md 列均明示 Secondary。✓
- **禁區守恆**：收尾 Step 2 用 `git diff --stat` 把關不碰 models/契約/gate/viewer。✓
- **無 placeholder**：文件內容完整給出，非「填入說明」。✓
