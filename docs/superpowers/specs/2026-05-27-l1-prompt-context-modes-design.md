# L1 Prompt Context Modes — Design

**Date:** 2026-05-27
**Status:** Draft — awaiting user review
**Scope:** Step A only. Step B (evidence schema) and Step C (OpenAPI/SQL parsers) explicitly deferred to a future "multi-signal fusion" spec.

---

## 1. Background

The Door 透過 LLM 把 AST 節點翻譯成非技術讀者能讀懂的 L1 feature 敘述。實測 v1.3.6 翻譯品質約 80/100；瓶頸不在 LLM 能力或 prompt 約束，而在於**輸入給 LLM 的脈絡量遠低於系統已抽取的資訊**。

### 1.1 Evidence — 現況稽核

`ASTExtractor` 已抽出每個節點的完整資訊（[`models.py:19-31`](../../the_door/src/the_door/models.py)）：

```python
@dataclass(frozen=True)
class ASTNode:
    node_id: str
    type: str           # function | class | method
    name: str
    file: str
    language: str
    decorators: list[str]
    parameters: list[str]
    return_type: str | None
    docstring: str | None
    comments: list[str]
```

但 `BatchReader._process_batch` 送進 LLM 的 prompt 只有 node_id 字串清單（[`batch_reader.py:256-259`](../../the_door/src/the_door/core/reading/batch_reader.py)）：

```python
prompt = json.dumps({
    "batch": batch_num,
    "nodes": node_ids,   # 僅 ID 列表
})
```

LLM 因此只能靠節點名稱猜業務意圖，無法看 signature、docstring、裝飾器、檔案路徑。`SourceReviewer` 雖然存在於 `core/reading/source_reviewer.py`，但未被 `BatchReader` 呼叫（grep 確認）。

### 1.2 為何此設計

把已抽取的 ASTNode 詳情直接序列化進 prompt，是「補完設計遺漏」而非「加新功能」。但為了控制 token 成本與保留向後相容路徑，引入**雙模式**：

- `detail` — 預設，送完整 ASTNode 序列化
- `minimal` — 維持原本只送 node_id 的行為，作為 opt-out fallback

---

## 2. Goals & Non-Goals

### Goals
- LLM 收到完整節點脈絡（signature、docstring、裝飾器、檔案路徑），翻譯品質從 ~80 提升至預期 ~90+
- 提供 `--minimal-context` CLI flag 作為 opt-out，保留原本行為作為 fallback
- 零 output schema 變動 — 既有 Feature / FeatureSummary / snapshot 結構不動，無 migration 成本
- 既有測試套件透過明確更新點即可跟上

### Non-Goals
- 不引入 `evidence: {code, api, data}` 分類結構（→ 未來 multi-signal spec）
- 不接入 OpenAPI / SQL schema / GraphQL parser（→ 未來 multi-signal spec）
- 不改 L1 輸出 schema 任何欄位
- 不修改 PruningEngine、TopologyAnalyzer、SnapshotStore 行為
- 不引入 retry / tiered escalation 機制（先單模式觀察，未來視資料再決定）

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

當 `context_mode == "detail"`，prompt JSON 結構：

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

欄位完全對映 `ASTNode` dataclass。空欄位（如 `docstring: null`、`comments: []`）保留，由 LLM 自行判讀「沒有就沒有」。

### 3.3 Minimal mode payload schema

當 `context_mode == "minimal"`，維持原本：

```json
{
  "batch": 1,
  "context_mode": "minimal",
  "nodes": ["OrderController.checkout", "PaymentService.charge"]
}
```

新增 `context_mode` 欄位便於 prompt 自我說明（見 §4）。

---

## 4. Prompt Updates

### 4.1 L1_SYSTEM_PROMPT 改動點

[`prompts.py:22`](../../the_door/src/the_door/core/llm/prompts.py) 目前說：

> 你會收到一組 AST 節點清單

改為：

> 你會收到一組 AST 節點。每個節點可能是「節點 ID 字串」（minimal 模式）或「包含 signature、docstring、裝飾器等完整資訊的物件」（detail 模式）。`context_mode` 欄位會明確告知。

### 4.2 新增的硬性規則（補強 §風格規則）

加入第 5 條：

> 5. **看到 docstring / comments / 裝飾器 / signature 時**：用它們**理解**功能在做什麼，但**不可**把這些內容直接複製或引用到 description / trigger_description 裡。輸出仍然是給非技術讀者看的白話敘述。

這條規則消滅一個明顯風險：LLM 看到 docstring 就直接抄進輸出，反而比 minimal 模式更糟。

### 4.3 輸出 schema 不變

L1_SYSTEM_PROMPT 的「輸出格式」section 完全不動。Feature 欄位、relations、unclassified、infrastructure 都維持現狀。

---

## 5. CLI Surface

### 5.1 Flag definition

加入 `analyze_cmd` 與 `update_cmd`：

```
--minimal-context     使用原本只送 node_id 的 prompt 模式（預設為 detail 模式，
                      會把節點 signature/docstring 等完整資訊送給 LLM 以提升翻譯品質）
```

### 5.2 status / next-action 影響

`the-door status` 與 next-action renderer 的輸出不需要顯示模式 — 模式是隱形的執行細節，使用者無需感知。但 `the-door analyze --help` 文字需更新。

### 5.3 MCP tool surface

`analyze_tool.py` 的 input schema 加入 optional：

```json
"context_mode": {
  "type": "string",
  "enum": ["detail", "minimal"],
  "default": "detail",
  "description": "..."
}
```

`extract_structure` MCP tool 不受影響（它不呼叫 LLM）。

---

## 6. Token Budget & Batch Splitting

### 6.1 Payload size 估算

minimal 模式單節點約 30-50 bytes。detail 模式單節點：
- 無 docstring：100-200 bytes
- 一般 docstring：300-600 bytes
- 大量 comments + 長 docstring：1000+ bytes

整體 payload 預估膨脹 **5-15 倍**。

### 6.2 既有 `_maybe_split` 機制

[`batch_reader.py:226-248`](../../the_door/src/the_door/core/reading/batch_reader.py) 的 `_maybe_split` 已實作遞迴折半邏輯，但目前在 minimal 模式下幾乎不觸發（payload 太小）。detail 模式下會頻繁觸發。

**需要修改**：`_maybe_split` 估算 payload 大小時，必須**用實際送出去的內容**而非 node_id 字串。具體做法：`_maybe_split` 改為接收 `context_mode`，內部依模式呼叫對應的序列化函式取得真實 payload 字串後再估算 token 數。不採「把已序列化的 payload 傳入」的做法，避免上游 caller 重複序列化造成雙倍成本。

### 6.3 MAX_BATCHES 上限

`MAX_BATCHES = 5` ([`batch_reader.py:21`](../../the_door/src/the_door/core/reading/batch_reader.py)) 維持不變。Detail 模式下更可能因 split 而觸發批次數上升 — overflow 節點仍走既有 unclassified 路徑，不引入新行為。

### 6.4 Token 成本顯式提示

`the-door analyze --help` 描述 `--minimal-context` flag 時，明確說明「節省 token 但翻譯品質會回到 v1.3.6 之前的水準」。讓使用者知道 trade-off。

---

## 7. Backward Compatibility & Migration

### 7.1 Output schema：零變動

Feature、FeatureSummary、L1Output、VersionSnapshot 結構完全不變。既有 snapshot 檔案無需 migration。

### 7.2 既有測試的衝擊

`tests/unit/core/reading/test_batch_reader.py` 中所有檢查 prompt 內容形如 `{"batch": ..., "nodes": [...]}` 的斷言，在 detail 模式下會失敗。需要：

- 既有測試明確 pass `context_mode="minimal"` 維持斷言不變
- 新增 detail 模式測試案例
- prompt-content 測試 ([`tests/unit/core/llm/test_prompts.py`](../../the_door/tests/unit/core/llm/test_prompts.py)) 加新條目驗證「看到 docstring 不可直接複製」規則出現在 prompt 中

### 7.3 MCP 向後相容

`analyze_tool` 收到沒有 `context_mode` 欄位的舊 caller 時，預設 `"detail"`。舊 caller 自動享有新模式，無顯式版本協商。

### 7.4 Regenerate path

[`batch_reader.py:138-150`](../../the_door/src/the_door/core/reading/batch_reader.py) 的 `regenerate` 方法也只送 source_nodes ID 列表，**同樣套用** detail / minimal 切換邏輯。否則 regenerate 出來的 feature 品質會跟初次分析不一致。

---

## 8. Testing Strategy

### 8.1 Unit tests — 新增

| 測試檔 | 新增測試案例 |
|---|---|
| `tests/unit/core/reading/test_batch_reader.py` | `test_detail_mode_sends_full_ast_node`、`test_minimal_mode_sends_node_ids_only`、`test_detail_mode_split_uses_serialized_payload` |
| `tests/unit/core/llm/test_prompts.py` | `test_prompt_mentions_both_context_modes`、`test_prompt_forbids_docstring_passthrough` |
| `tests/unit/cli/test_analyze_cmd.py` | `test_minimal_context_flag_parses`、`test_default_is_detail_mode` |
| `tests/unit/mcp/tools/test_analyze_tool.py` | `test_context_mode_optional_defaults_to_detail` |

### 8.2 Unit tests — 更新

既有 `test_batch_reader.py` 中所有檢查 prompt JSON shape 的測試，標註 `context_mode="minimal"` 維持原本斷言，避免無謂改動。

### 8.3 Integration / scenario test

`tests/scenarios/` 既有 v105 baseline 流程不需新增 scenario；但若有現有 scenario 檢查 batch_reader 輸出，需確認模式選擇。

### 8.4 Quality observation（非自動化）

正式發版前手動比對：
- 同一 codebase（test-target v105 v1.2.2）跑 detail vs minimal 兩種模式
- 用 eyeball 評估 description 是否仍堅守「禁實作細節」規則
- 確認 LLM 沒有把 docstring 直接抄進 description

無正式 quality metric — L1 翻譯品質本質是主觀，不引入自動化評分以免假精確。

---

## 9. Risks & Mitigations

| 風險 | 機率 | 緩解 |
|---|---|---|
| LLM 把 docstring / comments 直接複製進 description，反而違反非技術讀者規則 | 中 | §4.2 加 prompt 硬性規則 + §8.4 eyeball 驗收 |
| Token 成本上升超過預期 | 中 | `--minimal-context` 提供 opt-out；help 文字明示 trade-off |
| Payload 膨脹導致 `_maybe_split` 切太碎，超過 `MAX_BATCHES=5` 把節點丟進 unclassified | 中 | overflow 是既有機制，無新行為；但需在 release notes 提醒「detail 模式下大型 codebase 可能 unclassified 變多」 |
| 既有測試大量 break | 高 | 明確列入 §7.2 + §8.2 處理計畫，標 `context_mode="minimal"` 維持斷言 |
| Regenerate 與初次分析模式不一致 | 中 | §7.4 規定兩條路徑都套用模式切換 |
| 模式切換 plumbing 漏接（某條 entry path 沒傳 mode） | 低 | 所有 entry point 在 §3.1 流程圖明列；測試覆蓋每條路徑 |

---

## 10. Future Work (Out of Scope)

以下不在本 spec 範圍，未來合成單一「multi-signal fusion」spec 一起設計：

- **Evidence schema**：Feature 加入 `evidence: {code, api, data}` 分類結構，作為多信號的儲存形式
- **OpenAPI parser 整合**：把 `.yaml` / `.json` OpenAPI 規格抽出 endpoint，作為 evidence.api 來源
- **SQL schema parser 整合**：用 sqlglot 抽出資料表，作為 evidence.data 來源
- **Tiered prompt escalation**：根據 confidence 自動重試的分層策略（只在資料證明單模式不足時引入）

未來 spec 應在本 spec 落地、累積一段使用資料之後再設計，避免過早結構化。

---

## 11. Acceptance Criteria

- [ ] `the-door analyze` 預設走 detail 模式，LLM 收到的 prompt 包含 ASTNode 完整欄位
- [ ] `the-door analyze --minimal-context` 退回原本只送 node_id 行為
- [ ] `the-door update --minimal-context` 同樣支援
- [ ] MCP `analyze_tool` 接收 optional `context_mode`，預設 detail
- [ ] L1_SYSTEM_PROMPT 包含「看到 docstring 不可直接複製」硬性規則
- [ ] `_maybe_split` 基於實際 payload 大小切批，不再低估
- [ ] 既有 batch_reader 測試以 `context_mode="minimal"` 標註維持綠燈
- [ ] 新增 detail 模式測試覆蓋 prompt shape、split 行為、CLI flag、MCP schema
- [ ] Eyeball 驗收：test-target v105 v1.2.2 detail 模式翻譯品質 ≥ minimal 模式（主觀評估）
- [ ] Output schema 零變動，既有 snapshot 檔可直接讀取無 migration
- [ ] CHANGELOG 與 README 更新，標示 v1.4.x 引入 detail context 模式
