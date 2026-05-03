# The Door — 自我分析報告

> The Door 對自己的原始碼執行 `the-door extract`，以下是結果。

---

## 分析摘要

| 指標 | 數值 |
|---|---|
| 原始碼檔案 | 94 個（全部 Python） |
| AST 節點 | 459 個（函式、類別、方法） |
| 依賴邊 | 1,145 條（呼叫、import、繼承） |
| 拓撲批次 | 4 批 |
| 入口節點 | 0 個（CLI 工具，無 HTTP handler） |

---

## 模組結構

The Door 的原始碼分為三層：核心引擎（`core/`）、CLI 指令（`cli/`）、MCP 工具（`mcp/`），加上共用資料模型（`models.py`）。

### 核心引擎（core/）— 282 個節點

| 模組 | 節點數 | 職責 |
|---|---|---|
| `core/llm` | 45 | LLM 供應商抽象層（OpenAI / Anthropic / Ollama）+ 設定管理 |
| `core/extraction` | 44 | AST 結構提取（tree-sitter） |
| `core/pipeline` | 43 | 版本更新管線編排 + 報告渲染 + 分析管線核心函式 |
| `core/scope` | 38 | 範圍驗核 + 疑義追蹤（狀態機 + 持久化） |
| `core/reading` | 34 | 拓撲引導批次讀取引擎 + 敘事鏈 |
| `core/diff` | 31 | 版本快照 CRUD + Diff 計算 + Diff 渲染 |
| `core/validation` | 22 | 輸出驗證（schema + 4 項語意檢查） |
| `core/vulnerability` | 15 | 漏洞掃描（osv-scanner）+ 漏洞渲染 |
| `core/timeline` | 14 | 時間軸分析 + 版本保留策略 |
| `core/rendering` | 12 | Mermaid 渲染 + 共用工具 |
| `core/topology` | 11 | 拓撲分析（入度/出度/批次分配） |

### CLI 指令（cli/）— 35 個節點

11 個 Click 指令 + 子指令群組，對應 `the-door` 的所有功能。

### MCP 工具（mcp/）— 27 個節點

18 個 MCP tools + server 主程式 + dispatch 邏輯。

### 資料模型（models.py）— 85 個節點

所有 Phase 的 frozen dataclass + exception class，集中定義在單一檔案。

---

## 拓撲分析結果

### 最高入度節點（被最多其他節點依賴）

| 排名 | 節點 | 入度 | 說明 |
|---|---|---|---|
| 1 | `narrative_chain.py::append` | 81 | 敘事鏈追加（讀取引擎的核心操作） |
| 2 | `snapshot_store.py::SnapshotStore` | 28 | 版本快照儲存層 |
| 3 | `models.py::L1Output` | 15 | L1 輸出資料結構 |
| 4 | `doubt_store.py::DoubtStore` | 15 | 疑義持久化層 |
| 5 | `models.py::Feature` | 14 | 功能節點資料結構 |
| 6 | `models.py::CheckResult` | 14 | 驗證結果資料結構 |
| 7 | `models.py::FeatureRelation` | 13 | 功能關係資料結構 |
| 8 | `models.py::ASTNode` | 12 | AST 節點資料結構 |
| 9 | `ast_extractor.py::ASTExtractor` | 12 | AST 提取器 |
| 10 | `topology_analyzer.py::TopologyAnalyzer` | 12 | 拓撲分析器 |

**觀察：** `narrative_chain.py::append` 入度 81 遠超其他節點，反映敘事鏈是整個讀取引擎的核心資料結構。`models.py` 中的 dataclass 佔據多個高入度位置，符合「集中定義、到處引用」的設計。

### 批次分配

| 批次 | 節點數 | 說明 |
|---|---|---|
| Batch 2 | 115 | 高入度核心節點（models、store、engine） |
| Batch 3 | 115 | 中入度節點（renderer、verifier） |
| Batch 4 | 115 | 低入度節點（CLI 指令、MCP tools） |
| Batch 5 | 114 | 最低入度節點（helper、utility） |

> 沒有 Batch 1 節點，因為 The Door 是 CLI 工具，沒有 HTTP handler 或框架入口裝飾器。所有 CLI 指令透過 Click 的 `@click.command` 裝飾器註冊，但 Click 不在 `is_entry_point` 的判斷規則中（規則針對 web 框架入口）。

---

## 依賴關係特徵

| 指標 | 數值 |
|---|---|
| 總邊數 | 1,145 |
| 平均入度 | 2.5 |
| 平均出度 | 2.5 |
| 最高入度 | 81（narrative_chain::append） |
| 最高出度 | 9（SnapshotStore） |
| 零入度節點 | ~200（CLI 指令、MCP tools、頂層函式） |
| 零出度節點 | ~150（dataclass、exception、leaf function） |

---

## 完整結構 JSON

完整的 AST 結構原料 JSON（含所有節點、邊、拓撲資訊）存放在：

```
docs/self-analysis-structure.json    # 395 KB
```

這個 JSON 就是 The Door 的標準輸出格式——任何 LLM 都可以讀取它，搭配約束 prompt 生成功能語言圖形。

---

## 如何重現

```bash
cd the_door
the-door extract src/the_door -o ../docs/self-analysis-structure.json
```

或透過 Python API：

```python
from the_door.core.extraction.ast_extractor import ASTExtractor
from the_door.core.topology.topology_analyzer import TopologyAnalyzer

extractor = ASTExtractor()
result = extractor.extract("src/the_door")

analyzer = TopologyAnalyzer()
topology = analyzer.analyze(result.nodes, result.edges)

print(f"Files: {len(result.files)}")
print(f"Nodes: {len(result.nodes)}")
print(f"Edges: {len(result.edges)}")
print(f"Topology entries: {len(topology.entries)}")
```
