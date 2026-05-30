[English](README.md) | 繁體中文

# The Door

把程式碼的「結構與變化」翻譯成功能語言圖形，讓不讀程式的人能直接驗核開發產出。

> 翻譯方向：技術語言 → 功能語言。圖形不是裝飾，是驗核介面。

---

## 這是什麼

The Door 是一個命令列工具 + MCP Server + 本地 UI。它讀取程式碼，透過 LLM（或經由支援 MCP 的 AI 平台）翻譯成「功能語言」——用一般人的話描述系統能做什麼、改了什麼、有沒有異常。

**給誰用：** PM、專案經理、發布經理、QA、甲方——任何需要確認「開發產出是否符合承諾」但不讀程式碼的人。

**核心能力：**

| 能力 | 說明 |
|---|---|
| 功能翻譯 | 程式碼 → 功能語言圖形（互動式 + Mermaid fallback）+ 自然語言敘述 |
| 版本比對 | 兩個版本之間改了什麼，風險項目優先顯示 |
| 增量更新 | 只重新分析「source nodes 有變動」的功能——比對本身不呼叫 LLM |
| 範圍驗核 | PM 定義 sprint 範圍 → 自動比對 → 標記超出範圍項目 |
| 漏洞掃描 | 依賴套件的已知 CVE，整合到功能圖形中 |
| 功能演進 | 多版本時間軸，追蹤功能從何時出現、改了幾次 |
| 疑義追蹤 | 發現異常 → 標記疑義 → 指派 → 解決（含超時升級） |
| 本地 UI | 瀏覽器工作台，互動式圖形，三層導覽（L1 → L2 → L3） |
| Scope-aware 關聯邊 | 跨檔關聯邊帶 `resolution` 標籤（`scope_rule` / `import_alias` / `name_match` / `skipped_dynamic`），LLM 可區分高低信心邊，不再把所有裸名匹配同等對待 |
| **邊噪音投影** | LLM 收到的關聯邊已過濾高候選量噪音、動態 dispatch 邊聚合成 caller 散文 hint；snapshot 與 viewer 仍保留完整事實。 |
| **Onboarding 雙欄精靈** | 視覺化的「開門→分析→進入 Viewer」三段體驗，含即時 file-level 進度 feed | v1.4.7 |

---

## 安裝

```bash
pip install the-door
```

需 Python ≥ 3.10。選配：`osv-scanner`（漏洞掃描）、`ollama`（本地 LLM）。

---

## 三條起手路線

挑一條符合你情境的。第一條最安全——它會先盤點你的專案、告訴你**你**應該下哪條命令。

### 1. `the-door status` —— 不確定專案目前在什麼狀態時

```bash
the-door status ./my-project
```

它會回報專案是否分析過、原始碼是否有變動，並印出一個 **`Next:`** 區塊——明確告訴你下一條該跑的命令。冷啟動時先跑這個。

### 2. 透過 AI 平台用 MCP —— 不需要 API key

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

### 3. 直接驅動 CLI —— 你有自己的 LLM API key

```bash
the-door config init    # 一次性設定，填入 OpenAI / Anthropic / Ollama key
the-door analyze ./my-project
```

---

## 典型使用順序

### A. 第一次分析（建立基準）

```bash
the-door analyze ./my-project
```

跑完整 pipeline：AST 抽取 → LLM 功能識別 → 漏洞掃描 → 自動建立快照存於 `.the-door/snapshots/`。輸出尾巴會印一個 **`Next:`** 區塊告訴你下一步。

預設會把節點完整的 signature、docstring、decorators 送給 LLM 以提升描述品質。如果你 token 預算有限，加 `--minimal-context` 退回到只送 node_id 的舊模式：

```bash
the-door analyze ./my-project --minimal-context
```

### B. 程式碼改動後（增量更新——比對不需要 API key）

如果你已經有 baseline 快照、只想看「現在跟那個版本差什麼」：

```bash
the-door update --from-snapshot v1.0 ./my-project
```

重新抽取當前的 AST、跟 baseline 的持久化結構比對、把每筆變動歸給對應的功能。這一步是**純 AST + diff**——不呼叫 LLM、不需要 API key。第一次 `analyze` 之後的日常 loop 就用這條。

只想 CLI 看一下差異、不打算寫新快照？

```bash
the-door diff ./my-project --baseline v1.0
```

### C. 瀏覽器視覺化

```bash
the-door ui ./my-project
```

在 `http://127.0.0.1:8765` 打開三欄工作台：左 = 功能列表 / 變更列表（風險優先）、中 = 互動式圖形（Cytoscape.js）、右 = 詳細面板含 Before/After。三層導覽：L1 功能總覽 → L2 模組圖 → L3 source node 圖。

### D. 補既有快照缺失的結構檔

如果 `update --from-snapshot` 抱怨 baseline 沒有持久化 AST（通常是該快照建立時還沒有 structures cache），而你還留著當時的原始碼：

```bash
the-door extract --as-version v1.0 ./baseline-source
```

不需要 API key——這條命令重新抽取 AST、存到 `.the-door/structures/<vid>.json.gz`，之後 `update --from-snapshot` 就能正常跑。

---

## Snapshot 參考格式

任何吃 baseline 參數的命令／工具（`--baseline`、`--from-snapshot`、`inherit_from`）都接受以下五種格式：

| 格式 | 例 | 說明 |
|---|---|---|
| Snapshot label | `v1.0.0`、`my-baseline` | 你跑 `analyze` 時明確指定的 |
| Git tag | `v1.0.0` | 該快照當下 commit 上的 tag |
| 日期 | `2026-05-06` | 解析為「該日或之前」最新的一筆快照 |
| Commit SHA（≥7 字元） | `8de9b18` | |
| UUID | 完整 `version_id` | chain 多個工具呼叫時好用 |

Viewer 的版本選擇器優先用 `git_tags[0]` → `label` → `version_id`，所以你分享的 URL 通常是人類可讀的。

---

## 設定

`the-door config init` 會建立 `~/.the-door/config.toml`，支援 OpenAI / Anthropic / Ollama 三種 provider。環境變數 `THE_DOOR_OPENAI_KEY`、`THE_DOOR_ANTHROPIC_KEY`、`THE_DOOR_OLLAMA_URL` 優先於設定檔。

完整參考（每個命令、每個 flag、每個 API endpoint）見 [`docs/USER-GUIDE.md`](docs/USER-GUIDE.md)。

---

## 架構概覽（一句話）

```
程式碼 → AST 抽取（tree-sitter，305+ 語言）
       → 拓撲分析（相依排序，純本地）
       → [LLM 翻譯 OR 快取的 baseline 結構]
       → 輸出驗核 + Mermaid 圖 + JSON 報告
       → 本地 UI（互動式圖形工作台）
```

同一個前段、兩條後段路徑：LLM 路徑（首次分析或重分析）、增量路徑（比對當前 AST 對既有 baseline，不呼叫 LLM）。快照本地優先存放；唯一的網路呼叫是 LLM 本身。

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
