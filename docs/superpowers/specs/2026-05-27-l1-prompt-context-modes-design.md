# L1 Prompt Context Modes + Multilingual ASTNode Enrichment — Design

**Date:** 2026-05-27
**Status:** Draft — awaiting user review
**Scope:** Single coherent ship — L1 LLM 收到所有支援語言的完整節點脈絡。Evidence schema 改造、OpenAPI / SQL parsers 等延後到未來「multi-signal fusion」spec。

---

## 1. Background

The Door 透過 LLM 把 AST 節點翻譯成非技術讀者能讀懂的 L1 feature 敘述。實測 v1.3.6 翻譯品質約 80/100。瓶頸由兩個**已抽出但被丟掉 / 根本沒抽**的設計遺漏組成，必須同時解決才有完整效益。

### 1.1 遺漏一：prompt 只送 node_id，丟掉 ASTNode 物件

`ASTExtractor` 已抽出每個節點的詳情（[`models.py:19-31`](../../the_door/src/the_door/models.py)）：

```python
@dataclass(frozen=True)
class ASTNode:
    node_id, type, name, file, language
    decorators, parameters, return_type, docstring, comments
```

但 `BatchReader._process_batch` 送進 LLM 的 prompt 只有 node_id 字串清單（[`batch_reader.py:256-259`](../../the_door/src/the_door/core/reading/batch_reader.py)）：

```python
prompt = json.dumps({"batch": batch_num, "nodes": node_ids})
```

LLM 因此只能靠節點名稱猜業務意圖。`SourceReviewer` 雖然存在於 `core/reading/source_reviewer.py`，但未被 `BatchReader` 呼叫（grep 確認）。

### 1.2 遺漏二：generic walker 不抽 ASTNode 詳情欄位

引進 codegraph（[`language_configs.py`](../../the_door/src/the_door/core/extraction/language_configs.py) 標頭與 [`.kiro/specs/multilang-node-extraction/spec.md`](../../.kiro/specs/multilang-node-extraction/spec.md)）的初衷是**多語言節點識別**。但只解決了「哪些 tree-sitter node 算 function/class」，沒解決「ASTNode 內容怎麼填」。

[`node_builder.py:370-499`](../../the_door/src/the_door/core/extraction/node_builder.py) 的 `_walk_config_driven` 每次建構 ASTNode 都只填 4 個欄位（node_id, type, name, file），其餘為 default：

```python
ASTNode(
    node_id=..., type=..., name=..., file=..., language=...,
    # parameters → []     return_type → None
    # decorators → []     docstring → None     comments → []
)
```

對應語言：**Java, Go, Rust, Ruby, PHP, C#** 共 6 種。Python 與 TypeScript/JavaScript 走專用 walker，已抽詳情。

### 1.3 兩個遺漏的耦合

| 只解決 | 結果 |
|---|---|
| 遺漏一 | 對 Python/TS 翻譯品質飆升，對其他語言只多了 file path。違背 codegraph 引入時的多語言初衷。 |
| 遺漏二 | 抽出來的詳情沒人讀，dead enrichment。 |

**兩者必須同 ship**。本 spec 的單位是「**L1 LLM 收到所有支援語言的完整節點脈絡**」這個完整產品宣告。

---

## 2. Goals & Non-Goals

### Goals
- LLM 收到完整節點脈絡（signature、docstring、裝飾器/註解、檔案路徑）
- 翻譯品質從 ~80 提升至預期 ~90+，對 LANGUAGE_CONFIGS 註冊的**所有**語言一致有效
- 提供 `--minimal-context` CLI flag 作為 opt-out（保留原行為作為 fallback）
- 延續 codegraph 引入的 config-driven 設計風格：`LanguageConfig` 宣告各語言詳情抽取規則，避免手寫多個重複抽取函式
- 零 L1 output schema 變動 — Feature / FeatureSummary / snapshot 結構不動，無 migration 成本

### Non-Goals
- 不引入 `evidence: {code, api, data}` 分類結構（→ 未來 multi-signal spec）
- 不接入 OpenAPI / SQL schema / GraphQL parser（→ 未來 multi-signal spec）
- 不改 L1 輸出 schema 任何欄位
- 不修改 PruningEngine / TopologyAnalyzer / SnapshotStore 行為
- 不引入 retry / tiered escalation 機制
- 不擴充 LANGUAGE_CONFIGS 的語言清單（沿用現有 8 種：python, typescript, javascript, java, go, rust, ruby, php, csharp）

---

## 3. Architecture

### 3.1 Mode flag flow

```
CLI (--minimal-context)
   │
   ▼
analyze_cmd / update_cmd
   │  context_mode: "detail" | "minimal"
   ▼
PipelineOrchestrator(..., context_mode=...)
   │
   ▼
BatchReader(..., context_mode=...)
   │
   ▼
_process_batch  ──┬── detail  → serialize_full_nodes(active_nodes)
                  └── minimal → list of node_ids
```

MCP `analyze` tool 同樣接收 optional `context_mode` 欄位（預設 `"detail"`）。

### 3.2 Detail mode payload schema

當 `context_mode == "detail"`：

```json
{
  "batch": 1,
  "context_mode": "detail",
  "nodes": [
    {
      "node_id": "OrderController.checkout",
      "type": "method",
      "name": "checkout",
      "file": "src/controllers/order_controller.py",
      "language": "python",
      "parameters": ["self", "cart_id: str", "user: User"],
      "return_type": "OrderResult",
      "decorators": ["@app.route('/orders/checkout', methods=['POST'])"],
      "docstring": "Process payment and create order from cart contents.",
      "comments": []
    }
  ]
}
```

欄位完全對映 `ASTNode` dataclass。空欄位（`docstring: null` / `comments: []`）保留，由 LLM 自行判讀。

### 3.3 Minimal mode payload schema

```json
{
  "batch": 1,
  "context_mode": "minimal",
  "nodes": ["OrderController.checkout", "PaymentService.charge"]
}
```

### 3.4 LanguageConfig 擴充（解遺漏二）

擴充 [`language_configs.py`](../../the_door/src/the_door/core/extraction/language_configs.py)：

```python
@dataclass(frozen=True)
class LanguageConfig:
    # 既有欄位（codegraph 引入時就有）
    function_types: frozenset[str] = field(default_factory=frozenset)
    method_types: frozenset[str] = field(default_factory=frozenset)
    class_types: frozenset[str] = field(default_factory=frozenset)
    container_types: frozenset[str] = field(default_factory=frozenset)

    # 新增（detail 模式 ASTNode 充實用）
    parameters_field: str | None = None
        # tree-sitter field name for parameters node, e.g. "parameters"
    return_type_field: str | None = None
        # tree-sitter field name for return type, e.g. "return_type"
    doc_comment_strategy: str | None = None
        # "preceding_line_comments" | "preceding_block_comment" | None
    doc_comment_types: frozenset[str] = field(default_factory=frozenset)
        # comment node types to scan, e.g. {"line_comment", "block_comment"}
    doc_comment_marker: str | None = None
        # optional prefix identifying doc comments (e.g. "///" for Rust/C#)
    annotation_types: frozenset[str] = field(default_factory=frozenset)
        # node types treated as annotation/attribute (e.g. {"attribute_item"} for Rust)
```

各語言對應規則（初步事實假設，實作階段以該語言 grammar 驗證並就地修正）：

| 語言 | parameters_field | return_type_field | doc_comment_strategy | doc_comment_types | doc_comment_marker | annotation_types |
|---|---|---|---|---|---|---|
| java | `parameters` | `type` | preceding_block_comment | `{block_comment}` | — | `{annotation, marker_annotation}` |
| go | `parameters` | `result` | preceding_line_comments | `{comment}` | — | — |
| rust | `parameters` | `return_type` | preceding_line_comments | `{line_comment, block_comment}` | `///` 或 `//!` | `{attribute_item}` |
| ruby | `method_parameters` | — | preceding_line_comments | `{comment}` | — | — |
| php | `formal_parameters` | `return_type` | preceding_block_comment | `{comment}` | `/**` | — |
| csharp | `parameter_list` | `returns` (近似) | preceding_line_comments | `{comment}` | `///` | `{attribute_list}` |

> 表中 field 名稱對照 codegraph commit `5aae9c4` 與官方 tree-sitter grammar。實作階段若某 field 在實際 grammar 不正確，**就地修正對照表，不擴大設計範圍**。

### 3.5 `_walk_config_driven` 改造

每個產出 ASTNode 的分支（class / method / function / orphaned method）改用統一的 enriched builder：

```python
def _build_enriched_node(node, cfg, file_info, kind, parent_class):
    return ASTNode(
        node_id=...,
        type=kind,
        name=...,
        file=file_info.path,
        language=file_info.language,
        parameters=_extract_parameters(node, cfg.parameters_field),
        return_type=_extract_return_type(node, cfg.return_type_field),
        decorators=_extract_annotations(node, cfg.annotation_types),
        docstring=_extract_doc_comment(node,
                                       cfg.doc_comment_strategy,
                                       cfg.doc_comment_types,
                                       cfg.doc_comment_marker),
        comments=[],   # generic 路徑暫不收一般 comments；只收 doc comment 進 docstring
    )
```

四個 `_extract_*` helper 為純函式，輸入 tree-sitter node + config 欄位，輸出對應型別。`comments` 維持 `[]` 以避免無關註解雜訊；只把 doc comment 抽進 `docstring`。

Python 與 TypeScript 走專用 walker，**不受 §3.4 / §3.5 改動影響**（既有抽取已足夠）。

### 3.6 影響範圍彙整

| 檔案 | 改動類型 |
|---|---|
| `core/reading/batch_reader.py` | 加 `context_mode` 參數 + `_process_batch` 分支 + `_maybe_split` 用實際 payload |
| `core/llm/prompts.py` | L1_SYSTEM_PROMPT 加說明 + 新硬性規則 |
| `core/extraction/language_configs.py` | 擴充 `LanguageConfig` + 6 語言對照表 |
| `core/extraction/node_builder.py` | `_walk_config_driven` 改用 enriched builder + 4 個 helper |
| `core/pipeline/pipeline_orchestrator.py` | 接收並轉發 flag |
| `cli/analyze_cmd.py` / `update_cmd.py` | 加 `--minimal-context` argparse |
| `mcp/tools/analyze_tool.py` | input schema 加 optional `context_mode` |
| 測試 | 新增 + 更新（見 §8） |

L1 output schema 不變。

---

## 4. Prompt Updates

### 4.1 L1_SYSTEM_PROMPT 改動點

[`prompts.py:22`](../../the_door/src/the_door/core/llm/prompts.py) 目前說：

> 你會收到一組 AST 節點清單

改為：

> 你會收到一組 AST 節點。每個節點可能是「節點 ID 字串」（minimal 模式）或「包含 signature、docstring、裝飾器/註解等完整資訊的物件」（detail 模式）。`context_mode` 欄位會明確告知。

### 4.2 新增的硬性規則（補強 §風格規則）

加入第 5 條：

> 5. **看到 docstring / comments / decorators / annotations / signature 時**：用它們**理解**功能在做什麼，但**不可**把這些內容直接複製或引用到 description / trigger_description 裡。輸出仍然是給非技術讀者看的白話敘述。

### 4.3 輸出 schema 不變

「輸出格式」section 完全不動。

---

## 5. CLI Surface

### 5.1 Flag definition

加入 `analyze_cmd` 與 `update_cmd`：

```
--minimal-context     使用原本只送 node_id 的 prompt 模式（預設為 detail 模式，
                      會把節點 signature/docstring 等完整資訊送給 LLM 以提升翻譯品質）
```

### 5.2 status / next-action 影響

模式對使用者隱形，無需 surface 在 status / next-action。`--help` 文字更新即可。

### 5.3 MCP tool surface

`analyze_tool.py` 的 input schema 加入 optional：

```json
"context_mode": {
  "type": "string",
  "enum": ["detail", "minimal"],
  "default": "detail"
}
```

`extract_structure` MCP tool 不受影響（它不呼叫 LLM）。

---

## 6. Token Budget & Batch Splitting

### 6.1 Payload size 估算

minimal 模式單節點約 30-50 bytes。detail 模式因語言充實程度而異：

| 語言群 | 預估單節點 bytes |
|---|---|
| Python / TS（原本就有完整詳情） | 300-1000+ |
| Java / C# / Rust / PHP（充實後） | 200-800 |
| Go / Ruby（充實後，doc comment 較短） | 150-500 |

整體 payload 預估膨脹 **5-15 倍**。

### 6.2 既有 `_maybe_split` 機制

`_maybe_split` 估算 payload 大小時，必須**用實際送出去的內容**而非 node_id 字串。具體做法：`_maybe_split` 改為接收 `context_mode`，內部依模式呼叫對應的序列化函式取得真實 payload 字串後再估算 token 數。不採「把已序列化的 payload 傳入」的做法，避免上游 caller 重複序列化造成雙倍成本。

### 6.3 MAX_BATCHES 上限

`MAX_BATCHES = 5` 維持不變。Detail 模式下更可能觸發 split，overflow 節點仍走既有 unclassified 路徑。

### 6.4 Token 成本顯式提示

`--help` 文字明示「`--minimal-context` 節省 token 但翻譯品質會回到 v1.3.6 之前的水準」。

---

## 7. Backward Compatibility & Migration

### 7.1 Output schema：零變動

Feature / FeatureSummary / L1Output / VersionSnapshot 結構完全不變。既有 snapshot 檔案無需 migration。

### 7.2 既有測試的衝擊

- `tests/unit/core/reading/test_batch_reader.py` 中檢查 prompt 內容為 `{"batch": ..., "nodes": [...]}` 的斷言，明確 pass `context_mode="minimal"` 維持原斷言。
- prompt-content 測試 ([`tests/unit/core/llm/test_prompts.py`](../../the_door/tests/unit/core/llm/test_prompts.py)) 加新條目驗證「看到 docstring 不可直接複製」規則出現在 prompt 中。
- `tests/unit/core/extraction/test_node_builder.py` 各語言用例（若有）的 ASTNode 斷言會擴張 — 充實後欄位不再是空 default。

### 7.3 MCP 向後相容

`analyze_tool` 收到沒有 `context_mode` 欄位的舊 caller 時，預設 `"detail"`。舊 caller 自動享有新模式。

### 7.4 Regenerate path

[`batch_reader.py:138-150`](../../the_door/src/the_door/core/reading/batch_reader.py) 的 `regenerate` 方法也只送 source_nodes ID 列表，**同樣套用** detail / minimal 切換邏輯。

---

## 8. Testing Strategy

### 8.1 Unit tests — 新增

| 測試檔 | 新增測試案例 |
|---|---|
| `tests/unit/core/reading/test_batch_reader.py` | `test_detail_mode_sends_full_ast_node`、`test_minimal_mode_sends_node_ids_only`、`test_detail_mode_split_uses_serialized_payload`、`test_regenerate_respects_context_mode` |
| `tests/unit/core/llm/test_prompts.py` | `test_prompt_mentions_both_context_modes`、`test_prompt_forbids_docstring_passthrough` |
| `tests/unit/cli/test_analyze_cmd.py` | `test_minimal_context_flag_parses`、`test_default_is_detail_mode` |
| `tests/unit/mcp/tools/test_analyze_tool.py` | `test_context_mode_optional_defaults_to_detail` |
| `tests/unit/core/extraction/test_node_builder.py` | 每個 LANGUAGE_CONFIGS 註冊語言（java/go/rust/ruby/php/csharp）至少一個用例：assert ASTNode 在充實後 `parameters` / `docstring` / `decorators`（依該語言慣例）至少有一個非空 |

### 8.2 Unit tests — 更新

既有 batch_reader prompt-shape 測試明確標 `context_mode="minimal"` 維持原斷言。

### 8.3 Per-language fixture

`tests/fixtures/multilang/` 新增 6 個迷你 source 檔（每語言一個含 doc comment + parameters + annotation 的最小函式），供 §8.1 最後一列驗證。

### 8.4 Quality observation（非自動化）

正式發版前手動比對：
- test-target v105 v1.2.2（Python 為主）跑 detail vs minimal，eyeball 比對描述品質
- 額外準備一個多語言 test target（Go + Rust 至少各一個檔案）驗證非 Python/TS 也受益

無自動化 quality metric — L1 翻譯品質本質主觀，不引入假精確指標。

---

## 9. Risks & Mitigations

| 風險 | 機率 | 緩解 |
|---|---|---|
| LLM 把 docstring / comments 直接複製進 description | 中 | §4.2 加 prompt 硬性規則 + §8.4 eyeball 驗收 |
| Token 成本上升超過預期 | 中 | `--minimal-context` 提供 opt-out；help 文字明示 trade-off |
| Payload 膨脹導致 `_maybe_split` 切太碎，超過 `MAX_BATCHES=5` | 中 | overflow 是既有機制；release notes 提醒「detail 模式下大型 codebase 可能 unclassified 變多」 |
| 既有測試大量 break | 高 | §7.2 + §8.2 標 `context_mode="minimal"` 維持斷言 |
| Regenerate 與初次分析模式不一致 | 中 | §7.4 規定兩條路徑都套用模式切換 |
| 模式切換 plumbing 漏接（某 entry path 沒傳 mode） | 低 | 所有 entry point 在 §3.1 流程圖明列；測試覆蓋每條路徑 |
| §3.4 對照表的 tree-sitter field name 對某語言不正確 | 中 | 實作階段以該語言 grammar 驗證、就地修正對照表；不擴大設計範圍 |
| 某語言 grammar 無 docstring/annotation 慣例（如 Ruby 無 annotation） | 低 | LanguageConfig 對應欄位設 None / 空集合即可，self-documenting |

---

## 10. Future Work (Out of Scope)

- **Evidence schema**：Feature 加入 `evidence: {code, api, data}` 分類結構
- **OpenAPI parser 整合**：把 `.yaml` / `.json` OpenAPI 規格抽出 endpoint 作為 evidence.api 來源
- **SQL schema parser 整合**：用 sqlglot 抽出資料表作為 evidence.data 來源
- **Tiered prompt escalation**：根據 confidence 自動重試的分層策略
- **擴充 LANGUAGE_CONFIGS 至更多語言**（Kotlin, Swift, Scala 等）

未來 spec 應在本 spec 落地、累積一段使用資料之後再設計，避免過早結構化。

---

## 11. Acceptance Criteria

- [ ] `the-door analyze` 預設走 detail 模式，LLM 收到的 prompt 包含 ASTNode 完整欄位
- [ ] `the-door analyze --minimal-context` 退回原本只送 node_id 行為
- [ ] `the-door update --minimal-context` 同樣支援
- [ ] MCP `analyze_tool` 接收 optional `context_mode`，預設 detail
- [ ] L1_SYSTEM_PROMPT 包含「看到 docstring 不可直接複製」硬性規則
- [ ] `_maybe_split` 基於實際 payload 大小切批，不再低估
- [ ] `LanguageConfig` 擴充欄位（parameters_field / return_type_field / doc_comment_* / annotation_types）就位
- [ ] `_walk_config_driven` 對 java / go / rust / ruby / php / csharp 6 種語言抽出至少 parameters + docstring（若該語言有慣例）+ annotations（若該語言有慣例）
- [ ] 既有 batch_reader 測試以 `context_mode="minimal"` 標註維持綠燈
- [ ] 新增 detail 模式測試覆蓋 prompt shape / split 行為 / CLI flag / MCP schema / 6 語言 ASTNode 充實度
- [ ] Eyeball 驗收：test-target v105 v1.2.2（Python）+ 多語言 fixture 跑 detail 模式，翻譯品質主觀評估 ≥ minimal 模式
- [ ] Output schema 零變動，既有 snapshot 檔可直接讀取無 migration
- [ ] CHANGELOG 與 README 更新，標示 v1.4.x 引入 detail context 模式 + 多語言 ASTNode 充實
