# The Door

把程式碼的「結構與變化」翻譯成功能語言圖形，讓不讀程式的人能直接驗核開發產出。

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

## 快速開始

```bash
pip install the-door
the-door config init          # 建立設定檔，填入 LLM API key
the-door analyze ./my-project # 分析專案，輸出功能總覽
the-door ui ./my-project      # 在瀏覽器中開啟互動式工作台
```

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

## 主要指令

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

`the-door ui` 啟動後提供 13 個本地 API 端點（僅綁定 `127.0.0.1`）：

| Method | Path | 說明 |
|---|---|---|
| GET | `/api/project` | 專案路徑與可用資料狀態 |
| GET | `/api/snapshots` | 版本快照列表 |
| GET | `/api/report/latest` | 最新版本比對報告 |
| POST | `/api/update` | 觸發版本比對管線 |
| GET | `/api/update/status/<job_id>` | 輪詢管線進度 |
| GET | `/api/doubts` | 疑義列表 |
| GET | `/api/timeline` | 時間軸分析結果 |
| GET | `/api/l1` | L1 功能圖形 ViewModel |
| GET | `/api/l2/<feature_id>` | L2 模組圖形 ViewModel |
| POST | `/api/l2/<feature_id>/generate` | 觸發 L2 LLM 生成 |
| GET | `/api/structure` | AST 結構原料 |
| GET | `/api/layer-explanation/<fid>/<layer>` | 層說明快取 |
| POST | `/api/layer-explanation/<fid>/<layer>/generate` | 觸發層說明 LLM 生成 |

## 技術棧

| 元件 | 用途 | 授權 |
|---|---|---|
| tree-sitter-language-pack | AST 結構提取（305+ 語言） | MIT |
| networkx | 拓撲分析 | BSD-3 |
| jsonschema | 輸出驗證（Draft 2020-12） | MIT |
| mcp | MCP Server SDK | Apache 2.0 |
| click | CLI 框架 | BSD-3 |
| httpx | LLM API 呼叫 | BSD-3 |
| Cytoscape.js | 互動式圖形（本地打包，無 CDN） | MIT |
| osv-scanner | 漏洞掃描（選配） | Apache 2.0 |

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

MIT

## 文件

- [使用者指南](docs/USER-GUIDE.md) — 完整的使用說明
- [產品規格](the-door-spec-v4.1.md) — 設計理念與架構決策
- [圖形語言規範](docs/phase-0a/) — L1/L2 圖形語言定義
- [前端規格](docs/frontend-local-version-viewer/spec.md) — 本地 UI 設計規格
