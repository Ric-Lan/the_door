# 功能分類層（L1.5 區塊）設計

**目的**：讓已翻譯好的 L1 功能，依語意自動歸類成「最多兩層」的區塊（block），
給前端折疊呈現、跨版本可比較。

**核心約束（使用者下達）**：搭配既有流程、不獨立創作——做出來必須能接上現有
agent-as-LLM 鏈與快照載體，不可變成孤兒工具。

**適用範圍**：The Door 本體。後端分類層（資料模型 + 寫入 + 驗證 + guide/prompt +
endpoint）為主體；前端兩層折疊為同 spec 的最後章節，但實作順序在後端之後。

---

## 1. 術語

| 本 spec 用語 | 既有程式碼對應 | 說明 |
|---|---|---|
| 區塊 block | `BlockSummary` / `l1_5_snapshot` | 一個區塊 = 一個功能類別 |
| 兩層 | `parent_block_id` 自我嵌套 | 頂層區塊 → 子區塊 → 功能 |
| 成員 | `related_features` | 歸屬此區塊的 L1 `feature_id` |

「分類 / 類別」是對使用者的說法；落到程式碼一律用既有的「區塊 / block」術語，
不新造名詞。

---

## 2. 背景：喚醒休眠的 L1.5 層（為何不新發明）

The Door 早已設計過一個承接此需求的層，但在乙案/丙案重構後休眠：

- `models/snapshot.py:43` `BlockSummary`（block_id / label / responsibility / confidence）
- `models/snapshot.py:89` `VersionSnapshot.l1_5_snapshot: dict[str, BlockSummary]`
- `core/diff/snapshot_store.py` 序列化（367-371）/反序列化（450-455）已接 `l1_5_snapshot`
- `prompts/l1-5-constraint.md`：原本的 L1.5 分組原則（「把 L1 功能分組成上層區塊」）
- `schemas/l1-5-output.schema.json`、`core/validation/`、`core/rendering/mermaid_renderer.py`

**現況**：`snapshot_write_tool.py` 完全不碰 `l1_5`，無任何工具產出它——model/schema/
序列化/validation/renderer 都在，但沒有資料來源。本 spec = 喚醒並強化這層，
**不新增層、不新增 MCP 工具**。

與既有 `core/classification/operational_classifier.py` 的區別（避免混淆）：那支是
「節點是否屬正式運行表面」的純路徑分類（test/fixture/script/prototype），與「功能
歸類成區塊」**不同件事**，不可混用；但它證明 `core/classification/` 套件已存在，
本 spec 的區塊驗證邏輯放進同套件最自然。

---

## 3. 反過度設計的形態：不新增 MCP 工具

依 agent-as-LLM 鐵則，分類的語意判斷由 agent（驅動的 AI）親自做，工具不做語意判斷。
因此**完全套用 version_narrative 的形態**：

```
version_narrative：snapshot_list → analyze_changes → (agent 自己寫敘述) → snapshot_patch(version_narratives)
功能分類    ：(snapshot 已存) → analyze_changes → (agent 自己分區塊) → snapshot_patch(blocks)
```

不需要「產提議的工具」——agent 自己就是 LLM，自己產提議、自己呈現給使用者確認。
工具/基礎設施只負責三件純結構的事：①承載資料（`BlockSummary` + `snapshot_patch`）
②寫入時硬驗結構不變量（§5）③提供原則（guide + prompt）。

---

## 4. 資料模型擴充（純加法）

`models/snapshot.py` 的 `BlockSummary` 加三個欄位，全部帶 default（舊快照反序列化不受影響）：

```python
@dataclass(frozen=True)
class BlockSummary:
    block_id: str
    label: str
    responsibility: str
    confidence: str | None = None
    related_features: tuple[str, ...] = ()      # 新增：成員 feature_id（tuple 維持 frozen 可雜湊）
    parent_block_id: str | None = None          # 新增：None=頂層；有值=子區塊
    is_new_this_version: bool = False            # 新增：跨版本自動開新類的標記
```

`related_features` 用 tuple（非 list），理由同 `FeatureSummary.source_nodes`——
`frozen=True` dataclass 要可雜湊。`confidence` 既有欄位**分類時不使用**（區塊是聚合，
信心由前端以成員統計呈現，§8）；保留欄位不動。

### 序列化（`core/diff/snapshot_store.py`）
- `_serialize` 367-371：`l1_5_data[bid]` 加 `related_features`（轉 list）、`parent_block_id`、`is_new_this_version`
- `_deserialize` 450-455：用 `.get()` 容錯舊資料
  （`related_features` 預設 `()`、`parent_block_id` 預設 `None`、`is_new_this_version` 預設 `False`）

### Schema（避免 `audit_conformance` 誤標 non-conforming）
`snapshot_store.audit_conformance`（277）用 `snapshots/snapshot.schema.json` 驗證每個
on-disk 快照。新欄位須在 schema 的 `l1_5_snapshot` block 物件加為 **optional**
（`schemas/snapshot.schema.json`；若 `l1-5-output.schema.json` 也描述同結構則一併同步）。

---

## 5. 寫入路徑與硬驗不變量

### snapshot_patch 加 `blocks` 參數
`core/diff/snapshot_store.py:203 patch_snapshot` 加一個可選參數，與既有參數同構：

```python
def patch_snapshot(
    self,
    version_ref: str,
    ...,
    blocks: dict[str, dict] | None = None,   # 新增
) -> tuple["VersionSnapshot", list[str]]:
```

`blocks`：`block_id → {label, responsibility, related_features, parent_block_id,
is_new_this_version}`（confidence 省略）。提供時**整批取代** `l1_5_snapshot`
（分類是整體產物，不像 source_nodes 是逐 feature 增補）。用 `dataclasses.replace`
寫回，version_id / timestamp 不變。

`mcp/tools/snapshot_patch_tool.py` 的 `TOOL_SCHEMA` 加 `blocks` 屬性與說明；
`execute` 把 `blocks` 傳入並在回傳 payload 報告寫入的區塊。

### 硬驗（新模組 `core/classification/block_validator.py`，純函式、可獨立測）
`patch_snapshot` 在寫 `blocks` 前呼叫驗證；任一不過 → 拒絕寫入並回明確錯誤
（類比 C7 對結構的把關）。不變量：

1. **兩層上限**：任何 `parent_block_id` 非 None 的區塊，其 parent 的 `parent_block_id`
   必須為 None（禁止三層）。
2. **單一歸屬**：每個 `feature_id` 在所有區塊的 `related_features` 聯集中最多出現一次。
3. **功能只掛葉區塊**：有子區塊的區塊，其 `related_features` 必須為空
   （功能掛在最底層，使窮盡/單一歸屬計算單純）。
4. **窮盡**：current 快照 `l1_snapshot` 的每個 `feature_id` 都必須出現在某區塊的
   `related_features`。agent 須把未歸屬功能放進固定兜底區塊 `blk-unclassified`；
   驗證只**檢查**窮盡（仍有 feature 不在任何區塊 → 拒絕寫入，驗證不自動塞、不改資料），
   兜底區塊非空時在回傳 payload 回報數量（誠實揭露「有功能沒分到」，不靜默吞）。
5. **交叉引用**：`related_features` 的 id 都存在於 `l1_snapshot`；`parent_block_id`
   指向的 block 存在。
6. **命名規範**：沿用既有 L1.5 `core/validation` 的 language_check（規則見
   `prompts/l1-5-constraint.md`：禁裸術語、需功能語境）。
   ⚠ 實作時須確認 language_check 對中文 label 的字數判定行為；兜底區塊
   `blk-unclassified` 若與規則衝突則豁免命名檢查。

### 軟約束邊界（誠實）
「歸得準不準、沿用判斷對不對、命名貼不貼切」是純語意，**結構上無法 gate**
（種子 §5 固有缺口、C7 邊界）。這些靠 guide 原則 + 冷啟動互動確認把關，不假裝能驗。

---

## 6. agent-as-LLM 分類流程

### 冷啟動（第一版，互動確認）
1. snapshot_write 寫好 L1 功能後，agent 讀 `l1_snapshot`。
2. agent 在原則約束下，自己把功能分成最多兩層的區塊。
3. **agent 把提議（區塊樹 + 成員）以文字呈現給使用者**，得到同意後才寫入。
   （類比 version_narrative「先聲明、收到確認才執行」的 guide 約定，非 hook。）
4. 使用者偏好：使用者可在步驟 2 前先提供偏好區塊表當種子，有就優先採用、跳過提議。
5. agent 呼叫 `snapshot_patch(blocks=...)` 寫入。

### 後續版本（沿用 + 自動開新類 + 標記）
1. `analyze_changes(baseline=...)` 回傳 `inherited_features`（不變）與 `affected_features`
   （增/改/刪）（`analyze_changes_tool.py:165-166`，已存在）。
2. agent 讀 baseline 快照的 `l1_5_snapshot` 當沿用基礎。
3. `inherited_features` 維持 baseline 的區塊歸屬；`affected`/新功能歸入既有區塊；
   真的塞不進 → 自動開新區塊並標 `is_new_this_version=True`（**不打擾使用者**，留痕供事後檢視）。
4. `snapshot_patch(blocks=...)` 寫入 current。因 `blocks` 為**整批取代**（§5），
   re-patch 須帶齊所有區塊（繼承的 + 調整的），不可只帶 affected 的區塊。

### inherit_from 繼承 l1_5（最佳化，可延後）
`snapshot_write` 的 `inherit_from` 目前不帶 `l1_5_snapshot`。本 spec 讓它**一併繼承
baseline 的 `l1_5_snapshot`**（與 features 一起帶），使「affected set 全空」的純繼承
版本自動沿用區塊、無需 re-patch（呼應 project_summary「組成沒變不重寫」精神）。
**此為最佳化、非必要**：未做時 agent 每版整批 re-patch 亦正確，故可延後（§12）。

### guide / prompt 更新
- `CLAUDE.md`：在 agent-as-LLM chain 加「功能分類」流程段（冷啟動互動確認 + 跨版本沿用）。
- `prompts/l1-5-constraint.md`：更新為「最多兩層（parent_block_id）+ 單一歸屬 + 窮盡 +
  沿用既有 + 自動開新類標記」；移除本 spec 不啟用的欄位（見 §9）。

---

## 7. Endpoint：`GET /api/blocks`

與 `/api/integration` 對稱（獨立端點、前端獨立 state）。在
`core/ui/api/router.py:build_routes` 加一筆 Route，handler 讀 current 快照的
`l1_5_snapshot` → 組兩層樹，每個葉區塊帶成員（用 `l1_snapshot` 補功能 label/confidence/
description）→ 回 JSON。handler 可掛在既有 catalog 群組（`c`，已處理 snapshots/timeline
等讀取），不新增 handler 群組。無 `l1_5` 資料時回空樹，前端 fallback 平鋪（§8）。

回傳形狀（草案，實作可微調）：
```json
{
  "blocks": [
    {"block_id": "blk-core-engine", "label": "...", "responsibility": "...",
     "parent_block_id": null, "is_new_this_version": false,
     "features": [{"feature_id": "feat-...", "label": "...", "confidence": "high"}]}
  ]
}
```

---

## 8. 前端兩層折疊（mockup 已視覺確認）

唯一正式版 = `docs/frontend-local-version-viewer/viewer/`。功能總覽改成「依區塊兩層折疊」：

- 頂層區塊可折疊；有子區塊者展開顯示子區塊（縮排）→ 功能卡片。
- **收合時**標題列右側顯示該區塊加總（如 `high 3`、`medium 1`、整合 `✓ 2`），
  利用收合後的空白（使用者確認的行為）。
- 功能卡片含 label + description（翻譯）+ 信心 pill + 整合 ✓ 徽章（沿用既有語彙）；
  卡片用 flex 讓標記對齊底部、同列等高。
- 整合 ✓ 徽章**沿用既有 `state.integration`**（`/api/integration`，已存在），與 blocks
  併呈，不重複計算。收合統計的整合數同樣由 `state.integration` 算。
- `is_new_this_version` 區塊加「本版新增」徽章。
- 無 `/api/blocks` 資料時 fallback 回現有平鋪清單（不破壞既有行為）。

區塊結構來自 `/api/blocks` 經單一 state（呼應 integration 的 `state.integration` 模式）；
整合徽章仍走既有 `state.integration`，兩者在前端併呈。

---

## 9. 不做的事（YAGNI 邊界）

- **不新增 MCP 工具**（§3）。
- **不設類別數量上限**——收斂機制是「最多兩層」，不是綁死數量（大型專案必然功能多，
  綁死無意義，使用者明示）。
- **不啟用** L1.5 原 prompt 的 `trigger_mechanism`、`block_relations`、
  `infrastructure_block` 三個重欄位（本需求不要、會把輕量分類變回重結構）。
- **不做跨版本 diff 的區塊變化視圖**（資料已具備 `is_new_this_version`，視圖另議）。
- 後續開新類**不**互動確認（自動 + 標記；只有冷啟動第一版互動確認）。

---

## 10. 契約影響

`BlockSummary` 加欄位皆有 default、序列化用 `.get()` 容錯、schema 設 optional →
**純加法、不 bump** `SNAPSHOT_CONTRACT_VERSION`（現 `"1"`，`models/snapshot.py:12`）。
依 `docs/contract-versioning.md`：純加法不改既有欄位語義，亂 bump 會把舊快照誤標 legacy。

---

## 11. 測試

- `block_validator` 單元：六條不變量各一組 pass/fail（兩層、單一歸屬、功能只掛葉、
  窮盡+兜底、交叉引用、命名）。
- snapshot roundtrip：含新欄位的 `l1_5_snapshot` 序列化↔反序列化；舊快照（無新欄位）
  反序列化得 default。
- patch：`snapshot_patch(blocks=...)` 寫入後重讀一致；不合法 blocks 被拒並回明確錯誤。
- 沿用：baseline 有區塊 → inherit_from 繼承 l1_5；affected 非空時 re-patch 正確、
  新功能塞不進開新區塊標 `is_new_this_version`。
- endpoint：`GET /api/blocks` 回兩層樹；無資料回空樹。
- e2e fixture 只放 input（依既有慣例）。

---

## 12. 實作順序

1. 資料模型 + 序列化 + schema（§4）
2. `block_validator` + `snapshot_patch` blocks 參數（§5）
3. guide / prompt 更新（§6）
4. `GET /api/blocks`（§7）
5. 前端兩層折疊（§8）
6. （可延後）`inherit_from` 繼承 l1_5（§6 最佳化）

1–4 為後端分類層，可獨立交付測試；5 依賴 4；6 為最佳化、任何時候可加。
