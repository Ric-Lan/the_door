# Edge Noise Projection

**Date:** 2026-05-29
**Status:** Draft — pending user approval
**Builds on:** v1.4.5（Scope-Aware Edge Resolution，4 種 resolution 標籤已上線）
**Defers:** instance-binding walker（Q1.A）、type-annotation tracking（Q1.B）、chained-attribute receiver（Q1.C）

---

## 1. Goal — 產品宣告

**把 edge 噪音過濾從「LLM 自己看 resolution 標籤判斷」升級為「prompt 邊界做投影過濾」**：

- LLM 收到的 edges 只剩高信心 + 有限度的低信心 + 一條 aggregate hint
- 高 fanout 的 `name_match` / `skipped_dynamic` 邊**不再進 prompt**，改成 caller 級散文 hint
- Snapshot 仍保留完整事實，viewer 不受影響
- 0 schema 變動，0 新依賴，0 前端工作

對使用者的可觀察效果：
1. L1 description 不再出現「廣泛使用」「重度依賴」這類由噪音邊誘導的措辭
2. 對通用方法名（write / get / run / handle）的假連結消失
3. 工程師若需要，仍可在 viewer 看完整邊集

---

## 2. Background — 現況問題

### 2.1 v1.4.5 已解的部分

Scope-Aware Edge Resolution 把 `Edge.resolution` 分成 4 種：
- `scope_rule` / `import_alias` — 高信心
- `name_match` — 裸名 fallback，低信心
- `skipped_dynamic` — 動態 dispatch 候選，不可斷言

Dogfood §7.2 數據：
| Target | name_match | skipped_dynamic | gate |
|---|---|---|---|
| `the_door/src/the_door` | 28.8% | 0% | PASS |
| `test-targets/the-door-v105` | 30.8% | 0% | PASS |

### 2.2 剩餘問題：標籤救不了 attention budget

L1 prompt（`core/llm/prompts.py:37-46`）已教 LLM「`name_match` 持保守態度、`skipped_dynamic` 不要斷言」。但：

- LLM 看到 12 條 `write` name_match 邊，**注意力分配無法真正歸零**
- 「忽略」這個指令在資料量大時脆弱
- 通用方法名（write / get / set / run / handle）一個 call 可以對應 5–30 個候選 → fanout 爆炸 → 即使每條都標 `name_match`，整體仍誘導 LLM 寫出假依賴
- Ruby/Python 含 `method_missing` / `__getattr__` 的 target 上線後，`skipped_dynamic` 也會炸同樣 fanout

### 2.3 為什麼不擴大解析（A/B/C 都繞遠路）

A) instance-binding、B) type-annotation、C) chained-attribute — 三條都是 **擴大解析事實量**。即使做到 100% 覆蓋，仍有「receiver 我們真的不知道」的剩餘比例。

對「給非專業 LLM 翻譯」這個基準，槓桿不在事實量，**在 prompt 邊界控制給 LLM 看什麼**。

---

## 3. Non-Goals

- ❌ 擴大 receiver 解析（A/B/C 都不做，另開 spec）
- ❌ 改 `Edge` / `VersionSnapshot` schema 欄位（只在現有 `resolution` 加一個值）
- ❌ 引入 type inference / SCIP / LSP
- ❌ 改 viewer 前端（顯示視為 `name_match` 同等，加 tooltip 即可，0 改動）
- ❌ 改 minimal context mode（本來就無 edges）
- ❌ 改 diff 演算法（與 §6.4 同 bucket 策略並存）

---

## 4. Design — 架構

### 4.1 三層邊界（Clean-Code: Single Responsibility per layer）

| 層 | 職責 | 對 edge 做什麼 | 不做什麼 |
|---|---|---|---|
| **Extraction**（`edge_builder.py`） | 算結構性事實 | 候選照常解；fanout > N 時標 `name_match_ambiguous` | 不認識「哪些方法名是通用動詞」、不認識 prompt |
| **Snapshot**（`structure_serializer.py`） | 可追溯事實全集 | 全部邊照寫，含 ambiguous 標籤 | 不過濾 |
| **Projection**（`core/llm/edge_projection.py` 新檔） | prompt-input 認知負荷管理 | drop ambiguous；對 `skipped_dynamic` + ambiguous 聚合 aggregate hint | 不算 fanout、不持久化 |
| **Prompt**（`core/llm/prompts.py`） | 教 LLM 怎麼看 | 解釋新 resolution + aggregate hint 欄位 | 不過濾 |

關鍵原則：
- **Extraction 不認識 prompt**：閾值是純結構數，不查方法名清單
- **Projection 不認識 fanout 計算**：純消費 resolution 標籤 + 邊集，做投影
- **Snapshot 永遠是事實全集**：viewer 與 diff 不受 projection 影響

### 4.2 Schema 改動範圍

唯一改動：`Edge.resolution` 枚舉值多一個 `name_match_ambiguous`。

```python
# core/models.py（既有欄位，僅枚舉值擴張）
resolution: Literal[
    "scope_rule",
    "import_alias",
    "name_match",
    "name_match_ambiguous",  # 新增
    "skipped_dynamic",
]
```

- 0 新欄位（不加 `candidate_count`，可由 `_name_to_ids` 隨時推導）
- 0 新模型（CallSite 仍是 extraction-only tuple，不持久化）
- 0 新 CallSite-level metadata（aggregate hint 在 projection 即時算）
- 0 序列化版本變動（向後相容：舊 snapshot 反序列化時，未知值不會出現，因為新值只能由新版 EdgeBuilder 寫入）

### 4.3 Extraction 層改動

`edge_builder.py` Step 4 fallback 加一個閾值檢查：

```python
# 偽碼
def _resolve(self, name, context, rules):
    # ... Step 1–3 不變 ...

    # Step 4: name_match fallback（既有）
    matches = self._name_to_ids.get(name, [])
    if not matches:
        return []
    if len(matches) > FANOUT_THRESHOLD:
        return [(m, "name_match_ambiguous") for m in matches]
    return [(m, "name_match") for m in matches]
```

**自動同時涵蓋 calls 與 extends**：`_detect_extends` line 659 也呼叫 `_resolve()`，故閾值對 extends 邊一視同仁。**不需要兩處改**。

**`skipped_dynamic` 路徑（Step 1 早出）的處理**：不在 extraction 層加閾值（保留事實全集），改由 projection 層做 aggregate hint。

`FANOUT_THRESHOLD` 是模組級常數（語言無關），定在 `edge_builder.py` 頂部。實作初期 default `N = 3`（用於跑 RED/GREEN 測試）；§7.2 Step 1 dogfood 後若分佈顯示應調整，patch 常數值並更新測試 fixture。

### 4.4 Projection 層

新檔 `core/llm/edge_projection.py`，純函式模組，無狀態。

```python
# 偽碼
def project_edges_for_prompt(
    edges: list[dict],
    *,
    drop_ambiguous: bool = True,
    aggregate_dynamic: bool = True,
) -> tuple[list[dict], dict[str, list[str]]]:
    """Apply projection rules for LLM prompt input.

    Returns:
        (kept_edges, aggregate_hints)
        - kept_edges: edges that should appear in the prompt as-is
        - aggregate_hints: {caller_node_id: [method_name, ...]}
          for edges that were folded into a caller-level散文 hint
    """
```

投影規則：
1. `scope_rule` / `import_alias` → 保留
2. `name_match` → 保留（信心低但 fanout 受控）
3. `name_match_ambiguous` → drop，caller 累積 method name 到 hint
4. `skipped_dynamic` → drop，caller 累積 method name 到 hint

**Hint 散文形式**（projection 只回傳結構化 `dict[caller, list[method_name]]`；散文化由 prompt 模板在 LLM 端說明，BatchReader 直接傳遞 dict 進 payload，不做字串拼接）：
```
feat-X 內呼叫了無法精確定位的方法名：write / get / handle / run
```

Projection 純函式特性（Clean-Code: pure function for testability）：
- 不依賴 `_name_to_ids`、不依賴 `_node_map`
- 不算 fanout（事實已在 extraction 標好）
- 同輸入 → 同輸出，無副作用

### 4.5 BatchReader 整合

`batch_reader.py:_build_payload`（detail mode）的順序：

```
1. batch-local edge filter（既有 line 280-291）
2. project_edges_for_prompt(edges)（H 新增）
3. payload["edges"] = kept_edges
4. payload["aggregate_call_hints"] = hints  # 新 payload 欄位
```

順序意義：
- batch-local 先做 → projection 只看 batch 內邊，hint 內容對應到當前 batch 的 caller
- minimal mode（line 256-261）完全不變

### 4.6 Prompt 更新

`prompts.py:37-46` 既有 resolution 區塊改寫：

```
## 關聯邊 (edges) 的 resolution 標籤

每條邊都帶 resolution 標籤：
- scope_rule / import_alias：高信心，可採用為事實依據
- name_match：裸名匹配，限定 fanout 內，仍持保守態度

你也會看到 aggregate_call_hints 欄位：
{
  "feat-X": ["write", "get", "handle"]
}

這是 caller 端「無法精確定位」的方法名列表（包含高 fanout 與動態 dispatch 來源）。
這些方法名不對應任何具體 target —— 不可寫成依賴關係，也不可宣稱呼叫了某 feature。
若 description 必須提到，限定為「執行了一些（寫入 / 讀取 / 處理）動作」這種泛稱。
```

### 4.7 Viewer 與 Diff（不變動）

- **Viewer**：讀完整 snapshot 顯示，`name_match_ambiguous` 邊視為 `name_match` 同等顯示（tooltip 可選擇加註「高候選量」，本 spec 不要求改前端）
- **Diff**：`name_match` 與 `name_match_ambiguous` 視為同 bucket，避免 schema 升級造成假 churn

具體 diff 規則（落在 §6.4）：
- resolution 從 `name_match` → `name_match_ambiguous` 或反向 = **不算 attribute_changed**
- 其他 resolution 轉換照常算

---

## 5. TDD Plan

### 5.1 Pure-function 優先

`edge_projection.py` 設計成純函式，使測試零依賴：
- 輸入：`list[dict]` 模擬的 edges
- 輸出：`(kept_edges, hints)`
- 測試只需 dict 字面值，不需要 Structure / Snapshot fixtures

### 5.2 Test pyramid

| 層 | 測試形式 | 範例 |
|---|---|---|
| **Unit / Pure** | `tests/unit/core/llm/test_edge_projection.py` | 同輸入同輸出、單 caller 多 ambiguous → 1 hint、`scope_rule` 永遠保留 |
| **Property** | hypothesis | (1) projection idempotency：投影後再投影 = 投影一次；(2) ambiguous + dynamic 邊**不會**出現在 kept_edges；(3) 高信心邊永遠保留 |
| **Integration** | `tests/integration/extraction/test_edge_fanout_threshold.py` | EdgeBuilder 真實跑，fanout > N 的 name 確實標 ambiguous |
| **Integration** | `tests/integration/reading/test_batch_reader_projection.py` | detail mode payload 含 `aggregate_call_hints`、ambiguous 邊不在 `edges` 內 |
| **Contract** | `tests/contract/test_resolution_diff_bucket.py` | diff 比對 name_match ↔ ambiguous 不產生 attribute_changed |

### 5.3 Red-Green 順序

1. **RED**: 純函式測試（5.2 unit + property）
2. **GREEN**: 實作 `edge_projection.py`
3. **RED**: EdgeBuilder 閾值整合測試
4. **GREEN**: `edge_builder.py` Step 4 改動
5. **RED**: BatchReader detail mode payload 形狀測試
6. **GREEN**: `batch_reader.py` 整合
7. **RED**: diff bucket 契約測試
8. **GREEN**: diff 比對策略 patch
9. **DOGFOOD**: 跑 §7 數據驗收，定 N，調整

### 5.4 Coverage 紀律

`edge_projection.py` 累積覆蓋率 100%（純函式必達）。
`edge_builder.py` 閾值新增分支 100%。
其他既有檔不退步。

---

## 6. Data Flow

### 6.1 Extraction → Snapshot

```
codebase
  → ASTExtractor → nodes, edges (raw)
  → EdgeBuilder
       Step 1–3 如舊
       Step 4: len(matches) > N → name_match_ambiguous
              else            → name_match
  → structure_serializer → snapshot.json (含 ambiguous 標籤)
```

### 6.2 Snapshot → L1 Prompt（detail mode）

```
snapshot.json
  → BatchReader._build_payload
       batch-local filter (既有)
       project_edges_for_prompt(batch_edges)
         → kept_edges, aggregate_hints
  → payload {
       nodes: [...],
       edges: kept_edges,       # 不含 ambiguous / dynamic
       aggregate_call_hints: {...}
     }
  → LLM
```

### 6.3 Snapshot → Viewer（不變）

```
snapshot.json
  → API → viewer
       完整 edges（含 ambiguous）顯示
       resolution 用既有 4 色 + ambiguous 視為 name_match 同色
```

### 6.4 Snapshot → Snapshot Diff

```
snapshot_v1 (name_match) vs snapshot_v2 (name_match_ambiguous)
  → diff 比對：normalize resolution 進 bucket
       bucket = {
         "high":   {scope_rule, import_alias},
         "low":    {name_match, name_match_ambiguous},
         "dynamic": {skipped_dynamic},
       }
  → 同 bucket 內變化 = 不算 attribute_changed
```

---

## 7. Acceptance Criteria

### 7.1 結構性驗收（必達）

- `Edge.resolution` 枚舉值新增 `name_match_ambiguous`
- `edge_projection.py` 是純函式模組（無狀態、無 I/O、無 logging）
- `edge_builder.py` Step 4 fallback 加閾值，且 `FANOUT_THRESHOLD` 是模組級常數
- `batch_reader.py` detail mode payload 含 `aggregate_call_hints` key（即使為空 dict）
- minimal mode payload 不含 `aggregate_call_hints`、無變化
- diff 比對 `name_match` ↔ `name_match_ambiguous` 不算 attribute_changed
- 既有 v1.4.5 snapshot 反序列化不報錯，所有邊保留為 `name_match`（向後相容）

### 7.2 數據驗收（量化）

執行 `scripts/dogfood_edge_projection_report.py`（新腳本）：

**Step 1 — 量分佈定 N**
跑 `the_door/src/the_door` + `test-targets/the-door-v105`：
- 輸出 `name_match` 邊 candidate_count histogram（p50/p75/p90/p95）
- N 取 p75 與 p90 之間整數（推估 3–5 之間，實證決定）
- 把 N 寫進 `FANOUT_THRESHOLD`

**Step 2 — 投影前後比較**
| 指標 | 投影前（v1.4.5） | 投影後 | 期望 |
|---|---|---|---|
| L1 prompt 內邊數 | baseline | < baseline | drop 顯著（至少 -30%） |
| `aggregate_call_hints` 涵蓋 caller 比例 | 0% | > 0% | 至少 15% caller 收到 hint |
| Snapshot 邊數 | baseline | = baseline | 不變（事實全集） |

**Step 3 — 主觀驗收**
- 用 agent-as-LLM 各跑一次 v1.4.5 vs 投影版的 L1 description
- 對比「依賴關係」措辭：投影版應 ↓ 模糊用語（「廣泛」「重度」「多種」）
- 對比「假依賴」：投影版應 ↓ 對通用動詞的 feature-to-feature 連結

### 7.3 紀律驗收（程式碼層面）

- 紀律 1：`edge_projection.py` 是純函式 — `grep -E "open|requests|logging" edge_projection.py` 為 0 命中
- 紀律 2：extraction 層不認識方法名清單 — `grep -E "verb|common_methods" edge_builder.py` 為 0 命中
- 紀律 3：projection 不算 fanout — `grep -E "_name_to_ids|len.*matches" edge_projection.py` 為 0 命中
- 紀律 4：property test 釘住三個不變量（5.2 列出）

---

## 8. Risks & Mitigations

### Risk 1：N 取錯導致過度過濾或不夠過濾

- 過小 → 高信心 name_match 也被 drop，L1 漏連
- 過大 → 噪音穿透，目標沒達成
- **Mitigation**：§7.2 Step 1 強制用實證分佈定 N，不拍腦袋；後續可透過 dogfood 重跑微調

### Risk 2：Aggregate hint 措辭被 LLM 誤用為「事實依據」

- LLM 可能把 hint 內方法名當成可宣稱的呼叫
- **Mitigation**：§4.6 prompt 明示「不可寫成依賴關係」+ property test 用 LLM 跑樣本檢查

### Risk 3：舊 v1.4.5 snapshot 比對新版時 diff 不一致

- v1.4.5 全 `name_match`，新版部分變 ambiguous，使用者看 diff 會困惑
- **Mitigation**：§6.4 同 bucket 策略 + CHANGELOG 明示「v1.4.5 ↔ 新版 diff 對 name_match 子類別變化不報告」

### Risk 4：Projection 順序錯誤導致 hint 內容對應錯 caller

- 若 batch-local filter 在 projection 之後做，hint 會包含跨 batch caller
- **Mitigation**：§4.5 明定順序 + integration test 驗證

---

## 9. Out-of-Scope（明示後續工作）

以下不在本 spec 範圍，需要時另開 spec：

- W1: Instance-binding walker（`x = ClassName(); x.method()`）
- W2: Type-annotation tracking（Python annotation、TS type）
- W3: Chained-attribute receiver（`self.bar.baz()`）
- W4: Viewer 對 ambiguous 邊的差異化視覺
- W5: 跨 repo 邊解析
