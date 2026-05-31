# 資料模型契約驗證（Data-Model Contract Verification）設計

> Status: Design / 待 review
> Date: 2026-05-31
> 定位：旁路驗證層，不上 LLM 翻譯路徑、不改 L1/L2/L3。

## 1. 目標與動機

很多專案都有「資料模型」，只是以不同形式存在（SQL DDL、JSON、CSV、ORM model…）。
這份設計讓 The Door 能把「程式碼實際碰到的資料欄位」與「宣告的資料模型」做
**雙向契約對照**，標出落差：

- **寫入落差（write gap）**：程式碼寫出/產出一個 schema 沒有宣告的欄位 → 未記載的寫入。
- **覆蓋落差（coverage gap）**：schema 宣告了某欄位，卻沒有任何程式碼碰它 → 宣告未使用／待確認對應。
- **吻合（match）**：兩邊都有 → OK。

**主體始終是程式碼**；資料模型只是「用來對照的尺」。驗證是一份**獨立的差異性對比資料**，
**不是 LLM 翻譯的必須項** —— LLM 翻譯路徑（L1/L2/L3）完全不被本功能觸碰或改動。

### 1.1 取代關係（重要）

本設計**取代**先前記錄中「把 schema 變更變成新 L1 feature type『資料模型變更』」的舊想法。
資料模型在本設計中**永遠不會變成 L1 feature**，只作為驗證對照尺，藉此讓 L1/翻譯主路徑保持乾淨。

## 2. 核心原則

1. **The Door 定位、agent 推理、The Door diff。** native 抽取永遠停在簽章層。
2. **格式容忍度外包給 agent-as-LLM。** 不寫任何 framework-specific 的 schema parser
   （Django/Alembic/Knex/Prisma/SQL 方言一律不寫）。這延續 SCIP 被否決時確立的準則：
   不耦合上游/廠商、不擴大依賴、不產生新雜訊（見 `feedback_universal_translation_no_chasm`）。
3. **零新重依賴。** 不引入 `sqlglot` 等 SQL parser；不做資料流分析。
4. **旁路 + on-demand。** 不在每次 analyze 時跑；使用者明確要這份報告時才付成本。
5. **最小架構異動。** 以「追加 + 沿用既有」為主，照 `core/vulnerability/` 既有旁路分析層範式，
   不開平行子系統、不把契約 diff 混進 `diff_engine`（資料形狀不同，混入會造成膨脹）。

## 3. 為什麼不做 native 資料流（技術判斷）

The Door 現有 `ASTNode`（`the_door/src/the_door/models.py:19`）每節點僅抽：
`node_id / type / name / file / language / decorators / parameters(字串) / return_type / docstring / comments`；
Edges 僅 `calls / imports / extends / implements`。**不抽 function body、無欄位級讀寫追蹤、無資料流。**

> **已驗證的結構限制（影響切片策略）：** `ASTNode` **沒有行號/byte span 欄位**，
> `node_builder.py` 也未呼叫 tree-sitter 的 `start_point`/`end_point`。因此 The Door
> **無法**提供「函式 body 的行範圍切片」。Tier 1 因此改採**檔案層**交付（見 §4），
> agent 讀候選**檔案**、按節點名定位函式。行級切片需替 `ASTNode` 新增 span 欄位
> （會 ripple extraction/序列化/snapshot/MCP 輸出）→ 列為**非目標**（§11），守住最小架構異動。

要 native 看到「從什麼參數 OUTPUT 出什麼欄位」需建多語言靜態分析器（def-use、跨函式傳播）
＋ 持久化慣用法辨識（`User.objects.create(...)`、`INSERT INTO`…）→ 逐語言邏輯爆炸 ＋ framework 耦合
＋ 高雜訊，**三條準則同時破**。故「程式碼這邊碰了哪些欄位」的 body 級推理一律交給 agent-as-LLM。

## 4. 兩層架構

### Tier 0 — 本地候選定位器（零 token，預設執行）

- **輸入**：既有 `ExtractionResult`（nodes/edges）＋ file discovery 結果。**純唯讀消費，不改 extraction。**
- **邏輯**：純結構啟發式（config-driven，**config 放 `core/datamodel/datamodel_hints.py` 自有檔**，
  不掛 `language_configs.py`——那是 per-language scope rules，datamodel hints 是跨語言 name/dir 啟發式，混入會耦合過度）：
  - **schema 檔候選**：副檔名/路徑命中（`*.sql` / `*.csv` / schema-like `*.json` / ORM model 檔慣例目錄）。
  - **持久化疑似節點**：`name` / `decorators` / `return_type` / `file` 命中設定集
    （例：name 含 `save|create|insert|update|persist|repository|dao`；檔在 `models/`、`schema/` 目錄）。
  - 啟發式集合**小而明確**，全部列在 `datamodel_hints.py` 一份可讀 config，便於審視與擴充。
- **輸出**：`DataModelLocalization` —— 程式碼候選清單 `[{node_id, file, kind, flagged_reason}]`
  ＋ schema 檔候選清單。這就是「本地資料清洗」產物，**單獨即有價值**（指出哪裡該人工確認對應）。

### Tier 1 — agent 正規化 ＋ 契約 diff（on-demand、檔案層交付）

- The Door 把 Tier 0 圈出的**候選檔案路徑 ＋ 各檔內的候選節點名**交給 agent；
  agent 讀那些**檔案**、按節點名定位相關函式（無行級切片，見 §3 限制）。
- agent 產**兩份正規化欄位集**（agent-as-LLM，無需 API key）：
  - **宣告模型** `DeclaredModel`：`{ entity: [ {field, type} ] }`
  - **程式觸及模型** `CodeTouchedModel`：`[ {op: "write"|"read", entity, fields:[...]} ]`
- The Door 做**雙向契約 diff**（純結構運算，與 L1 diff 同肌肉但不同資料形狀）：
  - write gap / coverage gap / match（見 §1）。
- **輸出**：`ContractDiff` —— 三類條目的結構化報告。

> Tier 1 的兩份欄位集都由 agent 提供。The Door native 抽取（節點名）**可選**作 best-effort 交叉佐證
> （agent 回報的 entity/欄位若完全對不上任何候選節點 → 標低信心），但**非核心、非 v1 必做**，
> 不為它增加 `contract_verifier` 的複雜度。

## 5. 元件歸位（最小架構異動）

照 `core/vulnerability/`（scanner + renderer）旁路分析層範式，新增一個**同儕子套件**
`core/datamodel/`，其餘全沿用或各處 append 一個檔。

| 設計元件 | 現況 | 動作 |
|---|---|---|
| Tier 0 輸入 | `extraction/`（ExtractionResult / file_discovery） | **純沿用**（唯讀） |
| Tier 0 啟發式 config | 無（不掛 `language_configs.py`，避免耦合） | **新** `core/datamodel/datamodel_hints.py`（跨語言 name/dir 啟發式） |
| Tier 0 定位器 | 無 | **新** `core/datamodel/datamodel_localizer.py` |
| Tier 1 契約 diff | `diff/diff_engine.py`（L1 diff，資料形狀不同） | **新** `core/datamodel/contract_verifier.py`（不混入 diff_engine） |
| 報告呈現 | `vulnerability/vulnerability_renderer.py` 範式 | **新** `core/datamodel/datamodel_renderer.py` |
| 資料模型 | 無 | **新** `core/datamodel/models.py`（見 §6 dataclasses） |
| 報告持久化路徑慣例 | `diff/snapshot_store.py` 管 `.the-door/` | **沿用**路徑慣例，報告寫成 `.the-door/` 下獨立檔 |
| CLI | 每功能一 `*_cmd.py` + `main.py` dispatch | **新** `cli/verify_datamodel_cmd.py` ＋ `main.py` 註冊 |
| MCP | `mcp/tools/*.py` 一檔一工具 + `server.py` registry | **新** `localize_datamodel_tool.py` ＋ `verify_contract_tool.py` ＋ `server.py` 註冊 |

**淨新增**：`core/datamodel/`（5 檔：models / datamodel_hints / datamodel_localizer / contract_verifier / datamodel_renderer）
＋ CLI 1 檔 ＋ MCP 2 檔 ＋ `main.py`/`server.py` 各 append（註冊用）。**不改 extraction、不改 ASTNode、不改 language_configs。**
無平行子系統、無功能重複。

## 6. 資料模型（dataclasses，`core/datamodel/models.py`）

```python
@dataclass(frozen=True)
class DataModelCandidate:
    node_id: str            # 對應 ASTNode.node_id；schema 檔候選此欄為 ""
    file: str               # 候選檔案路徑（交付粒度為「檔」，非行範圍——見 §3 限制）
    kind: str               # "code_site" | "schema_file"
    flagged_reason: str     # 命中哪條啟發式（可讀字串）

@dataclass(frozen=True)
class DataModelLocalization:
    code_candidates: list[DataModelCandidate]
    schema_candidates: list[DataModelCandidate]

@dataclass(frozen=True)
class DeclaredField:
    field: str
    type: str | None        # agent 抓不到型別時為 None

@dataclass(frozen=True)
class CodeTouch:
    op: str                 # "write" | "read"
    entity: str
    fields: tuple[str, ...]

@dataclass(frozen=True)
class ContractEntry:
    entity: str
    field: str
    status: str             # "write_gap" | "coverage_gap" | "match"
    detail: str             # 可讀說明

@dataclass(frozen=True)
class ContractDiff:
    entries: tuple[ContractEntry, ...]
    # 摘要計數於 renderer 端衍生，不存欄位（避免冗餘狀態）
```

> 命名以「做什麼」為準（clean code）：`DataModelCandidate` 而非 `Item`；
> `flagged_reason` 而非 `flag`。frozen dataclass 保持值物件不可變，與既有 `ASTNode`/`Edge` 一致。

## 7. 介面

### 7.1 CLI

```
the-door verify-data-model <path>            # 預設只跑 Tier 0，輸出定位圖報告
the-door verify-data-model <path> --deep     # 印出 Tier 1 待 agent 處理的候選檔清單（不自動呼叫 LLM）
```

`--deep` **不自動跑 LLM**。它輸出「要交給 agent 的候選檔清單 + 指令」，符合 wizard 既有
「出指令卡交給 agent 跑」哲學。完成的 `ContractDiff` 由 MCP 路徑回寫報告。
命令成功時印 `Next:` 區塊（沿用 `cli/next_action_renderer.py` 慣例）。

### 7.2 MCP（agent-as-LLM，無需 API key）

- `localize_data_model(codebase_path)` → 回 `DataModelLocalization` 序列化（候選檔清單 ＋ 各檔內候選節點名）。
- `verify_data_model_contract(codebase_path, declared_model, code_touched_model)`
  → The Door 算 `ContractDiff`、寫 `.the-door/` 報告、回 diff 摘要。

鏡像既有 `extract_structure → agent → snapshot_write` 鏈。
工具 schema 與註冊照 `mcp/tools/snapshot_write_tool.py` ＋ `mcp/server.py` 既有寫法。

### 7.3 Viewer

**v1 不做**（YAGNI）。先 CLI + 報告檔，之後再評估是否加 Viewer 層。

## 8. 持久化

報告寫到 `.the-door/` 下獨立檔（如 `.the-door/datamodel/contract-<timestamp>.json`），
**不掛進 snapshot、不進 L1**。沿用 `snapshot_store.py` 既有的 `.the-door/` 根目錄解析，
不新增持久化框架。

## 9. 錯誤處理

- **無候選**（Tier 0 命中 0）：正常輸出空定位圖 ＋ 提示「未偵測到資料模型觸點」，非錯誤。
- **agent 回傳格式不合**（Tier 1 缺欄位/型別錯）：在 `verify_data_model_contract` 邊界驗證，
  回明確錯誤訊息（照 `analyze_tool` 邊界驗證慣例），不寫半截報告。
- **schema 檔讀取失敗**：該檔標記為 skipped 並列入報告 meta，不中斷整體。

## 10. 測試策略（TDD，100% coverage 紀律）

逐單元紅→綠，每單元可獨立測試：

1. **`datamodel_localizer`**：給定 fixture `ExtractionResult`（含命中/不命中節點 + 各類 schema 檔），
   斷言候選清單與 `flagged_reason` 正確；含「零命中」邊界。
2. **`contract_verifier`**：給定兩份正規化欄位集 fixture，斷言三類 `ContractEntry`
   （write_gap / coverage_gap / match）分類正確；含空輸入、entity 不對齊等邊界。
3. **`datamodel_renderer`**：給定 `ContractDiff`，斷言報告文字/JSON 結構與摘要計數。
4. **CLI `verify_datamodel_cmd`**：parse + 預設 Tier 0 路徑 + `--deep` 候選檔清單輸出 + 錯誤路徑。
5. **MCP 兩工具**：邊界驗證（合法/缺欄位）＋ 回傳 envelope 形狀 ＋ 報告寫入。
6. **`datamodel_hints` config**：啟發式集合被 localizer 正確讀取（命中/不命中）。

fixture 只放輸入（ExtractionResult / 欄位集 / schema 檔內容），主程式產結果、test 斷言結果
（沿用 `feedback_e2e_fixture_input_only`）。

## 11. 邊界 / 非目標

- 不做資料流分析、不走進 body AST（body 由 agent 自行讀候選**檔案**）。
- **不替 `ASTNode` 新增行號/span 欄位、不改 extraction**：行級 body 切片是未來最佳化、本版非目標
  （現以檔案層交付替代，見 §3）。
- 不寫 framework-specific schema parser；格式容忍度是 agent 的事。
- 不改 L1/L2/L3、不上翻譯路徑、不掛 snapshot、不改 `language_configs.py`。
- 不自動呼叫 LLM（CLI `--deep` 只出候選檔清單與指令）。
- native 節點名交叉佐證為 best-effort 選配，非 v1 必做。
- Viewer 呈現 v1 不做。
- v1 schema 來源：SQL DDL / JSON / CSV / ORM model（皆由 agent 正規化）。

## 12. 開放問題 / 未來最佳化

- 報告檔命名/格式（JSON vs markdown）細節留待 plan。
- Tier 0 啟發式初始集合的確切清單留待 plan（spec 只定原則：小、明確、config-driven）。
- **未來最佳化（非 v1）**：
  - **增量收斂**：把驗證綁到既有 `diff/feature_attribution`，只重驗變動的功能以省 token。
    v1 維持 on-demand 全量定位，避免提早耦合 snapshot/diff。
  - **行級切片**：替 `ASTNode` 加 span 欄位以改用 body 切片（取代檔案層交付）降 token。
    需 ripple extraction/序列化/snapshot，自成一條 spec。
