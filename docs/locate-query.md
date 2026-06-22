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
