# The Door — 使用者指南

> 把程式碼的「結構與變化」翻譯成功能語言圖形，讓不讀程式的人能直接驗核開發產出。

---

## 誰適合用這個工具

- 產品經理（PM）：確認 feature 是否完成、有沒有超出範圍
- 專案經理（SPM）：追蹤開發方向有沒有跑掉
- 發布經理：上線前確認更新內容是否如工程師所述
- QA / PO：確認這次 build 包含哪些功能
- 甲方 / 上層：里程碑審閱，確認系統結構符合規劃

你不需要讀程式碼。The Door 會把程式碼翻譯成「功能語言」——用一般人的話告訴你系統能做什麼、改了什麼、有沒有異常。

---

## 第一次使用

### 1. 安裝

```bash
pip install the-door
```

需要 Python 3.10 以上。

### 2. 設定 LLM

The Door 需要 LLM 來「翻譯」程式碼。支援三種 provider，擇一設定即可。

```bash
the-door config init
```

這會在 `~/.the-door/config.toml` 建立預設設定檔。打開它，填入你的 API key：

**方式 A：OpenAI（預設）**

```toml
[provider]
default = "openai"

[provider.openai]
api_key = "sk-your-key-here"
model = "gpt-4o"
```

**方式 B：Anthropic**

```toml
[provider]
default = "anthropic"

[provider.anthropic]
api_key = "your-anthropic-key-here"
model = "claude-sonnet-4-20250514"
```

**方式 C：Ollama（本地模型，免費）**

先安裝 [Ollama](https://ollama.com)，然後：

```bash
ollama pull qwen3:8b
```

設定檔改為：

```toml
[provider]
default = "ollama"

[provider.ollama]
url = "http://localhost:11434"
model = "qwen3:8b"
```

> 也可以用環境變數代替設定檔：`THE_DOOR_OPENAI_KEY`、`THE_DOOR_ANTHROPIC_KEY`、`THE_DOOR_OLLAMA_URL`。環境變數優先於設定檔。

### 3. 第一次分析

把你的專案路徑丟給 The Door：

```bash
the-door analyze /path/to/your/project
```

這一個指令會自動完成所有事：
- 解析程式碼結構（支援 305+ 語言）
- 掃描已知漏洞
- 呼叫 LLM 翻譯成功能語言
- 建立版本快照

完成後你會看到功能總覽——用一般人的話描述這個系統能做什麼。

> 第一次分析會呼叫 LLM，會產生費用（API provider）或需要等待（本地模型）。工具會在呼叫前顯示預估成本，你可以確認後再繼續。加 `--yes` 跳過確認。

### 4. 看圖形

```bash
the-door render /path/to/your/project
```

輸出 Mermaid 文字，貼到任何支援 Mermaid 的地方（GitHub、GitLab、VS Code、Obsidian）就能看到功能圖形。

---

## 日常使用

### 版本比對：這次改了什麼

這是最常用的功能。當工程師說「我改了 A」，你可以自己驗證：

```bash
the-door update /path/to/old-version /path/to/new-version
```

輸出一份互動式報告，從上到下四層：
- **L0 摘要**：一句話結論（「新增 2 個功能、修改 1 個功能」）
- **L1 變更總覽**：哪些功能變了，風險項目排最前面
- **L2 細節**：每個功能的變更前後對比（預設收合，點擊展開）
- **L3 技術附錄**：完整 JSON 資料（預設收合）

常用選項：

```bash
# 輸出 JSON 格式（給程式消費）
the-door update old/ new/ --json

# 輸出 Mermaid 圖形
the-door update old/ new/ --render

# 搭配範圍驗核
the-door update old/ new/ --scope sprint-12

# 跳過時間軸分析（加快速度）
the-door update old/ new/ --skip-timeline

# 輸出到檔案
the-door update old/ new/ -o report.md
```

### 單版本分析

只看一個版本的功能結構：

```bash
the-door analyze /path/to/project
```

### 版本快照

每次 `analyze` 會自動建立快照。你也可以手動建立有標籤的快照：

```bash
the-door snapshot create /path/to/project --label "v2.1-release"
the-door snapshot list /path/to/project
```

### Diff 比對（用快照）

```bash
# 跟上一個快照比
the-door diff /path/to/project --baseline latest

# 跟特定標籤比
the-door diff /path/to/project --baseline v2.1-release

# 跟特定日期比
the-door diff /path/to/project --baseline 2026-04-01
```

---

## 範圍驗核

PM 可以事先定義「這個 sprint 應該包含哪些功能」，然後讓工具自動比對。

### 建立範圍定義

```bash
the-door scope create sprint-12
```

這會在 `.the-door/` 下建立一個 JSON 檔案，列出預期的功能清單。編輯它，填入這個 sprint 應該交付的功能。

### 執行驗核

```bash
the-door scope verify /path/to/project --scope sprint-12
```

結果會標記：
- ✓ 範圍內已完成
- ⚠ 超出範圍（工程師做了計畫外的事）
- ○ 範圍內未完成

### 追蹤疑義

發現 ⚠ 時，建立疑義追蹤：

```bash
the-door doubt list                              # 看所有疑義
the-door doubt assign <doubt-id> <assignee>      # 指派給工程師
the-door doubt resolve <id> --as explained --reason "..."  # 工程師回覆
```

疑義有超時升級機制——如果指派後太久沒回應，會自動升級。

---

## 漏洞掃描

```bash
the-door scan /path/to/project
```

掃描專案依賴的已知漏洞（CVE）。需要系統安裝 [osv-scanner](https://github.com/google/osv-scanner)。

```bash
# 離線模式（不連網）
the-door scan /path/to/project --offline
```

> `analyze` 和 `update` 指令已內建漏洞掃描，不需要額外執行。加 `--offline` 切換離線模式。

---

## 功能演進時間軸

查看功能在多個版本之間的演進：

```bash
the-door timeline /path/to/project
the-door timeline /path/to/project --render    # Mermaid 圖形
the-door timeline /path/to/project --feature <id>  # 單一功能詳細演進
```

### 版本清理

快照太多時可以清理：

```bash
the-door snapshot prune /path/to/project --dry-run  # 先看會刪什麼
the-door snapshot prune /path/to/project             # 執行清理
```

手動建立的快照和有 git tag 的快照不會被清理。

---

## MCP Server（給 AI 工具用）

如果你用 Claude Desktop、Cursor 或其他支援 MCP 的 AI 工具，可以直接透過 MCP 呼叫 The Door：

```bash
the-door mcp-serve
```

提供 18 個 MCP tools，AI 工具可以直接呼叫分析、比對、驗核等所有功能。

---

## 注意事項

### LLM 相關

- **分析結果取決於 LLM 品質。** API 模型（GPT-4o、Claude）通常比本地模型（Ollama）準確。本地模型免費但品質可能較低。
- **信心標記要看。** 標記為「信心低」的項目代表 LLM 不確定，需要人工確認。不要忽略這些標記。
- **每次分析會呼叫 LLM。** 會產生 API 費用。用 `the-door estimate` 先預估成本。已分析過且程式碼沒變的版本會自動跳過（指紋驗證），不會重複花費。
- **結果不是 100% 準確。** The Door 是輔助驗核工具，不是自動驗收系統。發現疑義時應該追問工程師，而不是直接下結論。

### 檔案與路徑

- 所有專案資料存在目標專案的 `.the-door/` 目錄下（快照、指紋、疑義記錄等）。
- 使用者設定存在 `~/.the-door/config.toml`。
- 範圍驗核設定存在專案的 `.the-door/scope-config.json`。
- 版本保留策略設定存在專案的 `.the-door/retention-config.json`。
- 建議將 `.the-door/` 加入 `.gitignore`（分析結果是本地產物，不需要版控）。

### 效能

- 大型專案第一次分析可能需要幾分鐘（取決於檔案數量和 LLM 回應速度）。
- 後續分析如果程式碼沒變，會自動使用快取（秒級完成）。
- `--skip-timeline` 可以跳過時間軸分析，加快 `update` 指令的速度。
- `--offline` 可以跳過線上漏洞資料庫查詢。

### 支援的程式語言

tree-sitter 支援 305+ 語言，涵蓋所有主流語言。不支援的語言會被標記為 `[不支援的語言]` 並跳過。

---

## 快速參考

| 場景 | 指令 |
|---|---|
| 第一次設定 | `the-door config init` |
| 分析專案 | `the-door analyze <path>` |
| 看圖形 | `the-door render <path>` |
| 版本比對（兩個目錄） | `the-door update <old> <new>` |
| 版本比對（用快照） | `the-door diff <path> --baseline <ref>` |
| 範圍驗核 | `the-door scope verify <path> --scope <name>` |
| 漏洞掃描 | `the-door scan <path>` |
| 功能演進 | `the-door timeline <path>` |
| 預估成本 | `the-door estimate <path>` |
| 啟動 MCP Server | `the-door mcp-serve` |
