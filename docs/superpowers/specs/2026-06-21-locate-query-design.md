# 設計：定位查詢（Locate Query）

- 日期：2026-06-21
- 狀態：設計已核可，待寫實作計畫
- 定位：**輔助便利功能（secondary / convenience），非 The Door 主打**

---

## 1. 目標與動機

讓 AI agent（與人）能對 The Door **既有產出**做點查，快速定位程式碼——
「這個 symbol 在哪、誰呼叫它、它呼叫誰」，省去反覆 grep/glob/Read 的 token。
對標 CodeGraph 的定位用途，但**不另立產品線**：吃的是 `extract_structure` 已經
寫好的同一份 `.the-door/structure-view/` 資料。

### 鐵則（範圍紀律）

- **零重抽取**：locator 只讀持久化 artifact，**不呼叫 `ASTExtractor`**。
  （對比：`edge_residue` 工具會重跑 ASTExtractor——本功能刻意不這麼做。）
- **純加法**：不改任何 model、不動 `extract_structure` 輸出、不 bump
  `SNAPSHOT_CONTRACT_VERSION`、不新增/修改任何 gate。
- **YAGNI**：只做 `search` + `node` 兩個查詢；不建 SQLite/FTS5 索引
  （標的規模 load+scan 已是毫秒級，見 §7）。

### 非目標（明確排除）

- 不做語意/向量搜尋（只做名稱與 node_id 的子字串比對）。
- 不做即時 file-watch 自動 re-index（資料新鮮度見 §5）。
- 不做 callers/callees 的獨立查詢工具（查一次 `node` 即含兩者，§4.2）。
- 不動前端 viewer。

---

## 2. 架構

一個核心 + 兩個薄轉接，兩個轉接呼叫同一核心，回同一份資料：

```
core/structure_view/locator.py        ← 唯一邏輯：讀 artifact、建索引、答查詢、算 freshness
   ├── mcp/tools/locate_tool.py        ← MCP 轉接（給 AI agent）
   └── cli/locate_cmd.py               ← CLI 轉接（給人，click 指令）
```

- **locator.py**：純函式為主，輸入 `codebase_path`（+查詢參數），輸出 dict。
  不依賴 MCP/CLI，可被兩端與測試直接呼叫。
- **locate_tool.py**：照現有 MCP 工具樣式——`TOOL_SCHEMA` dict +
  `async def execute(arguments) -> dict`，成功回 `wrap(payload, Path(codebase_path))`，
  失敗回 `{"error": ...}`。於 `mcp/server.py` 的 `TOOLS` 清單加 `Tool(...)` 條目
  並在 dispatch 加 `elif name == "locate": ...`。
- **locate_cmd.py**：`@click.command("locate")`，於 `cli/main.py` 用
  `main.add_command(locate_cmd)` 註冊。

---

## 3. 資料來源與載入

### 3.1 來源 artifact

`<codebase>/.the-door/structure-view/`（由 `extract_structure` 產出）：

- `regions/<region_id>.json.gz` — 每區的 L2 node 視圖陣列。每個視圖（見
  `core/structure_view/node_view.py`）含：
  - `node_id`（格式 `file_path::symbol`，碰撞時加 `#i` 後綴）
  - `name`（裸符號名）、`type`、`file`、`start_line`、`end_line`、`language`
  - `topology`：`in_degree` / `out_degree` / `topology_rank` / `is_entry_point`
  - `in_edges`：`[{from_node_id, type, resolution}]` ←＝callers
  - `out_edges`：`[{to_node_id, type, resolution}]` ←＝callees

### 3.2 載入策略

locator 載入時讀**所有** `regions/*.json.gz`，在記憶體建兩張表（一次建、查詢共用）：

- `by_id: {node_id -> view}`
- `by_name: {name.lower() -> [node_id, ...]}`

規模見 §7，全量載入毫秒級，無需快取/索引檔。

### 3.3 artifact 不存在

若 `.the-door/structure-view/` 或 `regions/` 不存在 → locator 回明確錯誤：

```json
{ "error": "no structure-view artifacts; run extract_structure(codebase_path=...) first" }
```

---

## 4. 查詢動作

### 4.1 `search(codebase_path, query, limit=20)`

- **輸入守衛**：`query` 去除前後空白後為空 → 回 `{ "error": "query is required" }`。
- **比對**：`query` 大小寫不敏感，對每個節點的 `name` **與** `node_id` 做子字串比對，
  任一命中即收錄。並記錄命中種類：`name` 命中＝`match_kind="name"`，
  僅 `node_id`（路徑）命中＝`match_kind="path"`。
- **排序**（三層鍵，穩定）：
  1. `match_kind`：`name`（0）排在 `path`（1）之前——精確符號名命中優先於整檔路徑命中，
     避免搜 `user` 時 `user_service.py` 整檔節點靠 in_degree 蓋過真正叫 `user` 的符號。
  2. `topology.in_degree` 降冪（被呼叫越多越前面）。**fail-soft**：節點 `topology`
     可能為 `None`（見 node_view.py），此時 `in_degree` 視為 0，不得拋例外。
  3. `node_id` 字典序（決定性 tie-break）。
- **上限**：取前 `limit` 筆（預設 20，可由參數調整）。
- 結果每筆附 `match_kind`，讓呼叫者看得出是名稱命中還是路徑命中。
- **回傳**：
  ```json
  {
    "query": "...",
    "total_matched": 37,
    "returned": 20,
    "results": [
      { "node_id": "...::foo", "name": "foo", "type": "function",
        "file": "pkg/x.py", "start_line": 12, "end_line": 40,
        "in_degree": 9, "match_kind": "name" }
    ],
    "freshness": { ... }   // 見 §5
  }
  ```
  `total_matched` 與 `returned` 並列，讓呼叫者知道是否被 `limit` 截斷。

### 4.2 `node(codebase_path, node_id)`

- 由 `by_id` 取單一節點視圖；找不到 → `{ "error": "node_id not found: ..." }`
  （並可附「用 search 找正確 node_id」提示）。
- **回傳**（直接利用既有視圖，callers/callees 一次到位）：
  ```json
  {
    "node_id": "...::foo",
    "name": "foo", "type": "function",
    "file": "pkg/x.py", "start_line": 12, "end_line": 40,
    "language": "python",
    "topology": { "in_degree": 9, "out_degree": 3, "topology_rank": 0.7,
                  "is_entry_point": false },
    "callers": [ { "node_id": "...::bar", "type": "calls" } ],   // 由 in_edges 映射
    "callees": [ { "node_id": "...::baz", "type": "calls" } ],   // 由 out_edges 映射
    "freshness": { ... }
  }
  ```
  - `callers` 由視圖的 `in_edges` 映射（`from_node_id` → `node_id`）。
  - `callees` 由視圖的 `out_edges` 映射（`to_node_id` → `node_id`）。
  - 每筆 caller/callee 可選附其 `file`/`start_line`（若對端 node_id 在 `by_id` 中
    可解析；無法解析者只回 node_id，fail-soft 不報錯）。

### 4.3 CLI 輸出（給人讀）

`locate_cmd` 是給人用的轉接，輸出**人可讀的純文字**（非 JSON envelope；AI 端走 MCP）：

- `the-door locate search <query> [--limit N]`：每筆一行，
  `<match_kind>  <file>:<start_line>  <node_id>  (in:<in_degree>)`，
  末行印 `matched M, shown K`。
- `the-door locate node <node_id>`：印節點位置一行，接 `callers:` 與 `callees:`
  兩段縮排清單。
- 錯誤（artifact 缺、node 不存在、query 空）→ 印錯誤訊息至 stderr、非零 exit。
- freshness 非 `fresh` 時，於輸出尾端印一行提示
  （如 `⚠ structure-view 可能過時（N 個檔已變動）；重跑 extract_structure 以更新`）。
- **不做 `--json` 旗標**（AI 需要結構化就走 MCP，CLI 專注人讀；YAGNI）。

---

## 5. 資料新鮮度（freshness）— 誠實限制做成軟訊號

每次查詢回應都帶 `freshness` 區塊。**只警告、不阻擋**。

### 5.1 計算來源

複用既有的過時偵測原語（無新機制）：`core/checklist.read_checklist(codebase_path)`
→ `stages.edge_residue.source_files`，格式 `{relpath: [mtime_ns, size]}`（由
`edge_residue` 工具於抽取鏈時寫入）。

### 5.2 邏輯

```
checklist = read_checklist(codebase_path)
sf = checklist?.stages?.edge_residue?.source_files
if sf is None:               -> { "status": "unknown", "reason": "no edge_residue fingerprint" }
else:
    changed = []
    for relpath, [mtime_ns, size] in sf:
        stat (root/relpath)
        if missing or st.mtime_ns != mtime_ns or st.size != size:
            changed.append(relpath)
    status = "stale" if changed else "fresh"
    -> { "status": status, "changed_files": changed[:20], "changed_count": len(changed) }
```

- 三態：`fresh` / `stale` / `unknown`。
- `unknown`（沒跑過 edge_residue、或 checklist 缺/壞）→ 照常回查詢資料，僅標未知。
- `changed_files` 截斷上限 20，避免回應被大量檔名淹沒；`changed_count` 給總數。

### 5.3 已知近似（誠實聲明，寫入文件）

freshness 比對的是「當前 source vs **edge_residue 蓋章當下**的 fingerprint」，
作為「structure-view 是否過時」的代理。正常抽取鏈中 `extract_structure` 與
`edge_residue` 時間相近，此代理足夠；文件會註明這是近似訊號、非精確保證。

---

## 6. 文件（硬性需求）

新增 `docs/locate-query.md`，並於 `CLAUDE.md` 的工具表加一列。文件**開頭**即標明：

> **這是 The Door 的輔助便利功能（secondary），非主打。** The Door 的主打是
> 功能語意翻譯（L1/L2/簡介/版本敘述）。本功能讓你順手用同一份產出做程式碼定位。

並明列兩條限制：

1. **資料非即時**：改碼後需重跑 `extract_structure`，定位資料才更新；查詢回應的
   `freshness` 會以軟訊號提示資料是否過時（含近似聲明，見 §5.3）。
2. **名稱比對、非語意搜尋**：`search` 比對 symbol 名稱與 node_id 子字串，
   不理解自然語言意圖。

CLAUDE.md 工具表新列（維持既有表格語氣）：

| `locate` MCP / `the-door locate` CLI | 輔助：對既有 structure-view 做 symbol 定位點查（search/node）。非主打、資料非即時。 |

---

## 7. 規模佐證（為何不需要資料庫）

實測 test-target `the-door-v170`（真實資料）：

- 412 files / 2782 nodes / 7481 edges / 3 regions。
- region artifact gzip 後共約 **260KB**（最大區 `the_door` 248KB / 2593 nodes）。

此量級下「解壓全部 region → 建記憶體表 → 掃描」為毫秒級，**load+scan 即足夠**，
不引入 SQLite/FTS5。（CodeGraph 的索引 DB 是為 10 萬+ 節點 monorepo 準備；若未來
真遇到超大標的再議，YAGNI。）

---

## 8. 測試

### 8.1 locator 核心（用既有 fixture）

fixture：`the_door/tests/fixtures/sample_codebases/python_simple/`（已含
`.the-door/structure-view/`）。**測試隔離鐵則**：任何會改動檔案/mtime/size 的測試
（freshness stale、artifact 不存在）必須先把 fixture 複製到 `tmp_path` 再操作，
**絕不可改動 committed fixture**（守 E2E fixture 只放 input 的慣例）。

- `search`：
  - 命中 name 子字串、命中 node_id 子字串各一例。
  - 排序＝in_degree 降冪（造一個高 in_degree 與一個低的，斷言順序）。
  - `match_kind` 優先：造一個叫 `user` 的高 in_degree 路徑命中節點（檔名含 user）與
    一個 name=`user` 的低 in_degree 節點，斷言 name 命中排在路徑命中之前。
  - `limit` 截斷：`total_matched > returned`，`results` 長度＝limit。
  - 空白 query → `error`。
  - 無命中 → `results: []`、`total_matched: 0`（非錯誤）。
- `node`：
  - 既有 node_id → callers 由 in_edges、callees 由 out_edges 正確映射。
  - 不存在的 node_id → `error`。
- artifact 不存在（指向無 structure-view 的暫存目錄）→ `error`。
- `freshness` 三態：
  - `fresh`：不改檔，斷言 status=fresh。
  - `stale`：改動 fixture 下某 source（或於暫存複本改 mtime/size）→ status=stale
    且 `changed_files` 含該檔。
  - `unknown`：移除/不存在 checklist.json → status=unknown。

### 8.2 轉接層煙霧測試

- MCP `locate_tool.execute({...})`：search 與 node 各一條，斷言回 `wrap` 後的
  envelope 結構、必要欄位存在。
- CLI `the-door locate`：以 click 測試 runner 跑 search 與 node 子指令，斷言
  exit 0 與關鍵輸出。

### 8.3 註冊接線

- 斷言 `mcp/server.py` 的 `TOOLS` 含 `locate`、dispatch 能路由。
- 斷言 `the-door locate --help` 可用（命令已註冊）。

---

## 9. 風險與緩解

| 風險 | 緩解 |
|---|---|
| node_id 格式被誤記為 `ClassName.method`（CLAUDE.md 舊述）而非真實 `file::symbol` | 已用真實 artifact 核實格式（§3.1）；測試直接用 fixture 真值，不臆造 node_id |
| 不慎重跑 ASTExtractor，破壞「零重抽取」鐵則 | locator 僅 import gzip/json/checklist，**不 import ASTExtractor**；以測試或 review 守住 |
| freshness 近似造成誤解 | §5.3 明確聲明＋文件註記，定位為軟訊號非保證 |
| 被當成主打功能對外溝通 | 文件與 CLAUDE.md 均標 secondary（§6） |

---

## 10. 交付清單

- `core/structure_view/locator.py`（新）
- `mcp/tools/locate_tool.py`（新）+ `mcp/server.py` 註冊（改）
- `cli/locate_cmd.py`（新）+ `cli/main.py` 註冊（改）
- `docs/locate-query.md`（新）+ `CLAUDE.md` 工具表一列（改）
- 對應測試（§8）

不動：models、extract_structure、契約版號、任何 gate、前端 viewer。
