# Spec：專案簡介綜合（project_summary）— 單版本 L1 收斂成非技術簡介

> 日期：2026-06-13
> 狀態：draft（待雙審）
> 需求來源：使用者拍板（[[todo_project_summary_synthesis]]）——「將單一版本裡的功能模塊解釋
> 綜合起來說明簡介專案的功能，這是專案產品賣點的取向」、讀者＝非技術人員。

## 0. 目標與兩道閘門自檢

**目標**：L1 是逐 feature 的人話；缺「所以這個產品是做什麼的」收斂層。補上翻譯鏈最後一哩：
agent（執行分析的 LLM）讀自己剛產的 L1 描述，綜合成 2-4 句非技術簡介，持久化進 snapshot，
viewer 單版本模式顯示。

- **閘門 1（通用型強化 LLM 翻譯證據）**：簡介的生產者是 agent-as-LLM、消費者是人類客群。
  不新增任何分析工具、不引入工具間互相消費——agent 讀 L1（自己的產出）綜合，infra 只負責
  持久化與顯示。✅
- **閘門 2（不引多餘資訊）**：簡介內容上限＝L1 已有資訊的收斂（指引明文禁止引入 L1 之外的
  能力宣稱）；誠實化 metadata（綜合自 N 個功能、x 個低信心）**不持久化**、由消費端從
  l1_snapshot 即時導出（避免雙重計數；結構自明）。✅

## 1. Spike 已驗事實（2026-06-13，本 worktree）

| 事實 | 出處 |
|---|---|
| snapshot schema strict（root `additionalProperties: false`），加欄必動 schema | `schemas/snapshot.schema.json:6` |
| 加 optional 欄＝純加法 ⟹ `SNAPSHOT_CONTRACT_VERSION` 不 bump（亂 bump 會誤標 legacy） | docs/contract-versioning.md §6 |
| 持久化管線：`snapshot_write_tool.execute` → `SnapshotStore.create_snapshot`（keyword-only 參數）→ `VersionSnapshot` → `_write_snapshot`／`_load` 對稱（缺鍵→None 慣例已有 `contract_version` 先例） | `snapshot_store.py:93-137,374-489` |
| inherit 模式：baseline 解析→merge features；目前**不碰**任何 snapshot 級欄位的繼承（label/commit 都由本次呼叫給） | `snapshot_write_tool.py:191-269` |
| 顯示出口：viewer `summary-band`（`index.html:60`）單版本模式現顯「`label · 共 N 個功能`」（`ui-topbar.js:22-29`），正是簡介的位置 | grep 驗真 |
| `/api/l1` 回 `nodes/edges/warnings`，無 snapshot 級欄位；nodes 已含 per-feature confidence ⟹ 前端可自算低信心計數，後端零新邏輯 | `graph.py:33-`、`graph_view_model.py:95-139` |
| C3/C7 hook 只查 description 指紋＋node coverage＋staleness，新 optional 參數不會誤擋 | `c3_gate_snapshot_write.py`（06-13 已讀） |

## 2. 設計

### 2.1 資料形狀（持久層）

- `VersionSnapshot.project_summary: str | None = None`（None＝未綜合＝誠實缺席，不自鑄 default）。
- `snapshot.schema.json` 頂層加 `"project_summary": { "type": ["string", "null"] }`（非 required）。
- `_serialize_snapshot` **無條件 emit** `project_summary` 鍵（None 也寫，同 `commit_hash`
  慣例）——雙審抓到的硬約束：`test_schema_serialize_field_bijection` 強制 schema properties
  與落盤 keys 雙向相等，且 `_write_snapshot` 對 schema fail-closed；`_maximal_snapshot`／
  `_minimal_snapshot` 測試 fixture 同刀更新。`_deserialize` 以 `data.get("project_summary")`
  讀回（舊檔缺鍵→None，同 contract_version 先例；round-trip 等價測試自動覆蓋）。
- **不持久化** word count／信心統計／來源 feature 清單——全部可由 l1_snapshot 導出。

### 2.2 寫入（snapshot_write MCP）

- TOOL_SCHEMA 加 optional `project_summary: {"type": "string"}`，description 明寫：
  「2-4 句、給非技術讀者、只能綜合 l1_features 已含的資訊」。
- **Direct 模式**：有給→存；沒給→None（不警告——簡介是建議產出，不是必填）。
- **Inherit 模式**：沒給→**繼承 baseline 的 project_summary**（feature 組成沒動、簡介當然
  沿用）；有給→覆寫（信任 agent 判斷組成已變）。
- **誠實邊界（guide 級、不立 gate）**：「affected set 全空時不重寫簡介」寫進 CLAUDE.md
  增量鏈，不做指紋 gate——C7 鎖的是逐 feature 重譯；簡介是聚合產物，組成變了本來就該重寫，
  指紋 gate 屬過度設計（能做≠該做；若實際出現濫改再立，先記誠實缺口）。

### 2.3 讀出（/api/l1）

- `get_l1` handler 在回應頂層加 `"project_summary": snapshot.project_summary`。
- 不加統計欄——前端從已有 nodes（含 confidence）自算。

### 2.4 顯示（viewer，唯一正式版 viewer/）

- 單版本模式（`ui-topbar.js` renderTopBar 的 `state.l1Model` 分支）：
  - 有 `project_summary` →
    `summary-band` 顯示：`{project_summary}（綜合自 N 個功能，其中 x 個低信心）`；
    x=0 時省略低信心尾註。N、x 由 `state.l1Model` nodes 自算。
    **誠實化（審 2）**：x 只計 `confidence === 'low'`；`unknown`（未評估）不混入——
    若 unknown 數 y>0 另加「y 個未評估」，未評估≠低信心（H1 原則）。
    空字串視同 None（falsy → fallback）。
  - 無（None／舊 snapshot）→ fallback 現行「`label · 共 N 個功能`」，零行為變化。
- diff 模式不動（P2 的事）。
- `app.js` 載入 `/api/l1` 時把 `project_summary` 收進 `state.l1Model`。

### 2.5 Agent 指引（CLAUDE.md agent-as-LLM 鏈）

- 單版本鏈步驟 2 補：產出 JSON 同時給頂層 `project_summary`（2-4 句、非技術讀者、
  禁止引入 l1_features 之外的能力宣稱、低信心 feature 的能力描述保守措辭）。
- 步驟 4 `snapshot_write` 簽名範例補 `project_summary=...`。
- 增量鏈步驟 4 補：「affected features 非空→重寫簡介；全空→省略（自動繼承）」。

### 2.6 P2 前瞻（本刀不實作，只保留名稱空間）

版本級「這次更新做了什麼」白話敘述＝**diff 層**產物（描述 transition，不屬於單一 snapshot），
落點將是 diff-explanations store 或 report 面，欄名擬 `version_narrative`——與
`project_summary`（snapshot 級、描述 state）語義正交、不共用欄位。本 spec 唯一義務＝
命名不衝突（已確認）。

## 3. 不做清單

- ❌ 簡介指紋 gate（§2.2 誠實邊界）。
- ❌ 統計 metadata 持久化（§2.1）。
- ❌ diff 模式版本敘述（P2 分刀）。
- ❌ `snapshot_patch` 支援 patch 簡介（patch 家族＝source_nodes 回填；簡介屬重分析語義，
  走 inherit_from 新 snapshot——同 B1 confidence 回填的誠實理由：評估時點不同）。
- ❌ 契約版號 bump（純加法）。

## 4. 測試清單（TDD 順序）

1. **model/store round-trip**：`create_snapshot(project_summary="...")` → 落盤 → `_load` 讀回
   一致；未給→None；舊 snapshot JSON（無此鍵）load→None。
2. **schema**：帶 `project_summary`（str 與 null）的 snapshot 過 schema 驗證；strict 仍擋未知鍵。
3. **snapshot_write direct**：給→persist；不給→None。
4. **snapshot_write inherit**：baseline 有簡介＋本次未給→新 snapshot 繼承；本次有給→覆寫。
5. **/api/l1**：回應含 `project_summary`（有值與 null 兩態）。
6. **viewer vitest**：topbar 單版本——有簡介→band 顯簡介＋統計尾註（x=0 省略尾註）；
   無→fallback 現行文案（迴歸守護）。

## 5. 驗收（含消費端 LLM 回饋）

- 結構層：上述測試全綠＋全套基線不退（1484/536）。
- 消費層（自己驗自己、誠實分級）：對 test-target 實跑一次 agent-as-LLM 鏈產簡介→
  viewer 實看顯示；簡介品質（忠實、無引入多餘資訊）由主 agent 自評＋攤開理由，
  效力標 **medium**（單樣本），不升格。
