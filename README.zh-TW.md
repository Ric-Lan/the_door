[English](README.md) | 繁體中文

# The Door

> 為非技術人士設計的程式碼可視化工具——讓你不需要讀程式碼，也能確認交付物是否符合承諾。

The Door 將程式碼轉譯成功能語言圖：系統在做什麼、兩個版本之間改了什麼、交付物是否符合需求。

**這個工具是設計給 AI 代為操作的，不需要你自己手動執行分析流程。** The Door 提供 MCP 伺服器；AI agent（Claude Code、Kiro 或任何支援 MCP 的平台）負責讀取程式碼、產生功能描述並儲存在本地端。你只需要打開瀏覽器查看結果，全程不需要 API key。

> **如何使用這份文件：** 閱讀本頁了解 The Door 的用途，然後將本頁連同 [`CLAUDE.md`](CLAUDE.md) 一起交給你的 AI agent，請它開始操作。

---

## 目錄

1. [技術棧](#1-技術棧)
2. [分析檔案的置放方式](#2-分析檔案的置放方式)
3. [AI 如何從頭開始](#3-ai-如何從頭開始)
4. [CLI 指令清單](#4-cli-指令清單)
5. [快照版本參照格式](#5-快照版本參照格式)
6. [架構摘要](#6-架構摘要)
7. [授權協議](#7-授權協議)
8. [文件索引](#8-文件索引)

---

## 1. 技術棧

| 層次 | 技術 |
|---|---|
| 程式碼抽取 | Python ≥ 3.10、tree-sitter（支援 305+ 語言） |
| MCP 伺服器 | `the-door mcp-serve`，由 AI agent 呼叫 |
| 本地 UI | Vanilla JS（無 bundler），由 `the-door ui` 啟動 |
| 儲存 | 目標專案內的 `.the-door/` 資料夾，純本地 |
| LLM | **由你的 AI agent 擔任** — The Door 不內建任何 LLM provider，也不需要 API key |

> ⚠️ **作業系統：目前僅在 Windows 上測試過。** macOS 與 Linux 尚未驗證，使用時請自行評估風險。

### AI 模型建議

| 模型 | 建議 |
|---|---|
| Claude Sonnet 4.x | ✅ 推薦 |
| Claude Opus 4.8 | ❌ **極度不推薦** — 傾向偏離 agent-as-LLM 路徑，會對不存在的 LLM provider 產生錯誤假設 |
| 其他支援 MCP 的模型 | 自行評估 |

---

## 2. 分析檔案的置放方式

The Door 分析你指定的目錄。若要追蹤同一專案的多個版本，請將每個版本分開存放為獨立目錄：

```
test-targets/
  my-app-v1.0/      ← v1.0 完整原始碼快照
  my-app-v1.1/      ← v1.1 完整原始碼快照
  my-app-v1.2/      ← ...
```

The Door 會將分析結果儲存在目標目錄內：

```
my-app-v1.0/
  .the-door/
    snapshots/      ← 持久化的 L1 功能快照
    structure-view/ ← 快取的 AST 產物
    checklist.json  ← 執行順序 gate 記錄
```

**注意事項：**
- 每個版本目錄應為完整、獨立的原始碼副本（非 git worktree 或 symlink）
- 不要移動或重命名 `.the-door/`，快照的 label、UUID 都存放在這裡
- 可以用不同的目標目錄搭配同一個正在運行的 `the-door ui` 實例

---

## 3. AI 如何從頭開始

> **如果你是正在閱讀這份文件的 AI agent：** 你的完整操作指引是 [`CLAUDE.md`](CLAUDE.md)，請在呼叫任何工具前先讀它。以下是操作摘要。

The Door 沒有 `analyze` 指令，也沒有內建 LLM provider。**你（agent）就是 LLM。** 分析結果全部持久化在本地，不發出任何 LLM 網路請求。

### 步驟 0 — MCP 設定

將以下設定加入你的 AI 平台 MCP config：

```json
{
  "mcpServers": {
    "the-door": { "command": "the-door", "args": ["mcp-serve"] }
  }
}
```

### 步驟 1 — 永遠先查狀態

```bash
the-door status ./my-project
```

回報專案目前的狀態，並印出 `Next:` 區塊——你的下一步確切指令。

---

### 路徑 A — 全新資料夾（從未分析過）

**適用情境：** `.the-door/` 不存在，這是第一次分析這個版本。

```
extract_structure  →  （你識別 L1 功能）  →  edge_residue  →  snapshot_write
```

1. 呼叫 `extract_structure` — 取得 L0 結構索引
2. 你讀取結構，按功能目的將 nodes 分組，識別出 L1 features
3. 呼叫 `edge_residue` — 蓋章（執行順序 gate 的前置要求）
4. 呼叫 `snapshot_write` — 持久化你識別的 L1 功能

---

### 路徑 B — 已有舊版快照，準備加入新版本

**適用情境：** 舊版已分析完畢，現在有新版原始碼放進另一個資料夾，想記錄新版並與舊版比對。

執行前，**請先向使用者確認要使用哪種分析模式：**

> 「我偵測到你已有 `[舊版 label]` 的快照，現在要分析新版本。請問要用哪種方式？
> - **B1 完整重新分析**：從頭識別所有功能，不參考舊版（適合架構大幅變動）
> - **B2 繼承分析 + diff**：只重寫有變動的功能，穩定功能自動沿用舊版描述，並可生成版本差異白話說明（推薦：省時、描述一致）」

收到使用者確認後再執行。

#### B1 — 完整重新分析

**原因：** 架構大幅重構、功能重組，舊版描述已無法對應新版結構。

流程與路徑 A 相同，`snapshot_write` 使用新的 `label`，不帶 `inherit_from`。

#### B2 — 繼承分析 + diff（推薦）

**原因：** 多數版本迭代只有部分功能變動。繼承模式確保穩定功能的描述不因重寫而漂移，同時節省分析時間。可額外補上版本差異的白話敘述（`version_narrative`），讓非技術人士直接看到「這個版本改了什麼」。

```
analyze_changes  →  （你只重寫受影響的功能）  →  edge_residue  →  snapshot_write (inherit_from)
                 →  （可選）snapshot_patch 補 version_narrative
```

1. 呼叫 `analyze_changes` — 取得受影響的 features 清單
2. 只重寫受影響的 features 描述（未變動的不重寫，自動繼承）
3. 呼叫 `edge_residue` — 重新蓋章
4. 呼叫 `snapshot_write` 並帶 `inherit_from=<舊版 label>` — 未變動 features 自動沿用
5. （可選）呼叫 `snapshot_patch` 寫入 `version_narratives` — 一句白話說明「這版做了什麼」

---

### 最後 — 開啟瀏覽器查看

```bash
the-door ui ./my-project
```

在 `http://127.0.0.1:8765` 開啟三欄式工作台。viewer 為純顯示模式，讀取持久化快照，不呼叫 LLM。

完整工具鏈、tool schema、gate 說明：[`CLAUDE.md`](CLAUDE.md)。

---

## 4. CLI 指令清單

以下指令為純本地執行，不需要 AI agent：

| 指令 | 用途 |
|---|---|
| `the-door status <path>` | 查詢專案狀態；印出 `Next:` 區塊指引下一步 |
| `the-door ui <path>` | 啟動本地 viewer（`http://127.0.0.1:8765`） |
| `the-door diff <path> --baseline <ref>` | CLI 比對兩個快照版本的差異 |
| `the-door extract --as-version <label> <path>` | 為既有快照補寫持久化 AST 結構 |
| `the-door mcp-serve` | 啟動 MCP 伺服器（由 AI 平台呼叫，無需手動執行） |

> 首次分析與增量分析兩個流程由 AI agent 透過 MCP 執行，不是 CLI 指令。

---

## 5. 快照版本參照格式

任何接受 baseline 參數的指令或工具（`--baseline`、`inherit_from`）都支援以下五種格式：

| 格式 | 範例 |
|---|---|
| 快照 label | `v1.0.0`、`my-baseline` |
| Git tag | `v1.0.0` |
| 日期 | `2026-05-06`（解析為該日期當天或之前最近的快照） |
| Commit SHA（≥7 碼） | `8de9b18` |
| UUID | 完整的 `version_id` |

---

## 6. 架構摘要

```
程式碼 → AST 抽取（tree-sitter，305+ 語言）
       → 拓撲分析（依賴排序，純本地）
       → [agent-as-LLM 翻譯 OR 快取 baseline 結構]
       → 輸出驗證 + JSON 報告
       → 本地 UI（純顯示式圖表工作台）
```

全流程在本地執行。The Door 不發出任何 LLM 網路請求。

---

## 7. 授權協議

雙授權：

- **Community Edition** — [AGPL-3.0](LICENSE)。免費使用與修改。若你以網路服務形式散佈或運行修改版本，必須依相同條款開放原始碼。
- **Commercial Edition** — 若需要在專有產品或閉源服務中使用 The Door 而不受 AGPL-3.0 著作權限制，請透過 issue tracker 聯繫維護者。

---

## 8. 文件索引

- [Agent Guide（`CLAUDE.md`）](CLAUDE.md) — AI agent 完整操作決策樹（agent 的唯一入口）
- [User Guide](docs/USER-GUIDE.md) — 所有指令與參數說明
- [Product Spec](docs/the-door-spec-v4.1.md) — 設計理念與架構決策
- [Diagram Language Spec](docs/phase-0a/) — L1/L2 圖表語言定義
- [Frontend Spec](docs/frontend-local-version-viewer/spec.md) — 本地 UI 設計規格
