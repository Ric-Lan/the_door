[English](README.md) | 繁體中文

# The Door

把程式碼的「結構與變化」翻譯成功能語言圖形，讓不讀程式的人能直接驗核開發產出。

> 翻譯方向：技術語言 → 功能語言。圖形不是裝飾，是驗核介面。

**本 README 分兩部分：**

- **[第一部分 — 給使用者](#第一部分--給使用者)** —— The Door 是什麼、以及人會跑的命令。
- **[第二部分 — 給 AI agent](#第二部分--給-ai-agent)** —— 由 MCP 驅動的 agent 如何操作 The Door（唯一路徑、工具、gate）。權威完整指南是 [`CLAUDE.md`](CLAUDE.md)。

---

# 第一部分 — 給使用者

## 這是什麼

The Door 是一個命令列工具 + MCP Server + 本地 UI。由支援 MCP 的 AI 平台（Claude Code、Kiro…）驅動，它讀取程式碼、翻譯成「功能語言」——用一般人的話描述系統能做什麼、改了什麼、有沒有異常。

**The Door 不內建任何 LLM provider、不需要 API key。** 驅動它的 AI agent 就是 LLM：The Door 確定性地抽取程式碼結構，agent 產出自然語言層，The Door 負責持久化。（機制見[第二部分](#唯一路徑--零-api-key)。）

**給誰用：** PM、專案經理、發布經理、QA、甲方——任何需要確認「開發產出是否符合承諾」但不讀程式碼的人。

## 核心能力

| 能力 | 說明 |
|---|---|
| 功能翻譯 | 程式碼 → 功能語言圖形（互動式 + Mermaid fallback）+ agent 撰寫的自然語言敘述 |
| 版本比對 | 兩個版本之間改了什麼，風險項目優先顯示 |
| 增量更新 | 只重新分析「source nodes 有變動」的功能——比對本身是純 AST、不呼叫 LLM |
| 範圍驗核 | PM 定義 sprint 範圍 → 自動比對 → 標記超出範圍項目 |
| 漏洞掃描 | 依賴套件的已知 CVE，整合到功能圖形中 |
| 功能演進 | 多版本時間軸，追蹤功能從何時出現、改了幾次 |
| 疑義追蹤 | 發現異常 → 標記疑義 → 指派 → 解決（含超時升級） |
| 功能詳細面板 | 單一功能鑽研：觸發描述、信心理由、source node 清單——viewer 單版本模式可見 |
| Scope-aware 關聯邊 | 跨檔關聯邊帶 `resolution` 標籤（`scope_rule` / `import_alias` / `name_match` / `skipped_dynamic`），agent 可區分高低信心邊，不再把所有裸名匹配同等對待 |
| 邊噪音殘餘 | `edge_residue` MCP 工具過濾高候選量噪音、把動態 dispatch 邊聚合成 caller 級 hint（確定性、零 token）；snapshot 與 viewer 仍保留完整事實 |
| 本地 UI | 瀏覽器工作台，互動式圖形，三層導覽（L1 → L2 → L3），唯顯示 |

## 安裝

```bash
pip install the-door
```

需 Python ≥ 3.10。選配：`osv-scanner`（漏洞掃描）。

## 快速上手

**冷啟動、不確定專案目前在什麼狀態時，先跑這個：**

```bash
the-door status ./my-project
```

它會回報專案是否分析過、原始碼是否有變動，並印出一個 **`Next:`** 區塊——明確告訴你**你**的下一步。（如果下一步是「分析」，那由 AI agent 執行——見[第二部分](#第二部分--給-ai-agent)。）

**把已分析的專案在瀏覽器視覺化：**

```bash
the-door ui ./my-project
```

在 `http://127.0.0.1:8765` 打開三欄工作台：左 = 功能列表 / 變更列表（風險優先）、中 = 互動式圖形、右 = 詳細面板。三層導覽：L1 功能總覽 → L2 模組圖 → L3 source node 圖。Viewer 唯顯示——它讀取已持久化的快照，不呼叫任何 LLM。

## 其他人會跑的命令

這些是純確定性、不需要 AI agent 的命令：

**CLI 看對某個舊快照的差異**（檢視、不改任何東西）：

```bash
the-door diff ./my-project --baseline v1.0
```

**補既有快照缺失的結構檔** —— 如果 `analyze_changes` 抱怨某個 baseline 沒有持久化 AST（通常是該快照建立時還沒有 structures cache），而你還留著當時的原始碼：

```bash
the-door extract --as-version v1.0 ./baseline-source
```

這條命令重新抽取 AST、存到 `.the-door/structures/<vid>.json.gz`，之後增量分析就能正常跑。不需要 API key。

> 兩條分析工作流——**第一次分析**（建立基準）與**增量更新**（程式碼改動後）——由 agent 驅動，不是 CLI 命令。沒有 `the-door analyze`。見[第二部分](#第二部分--給-ai-agent)。

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

# 第二部分 — 給 AI agent

> **你是一個支援 MCP 的 AI agent（Claude Code、Kiro…），正在驅動 The Door。這一段是你的起手 on-ramp。**
> **權威、完整的操作指南是 [`CLAUDE.md`](CLAUDE.md)** —— 呼叫任何工具前先讀它。它有完整 decision tree、每個工具的輸入／輸出 schema、以及增量／補件鏈。這一部分只是幫你定向；`CLAUDE.md` 才是單一真相來源。

## 唯一路徑 — 零 API key

The Door **沒有 LLM provider**、**沒有 `analyze` / `update` / `config` 命令**。每一個需要自然語言的步驟都由你（agent）經 MCP 完成（agent-as-LLM）。只有一條路徑：

```
extract_structure  →  （你識別 L1 功能）  →  edge_residue  →  snapshot_write
```

`extract_structure` 與 `edge_residue` 確定性、純本地執行；**你**提供自然語言層；`snapshot_write` 持久化。「我需要 API key」的框架在這裡是錯的——在本專案，**你就是 LLM**。

## MCP 設定

在 AI 平台的 MCP 設定加上：

```json
{
  "mcpServers": {
    "the-door": { "command": "the-door", "args": ["mcp-serve"] }
  }
}
```

（開發／從原始碼跑的變體、以及 `python -m the_door` 註記見 [`CLAUDE.md`](CLAUDE.md)。）

## 你會呼叫的工具

| 工具 | 何時用 |
|---|---|
| `system_status`（或 `the-door status`） | **永遠先跑。** 回報狀態 + `Next:` 區塊——權威下一步。 |
| `extract_structure` | 取得 nodes／edges／topology，然後**你**把 node 分組成 L1 功能。 |
| `edge_residue` | 落盤邊噪音殘餘**並蓋執行 checklist**（零 token、確定性）。`snapshot_write` 之前必跑。 |
| `snapshot_write` | 持久化你識別的 L1 功能。用 `inherit_from` 接續 baseline。 |
| `snapshot_patch` | 對既有 snapshot 原地補 `source_nodes`（不改 `version_id`）。 |
| `analyze_changes` | 增量：列出對 baseline 而言「受變動影響」的功能。 |

然後你就能直接回應自然語言請求：

> 「幫我分析 `./my-project` 的 L1 功能圖」
> 「比對 `./old` 和 `./new` 之間改了什麼」

完整的逐步鏈（單版本、補件、增量）與確切 JSON 形狀都在 [`CLAUDE.md`](CLAUDE.md)。

## 執行序 gate —— 什麼會擋你、為什麼

一個 PreToolUse gate **結構性強制**唯一路徑。你無法用講的繞過；你只能照順序跑完步驟來滿足它。

- **`edge_residue` 先跑。** 它蓋 `.the-door/checklist.json`（記錄已分析的 node 集、契約版本、以及每檔的 `(mtime, size)` 指紋）。
- **`snapshot_write` / `snapshot_patch` 會被 deny**，除非 checklist **版本當前**、你要寫的 `source_nodes` **被涵蓋**在已蓋章的 node 集內、且自蓋章後**沒有任何已分析檔案變動**（刪除／原地修改 → staleness deny）。如果你在 `edge_residue` 之後改了程式碼，請重跑 `edge_residue`。
- **原生 code-exec 被擋。** 繞過 MCP 工具的臨時 inline `python -c`／獨立 `.py` 腳本會被 deny；`python -m`（pytest／pip／the_door）、`pytest`、`pip`、`git`、`the-door` 放行。

當一個呼叫被 deny，gate 的 stderr 會告訴你下一步、並指回單一權威（`system_status`／`the-door status`）。那則訊息就是「下一步怎麼做」的真相來源。

## → 接著讀這個

[`CLAUDE.md`](CLAUDE.md) —— 完整的 agent decision tree、工具 schema、操作鏈。驅動 The Door 前先從那裡開始。

---

# 參考

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

## 授權

雙授權：

- **社群版** — [AGPL-3.0](LICENSE)。可自由使用與修改。若以網路服務方式對外提供修改版，必須以同樣條款開源你的修改。
- **商業版** — 若需在閉源產品或封閉服務中使用 The Door、不希望受 AGPL-3.0 copyleft 約束，請透過 issue tracker 聯繫維護者取得商業授權。

## 文件

- [Agent 指南（`CLAUDE.md`）](CLAUDE.md) —— 給支援 MCP 的 AI agent 看的完整 decision tree（權威 agent 進入點）
- [使用者手冊](docs/USER-GUIDE.md) —— 每個命令、每個 flag
- [產品規格](docs/the-door-spec-v4.1.md) —— 設計理念與架構決策
- [圖形語言規格](docs/phase-0a/) —— L1 / L2 圖形語言定義
- [前端規格](docs/frontend-local-version-viewer/spec.md) —— 本地 UI 設計規格
