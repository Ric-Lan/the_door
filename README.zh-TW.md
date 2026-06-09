[English](README.md) | 繁體中文

# The Door

把程式碼的「結構與變化」翻譯成功能語言圖形，讓不讀程式的人能直接驗核開發產出。

> 翻譯方向：技術語言 → 功能語言。圖形不是裝飾，是驗核介面。

---

## 這是什麼

The Door 是一個命令列工具 + MCP Server + 本地 UI。由支援 MCP 的 AI 平台（Claude Code、Kiro…）驅動，它讀取程式碼、翻譯成「功能語言」——用一般人的話描述系統能做什麼、改了什麼、有沒有異常。

**The Door 不內建任何 LLM provider、不需要 API key。** 驅動它的 AI agent 就是 LLM：The Door 確定性地抽取程式碼結構，agent 產出自然語言層，The Door 負責持久化。見 [零 API key — 唯一路徑](#零-api-key--唯一路徑)。

**給誰用：** PM、專案經理、發布經理、QA、甲方——任何需要確認「開發產出是否符合承諾」但不讀程式碼的人。

**核心能力：**

| 能力 | 說明 |
|---|---|
| 功能翻譯 | 程式碼 → 功能語言圖形（互動式 + Mermaid fallback）+ agent 撰寫的自然語言敘述 |
| 版本比對 | 兩個版本之間改了什麼，風險項目優先顯示 |
| 增量更新 | 只重新分析「source nodes 有變動」的功能——比對本身是純 AST、不呼叫 LLM |
| 範圍驗核 | PM 定義 sprint 範圍 → 自動比對 → 標記超出範圍項目 |
| 漏洞掃描 | 依賴套件的已知 CVE，整合到功能圖形中 |
| 功能演進 | 多版本時間軸，追蹤功能從何時出現、改了幾次 |
| 疑義追蹤 | 發現異常 → 標記疑義 → 指派 → 解決（含超時升級） |
| Scope-aware 關聯邊 | 跨檔關聯邊帶 `resolution` 標籤（`scope_rule` / `import_alias` / `name_match` / `skipped_dynamic`），agent 可區分高低信心邊，不再把所有裸名匹配同等對待 |
| 邊噪音殘餘 | `edge_residue` MCP 工具過濾高候選量噪音、把動態 dispatch 邊聚合成 caller 級 hint（確定性、零 token）；snapshot 與 viewer 仍保留完整事實 |
| 本地 UI | 瀏覽器工作台，互動式圖形，三層導覽（L1 → L2 → L3），唯顯示 |

---

## 安裝

```bash
pip install the-door
```

需 Python ≥ 3.10。選配：`osv-scanner`（漏洞掃描）。

---

## 零 API key — 唯一路徑

The Door **沒有 LLM provider**、**沒有 `analyze` / `update` / `config` 命令**。每一個需要自然語言的步驟都由 AI agent 經 MCP 完成（agent-as-LLM）。只有一條路徑：

```
extract_structure  →  （agent 識別 L1 功能）  →  edge_residue  →  snapshot_write
```

`extract_structure` 與 `edge_residue` 確定性、純本地執行；agent 提供自然語言層；`snapshot_write` 持久化。一個 PreToolUse gate 強制這個順序：`edge_residue` 會蓋一份執行 checklist，gate 在 checklist 未蓋章／版本過期／要寫的 node 未被涵蓋時 deny `snapshot_write`。完整工具呼叫序列見 [`CLAUDE.md`](CLAUDE.md)。

---

## 兩條起手路線

### 1. `the-door status` —— 不確定專案目前在什麼狀態時

```bash
the-door status ./my-project
```

它會回報專案是否分析過、原始碼是否有變動，並印出一個 **`Next:`** 區塊——明確告訴你**你**的下一步。冷啟動時先跑這個。

### 2. 透過 AI 平台用 MCP —— 分析路徑

如果你用 **Claude Code**、**Kiro IDE** 或其他支援 MCP 的 AI 工具，分析由 AI 自己完成——The Door 只負責讀取程式碼、寫入結果。

在 AI 平台的 MCP 設定加上：

```json
{
  "mcpServers": {
    "the-door": { "command": "the-door", "args": ["mcp-serve"] }
  }
}
```

然後直接對 AI 講話：
> 「幫我分析 `./my-project` 的 L1 功能圖」
> 「比對 `./old` 和 `./new` 之間改了什麼」

AI 完整的工具呼叫序列見 [`CLAUDE.md`](CLAUDE.md)。

---

## 典型使用順序

### A. 第一次分析（建立基準）—— 由 agent 驅動

透過 MCP，請你的 AI agent 分析專案。它會跑 `extract_structure` → 識別 L1 功能 → `edge_residue` → `snapshot_write`，把快照存於 `.the-door/snapshots/`。不需要 API key、沒有 provider——agent 就是 LLM。

沒有 `the-door analyze` 命令；第一次分析一律由 agent 驅動。

### B. 程式碼改動後（增量更新）

請 agent 對 baseline 跑 `analyze_changes`，它只回傳「source nodes 有變動」的功能；agent 只重產那些功能、再以 `inherit_from` 呼叫 `snapshot_write`，未變動的功能自動繼承。比對本身是**純 AST**——不呼叫 LLM。

只想 CLI 看一下對某個舊快照的差異、不打算寫新快照？

```bash
the-door diff ./my-project --baseline v1.0
```

### C. 瀏覽器視覺化

```bash
the-door ui ./my-project
```

在 `http://127.0.0.1:8765` 打開三欄工作台：左 = 功能列表 / 變更列表（風險優先）、中 = 互動式圖形、右 = 詳細面板。三層導覽：L1 功能總覽 → L2 模組圖 → L3 source node 圖。Viewer 唯顯示——它讀取已持久化的快照，不呼叫任何 LLM。

### D. 補既有快照缺失的結構檔

如果 `analyze_changes` 抱怨 baseline 沒有持久化 AST（通常是該快照建立時還沒有 structures cache），而你還留著當時的原始碼：

```bash
the-door extract --as-version v1.0 ./baseline-source
```

不需要 API key——這條命令重新抽取 AST、存到 `.the-door/structures/<vid>.json.gz`，之後增量分析就能正常跑。

---

## Snapshot 參考格式

任何吃 baseline 參數的命令／工具（`--baseline`、`inherit_from`）都接受以下五種格式：

| 格式 | 例 | 說明 |
|---|---|---|
| Snapshot label | `v1.0.0`、`my-baseline` | `snapshot_write` 時明確指定的 |
| Git tag | `v1.0.0` | 該快照當下 commit 上的 tag |
| 日期 | `2026-05-06` | 解析為「該日或之前」最新的一筆快照 |
| Commit SHA（≥7 字元） | `8de9b18` | |
| UUID | 完整 `version_id` | chain 多個工具呼叫時好用 |

Viewer 的版本選擇器優先用 `git_tags[0]` → `label` → `version_id`，所以你分享的 URL 通常是人類可讀的。

---

## 架構概覽（一句話）

```
程式碼 → AST 抽取（tree-sitter，305+ 語言）
       → 拓撲分析（相依排序，純本地）
       → [agent-as-LLM 翻譯 OR 快取的 baseline 結構]
       → 輸出驗核 + Mermaid 圖 + JSON 報告
       → 本地 UI（唯顯示的圖形工作台）
```

同一個前段、兩條後段路徑：**agent-as-LLM 路徑**（首次分析或重分析，由你的 MCP agent 驅動）、**增量路徑**（比對當前 AST 對既有 baseline，不呼叫 LLM）。一切本地優先——The Door 不內建 provider、自身不發任何 LLM 網路呼叫。

> **終態 — 零 API key（丙案 / T5）。** The Door 曾內建選配的 LLM provider 與 `analyze` / `update` key-path，現已完全退場：沒有 provider、沒有 API key、沒有 provider 設定。唯一支援路徑是 agent-as-LLM，由一個 PreToolUse 執行序 gate 結構性強制。完整 campaign 歷程見 [CHANGELOG](CHANGELOG.md)。

---

## 授權

雙授權：

- **社群版** — [AGPL-3.0](LICENSE)。可自由使用與修改。若以網路服務方式對外提供修改版，必須以同樣條款開源你的修改。
- **商業版** — 若需在閉源產品或封閉服務中使用 The Door、不希望受 AGPL-3.0 copyleft 約束，請透過 issue tracker 聯繫維護者取得商業授權。

---

## 文件

- [Agent 指南（`CLAUDE.md`）](CLAUDE.md) —— 給支援 MCP 的 AI agent 看的完整 decision tree
- [使用者手冊](docs/USER-GUIDE.md) —— 每個命令、每個 flag
- [產品規格](docs/the-door-spec-v4.1.md) —— 設計理念與架構決策
- [圖形語言規格](docs/phase-0a/) —— L1 / L2 圖形語言定義
- [前端規格](docs/frontend-local-version-viewer/spec.md) —— 本地 UI 設計規格
