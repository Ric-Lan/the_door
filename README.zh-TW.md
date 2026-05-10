[English](README.md) | 繁體中文

# The Door

把程式碼的「結構與變化」翻譯成功能語言圖形，讓不讀程式的人能直接驗核開發產出。

Vibe coding為技術主軸。以需求串聯整個開發。

> 翻譯方向：技術語言 → 功能語言。圖形不是裝飾，是驗核介面。

---

## 這是什麼

The Door 是一個命令列工具 + MCP Server + 本地 UI。它讀取程式碼，透過 LLM 翻譯成「功能語言」——用一般人的話描述系統能做什麼、改了什麼、有沒有異常。

**給誰用：** PM、專案經理、發布經理、QA、甲方——任何需要確認「開發產出是否符合承諾」但不讀程式碼的人。

**核心能力：**

| 能力 | 說明 |
|---|---|
| 功能翻譯 | 程式碼 → 功能語言圖形（互動式 + Mermaid fallback）+ 自然語言敘述 |
| 版本比對 | 兩個版本之間改了什麼，風險項目優先顯示 |
| 範圍驗核 | PM 定義 sprint 範圍 → 自動比對 → 標記超出範圍項目 |
| 漏洞掃描 | 依賴套件的已知 CVE，整合到功能圖形中 |
| 功能演進 | 多版本時間軸，追蹤功能從何時出現、改了幾次 |
| 疑義追蹤 | 發現異常 → 標記疑義 → 指派 → 解決（含超時升級） |
| 本地 UI | 瀏覽器工作台，互動式圖形，三層導覽（L1 → L2 → L3） |

---

## 一、簡易入門

### 前置需求

| 需求 | 說明 |
|---|---|
| **Python ≥ 3.10** | 必要。[python.org/downloads](https://www.python.org/downloads/) |
| **pip** | 隨 Python 一起安裝 |
| **osv-scanner** _(選配)_ | `the-door scan` 需要。安裝方式：`go install golang.org/x/vuln/cmd/osv-scanner@latest`，或從 [google.github.io/osv-scanner](https://google.github.io/osv-scanner/) 下載 |
| **Ollama** _(選配)_ | 使用本地 LLM 模式時需要。從 [ollama.com](https://ollama.com) 安裝 |

> **MCP 模式（無需 API key）**：還需要支援 MCP 的 AI 平台，例如 Claude Code 或 Kiro IDE。

---

### 沒有 API Key？用 AI 平台直接分析

如果你使用 **Claude Code**、**Kiro IDE** 或其他支援 MCP 的 AI 平台，不需要自備 API key——由平台的 AI 負責分析，The Door 只負責讀取程式碼與產生圖形。

**步驟：**

1. 安裝套件：
   ```bash
   pip install the-door
   ```

2. 在 AI 平台的 MCP 設定中加入 The Door：
   ```json
   {
     "mcpServers": {
       "the-door": {
         "command": "the-door",
         "args": ["mcp-serve"]
       }
     }
   }
   ```

3. 在 AI 平台中直接對話，例如：
   > 「幫我分析 `./my-project` 的 L1 功能圖」
   > 「比對 `./old` 和 `./new` 之間改了什麼」

AI 會透過 MCP 呼叫 The Door 的工具完成分析，結果直接回傳到對話中。
具體 AI 呼叫工具的序列，請參考 [`CLAUDE.md`](CLAUDE.md)。

---

### 有 API Key？自行驅動 CLI

### 安裝（一次性）

```bash
pip install the-door
the-door config init    # 建立設定檔，填入 LLM API key
```

> 設定檔位於 `~/.the-door/config.toml`，支援 OpenAI / Anthropic / Ollama（詳見[詳細操作 → LLM 設定](#llm-設定)）。

---

### 專案路徑說明

`<path>` 填入你要分析的專案目錄路徑。分析產物會自動存在該目錄下的 `.the-door/` 資料夾，不會污染原始碼。

> **差異分析的路徑限制**因使用方式而異（UI vs CLI vs MCP），詳見[詳細操作 → 差異分析路徑規則](#差異分析路徑規則)。

---

### 流程順序：分析 → 快照 → 比對

**差異分析需要兩個時間點的快照才能比對。** 建議的標準流程：

```
第一次（建立基準）：  the-door analyze ./my-project
                     ↓ 自動建立快照（存於 .the-door/snapshots/）

開發進行中…

第二次（有新版本後）：the-door analyze ./my-project
                     ↓ 自動建立新快照

比對兩次快照：        the-door diff ./my-project --baseline <上一版的 label 或 git tag>
```

> `the-door analyze` 每次執行都會自動建立快照，**不需要手動執行** `snapshot create`。  
> 若要比對兩個不同目錄（如 `old/` 和 `new/`），直接用 `the-door update` 即可，它會自動分析兩邊再比對。

---

### L1 功能總覽

**一鍵 L1 分析**——讀取專案，輸出所有功能的總覽圖與自然語言說明：

```bash
the-door analyze ./my-project
```

**一鍵 L1 差異分析**——比對兩個版本之間改了什麼，風險項目優先顯示：

```bash
# 方式一：兩個目錄直接比對
the-door update <old-path> <new-path>

# 方式二：用快照比對（需先執行過兩次 analyze）
the-door diff <path> --baseline v1.0
```

> 路徑限制依使用方式不同，詳見[詳細操作 → 差異分析路徑規則](#差異分析路徑規則)。

---

### L2 模組細節

**一鍵 L2 分析**——在瀏覽器工作台查看各功能的模組連動圖（需先完成 L1 分析）：

```bash
the-door ui ./my-project
```

> 開啟後點選左側任一功能節點，右側面板點「生成 L2」即可展開模組圖。

**一鍵 L2 差異分析**——比對後直接在 UI 查看 L2 層的變更細節：

```bash
the-door update <old-path> <new-path> && the-door ui <new-path>
```

> 差異模式下節點以顏色標示新增／修改／刪除，點選節點可查看 Before/After 詳情。

---

## 二、詳細操作

### LLM 設定

`the-door config init` 會在 `~/.the-door/config.toml` 建立設定檔。支援三種 provider：

```toml
# OpenAI（預設）
[provider]
default = "openai"
[provider.openai]
api_key = "sk-..."
model = "gpt-4o"

# 或 Anthropic
[provider]
default = "anthropic"
[provider.anthropic]
api_key = "..."
model = "claude-sonnet-4-20250514"

# 或 Ollama（本地模型，免費）
[provider]
default = "ollama"
[provider.ollama]
url = "http://localhost:11434"
model = "qwen3:8b"
```

環境變數 `THE_DOOR_OPENAI_KEY`、`THE_DOOR_ANTHROPIC_KEY`、`THE_DOOR_OLLAMA_URL` 優先於設定檔。

### 分析與渲染

```bash
the-door analyze <path>                    # 一鍵分析（AST + LLM + 漏洞掃描 + 自動快照）
the-door analyze <path> --provider ollama  # 指定 provider
the-door render <path>                     # 輸出 Mermaid 功能圖形
the-door estimate <path>                   # 預估 LLM 呼叫成本
```

### 本地 UI 工作台

```bash
the-door ui <path>                         # 啟動本地 UI server，自動開啟瀏覽器
the-door ui <path> --port 9000             # 指定端口（預設 8765）
the-door ui <path> --no-browser            # 不自動開啟瀏覽器
```

啟動後在 `http://127.0.0.1:8765` 開啟三欄工作台：

- **左側**：功能清單 / 變更清單（風險優先排序）
- **中央**：互動式圖形（Cytoscape.js，支援點選、縮放、拖曳）
- **右側**：詳情面板（Before/After、資料來源、信心標記）

支援三層導覽：L1 功能總覽 → L2 模組連動圖 → L3 原始碼節點圖。差異模式下顯示有顏色標示的變更節點。

### 差異分析路徑規則

差異分析接受兩個路徑（`old_path` / `new_path`），但三種使用方式的限制不同：

| 使用方式 | 需要絕對路徑 | 需在同一根目錄下 |
|---|---|---|
| **UI（瀏覽器工作台）** | 是 | **是**，兩個路徑都必須位於啟動 UI 時指定的專案根目錄下 |
| **CLI** (`the-door update`) | 否，相對路徑會自動轉換 | 否，可比對系統上任意兩個目錄 |
| **MCP 工具** | 否 | 否，可比對系統上任意兩個目錄 |

**UI 的路徑結構範例：**

```
C:\projects\my-app\          ← 啟動 UI 時指定的根目錄
├── v1\                      ← 舊版路徑（必須在根目錄下）
└── v2\                      ← 新版路徑（必須在根目錄下）
```

**CLI / MCP 範例（無此限制）：**

```bash
# 兩個完全不同位置的目錄也可以比對
the-door update C:\projects\old-app C:\projects\new-app
```

### 版本比對

```bash
# 兩個目錄比對（完整管線：分析 → 比對 → 報告）
the-door update <old-path> <new-path>
the-door update <old> <new> --scope sprint-12   # 搭配範圍驗核
the-door update <old> <new> --json               # JSON 格式
the-door update <old> <new> --render             # Mermaid 圖形
the-door update <old> <new> -o report.md         # 輸出到檔案

# 用快照比對
the-door diff <path> --baseline <ref>            # ref = git tag / SHA / date / label
```

### 快照管理

```bash
the-door snapshot create <path> --label "v2.1"
the-door snapshot list <path>
the-door snapshot prune <path>              # 清理舊快照
the-door snapshot prune <path> --dry-run    # 預覽
```

### 範圍驗核

```bash
the-door scope create sprint-12             # 建立範圍定義
the-door scope verify <path> --scope sprint-12
the-door scope list
```

### 疑義追蹤

```bash
the-door doubt list
the-door doubt assign <id> <assignee>
the-door doubt resolve <id> --as explained --reason "..."
the-door doubt escalate <id> --reason "..."
```

### 漏洞掃描

```bash
the-door scan <path>
the-door scan <path> --offline              # 離線模式
```

### 功能演進

```bash
the-door timeline <path>
the-door timeline <path> --render           # Mermaid gantt 圖形
the-door timeline <path> --feature <id>     # 單一功能演進
```

### MCP Server

```bash
the-door mcp-serve                          # 啟動 MCP Server（18 tools）
```

支援所有 MCP-compatible AI 工具（Claude Desktop、Cursor 等）直接呼叫。

## 架構

```
程式碼 → AST 結構提取（tree-sitter，305+ 語言）
       → 拓撲分析（依賴排序，純本地）
       → LLM 翻譯（功能識別 + 功能語言敘述）
       → 輸出驗證（schema + 語意檢查）
       → Mermaid 圖形 + JSON 報告
       → 本地 UI（互動式圖形工作台）
```

- **LLM-Centric：** 功能識別與翻譯由 LLM 執行，系統負責約束 LLM 的輸入與輸出
- **AI-Medium-Agnostic：** CLI + MCP Server 雙核心，任何能讀取本機檔案的 AI 媒介都能執行
- **Local-first：** 除 LLM 呼叫外，所有分析、儲存、渲染都在本地完成，不需要雲端帳號
- **信任架構：** LLM 不知道的就標記為不知道，禁止幻覺，信心標記可見

## 本地 UI API

`the-door ui` 啟動後提供 14 個本地 API 端點（僅綁定 `127.0.0.1`）：

| Method | Path | 說明 |
|---|---|---|
| GET | `/api/project` | 專案路徑與可用資料狀態 |
| GET | `/api/snapshots` | 版本快照列表 |
| GET | `/api/report/latest` | 最新版本比對報告 |
| POST | `/api/update` | 觸發版本比對管線 |
| GET | `/api/update/status/<job_id>` | 輪詢管線進度 |
| GET | `/api/doubts` | 疑義列表 |
| GET | `/api/timeline` | 時間軸分析結果 |
| GET | `/api/l1?version_id=<id>` | L1 功能圖形 ViewModel（可指定版本） |
| GET | `/api/diff?baseline=<id>&current=<id>` | 依 version ID 比對兩個快照 |
| GET | `/api/l2/<feature_id>` | L2 模組圖形 ViewModel |
| POST | `/api/l2/<feature_id>/generate` | 觸發 L2 LLM 生成 |
| GET | `/api/structure` | AST 結構原料 |
| GET | `/api/layer-explanation/<fid>/<layer>` | 層說明快取 |
| POST | `/api/layer-explanation/<fid>/<layer>/generate` | 觸發層說明 LLM 生成 |

## 技術棧

**執行環境需求：** Python ≥ 3.10。以下 Python 套件均由 `pip install the-door` 自動安裝。

| 元件 | 用途 | 授權 |
|---|---|---|
| tree-sitter-language-pack | AST 結構提取（305+ 語言） | MIT |
| networkx | 拓撲分析 | BSD-3 |
| jsonschema | 輸出驗證（Draft 2020-12） | MIT |
| mcp | MCP Server SDK | Apache 2.0 |
| click | CLI 框架 | BSD-3 |
| httpx | LLM API 呼叫 | BSD-3 |
| pathspec | `.gitignore` 風格的檔案過濾 | MPL-2.0 |
| tomli | TOML 設定檔解析（僅 Python < 3.11） | MIT |
| Cytoscape.js | 互動式圖形（本地打包，無 CDN） | MIT |
| osv-scanner | 漏洞掃描——**外部執行檔，需另行安裝**（見前置需求） | Apache 2.0 |

## 專案資料

分析產物存在目標專案的 `.the-door/` 目錄下：

```
.the-door/
├── snapshots/                    # 版本快照（JSON）
├── fingerprints/                 # 檔案指紋（智慧跳過用）
├── doubts/                       # 疑義記錄
├── l2-outputs/                   # L2 模組分析快取
│   └── <feature_id>.json
├── layer-explanations/           # 層說明快取
│   └── <feature_id>/
│       └── <layer>.json
├── structure.json                # AST 結構原料（the-door extract 產生）
├── scope-config.json             # 範圍驗核設定
├── retention-config.json         # 版本保留策略
└── update-report-<timestamp>.json # 版本比對報告
```

建議將 `.the-door/` 加入 `.gitignore`。

## 開發

```bash
git clone <repo>
cd the_door
pip install -e ".[dev]"
python -m pytest tests/ -x -q
```

526 tests（unit + property-based + integration），使用 pytest + Hypothesis。

## 授權

雙重授權模式：

- **社區版** — [AGPL-3.0](LICENSE)。免費使用與修改。若你散布修改版或以修改版提供網路服務，必須以相同條款開放原始碼。
- **商業版** — 若你需要在私有產品或閉源服務中使用 The Door，且不接受 AGPL-3.0 的開源義務，請透過 issue tracker 聯繫維護者取得商業授權。

## 文件

- [使用者指南](docs/USER-GUIDE.md) — 完整的使用說明
- [產品規格](docs/the-door-spec-v4.1.md) — 設計理念與架構決策
- [圖形語言規範](docs/phase-0a/) — L1/L2 圖形語言定義
- [前端規格](docs/frontend-local-version-viewer/spec.md) — 本地 UI 設計規格
