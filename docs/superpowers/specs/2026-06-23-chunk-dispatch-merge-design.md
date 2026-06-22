# 設計：大專案分塊翻譯的 Dispatch + Merge

- 日期：2026-06-23
- 狀態：設計已核可，待寫實作計畫
- 前置：[Chunk 切分原則](2026-06-22-chunk-split-principle-design.md)（`chunk_planner.plan()` 已實作併入 main）
- 關聯待辦：[[todo_large_project_subagent_dispatch]]
- 定位：**best-effort「略微往上支援」**——讓塞不進單一 agent 的專案能被分塊翻譯成 L1；**非大型通吃**。

---

## 1. 動機與框架（研究已坐實）

`chunk_planner.plan()` 已能把 structure-view 切成 token 預算內的 chunk，但**只算切點、不翻譯、不合併**。本 spec 補上「把切分計畫真的拿去派 subagent 翻譯、再合併成單一 snapshot」這段。

研究發現（紮根真實資料）：

- **可行性**：派 fresh subagent 逐塊翻譯**做得到**，正是突破單-agent context 上限的手段。每個 subagent 只載自己那塊（≤budget）、回傳精簡 feature 清單；coordinator 不累積結構量。
- **品質代價（誠實）**：稠密專案（如 The Door 自身）切完後 calls 邊 **~84% 跨塊**（v170 實測，11 塊）——數學上稠密圖無稀疏割點、切不乾淨，任何演算法都救不了。⟹ 產出的 feature 較細、會碎；靠**結構切邊推導 relation** 把依賴接回來。這是「品質略降」，非「做不到」。
- **新天花板（仍有限）**：coordinator 最終的「合併 + 單次 `snapshot_write`」payload 是新上限——遠高於單-agent 直讀上限，但非無限。超過則須**明確回饋無法翻譯**（§5），而非攻頂失敗。

**核心分工原則**：subagent 做不可約的 LLM 工作（命名/描述 feature）；**所有結構接線（relation）由決定性工具從結構邊推導**（CLAUDE.md 閘門：結構性分析走純程式）。

**The Door 是 MCP server + CLI，無法自己 spawn subagent** ⟹ 派發是執行 agent 的工作，由 CLAUDE.md 協定規範；The Door 只提供 `chunk_planner`（已做）、`chunk_merge`（本 spec）與協定文件。

## 2. 端到端流程

```
chunk_planner.plan(codebase_path, target_tokens)   ✅已做
        ↓  回 {regime, needs_split, feasible(新§5), chunks:[{chunk_id,node_ids,…}], …}
[協定第 0 步：執行 agent 讀 plan]
  feasible==false（too_large）→ 回饋使用者「專案過大、無法翻譯」並停（§5）
  needs_split==false（small）  → 走現有單-agent 直翻（既有路徑，本 spec 不改）
  needs_split==true（feasible）→ 分塊翻譯：
        ↓
[執行 agent 每塊派一個 Task subagent]（§3 協定）
  subagent：就這塊 node views 產 features（命名空間 feature_id、無 relations）
  回傳精簡 feature 清單
        ↓
chunk_merge(codebase_path, chunks=[{chunk_id, features:[…]}])   ❌新做（§4，決定性）
  驗 id 唯一 → 建 node→feature 映射 → 從結構邊推導 static relations → 組裝
  回 {l1_features:[…], relations:[…], rollup:{…}}
        ↓
[執行 agent] edge_residue(codebase_path)   ← C3 前置：蓋 checklist（covered_nodes + source_files）
        ↓
[執行 agent] 自己綜合 project_summary（NL）→ snapshot_write(l1_features, relations, project_summary, …)
  ← 一次 gated 寫入（source_nodes 為全節點子集、必 ⊆ edge_residue covered → 過 C3）
```

> **前置鏈（協定必含）**：分塊翻譯與單-agent 同樣依賴 `extract_structure`（產 structure-view，plan/subagent/chunk_merge 皆讀它）與 `edge_residue`（C3 蓋章）。順序：`extract_structure` → `plan` →（分塊 dispatch → `chunk_merge`）→ `edge_residue` → `snapshot_write`。`edge_residue` 可在 dispatch 前或後跑，只要在最終 `snapshot_write` 前完成且其後 source 未變動（否則 C3 staleness 擋）。

## 3. chunk-subagent 任務（CLAUDE.md 協定規範，無新工具）

- **輸入**（coordinator agent 提供）：
  - 該 chunk 的 node views（inline；因 chunk 為預算大小，必 ≤ target_tokens）；
  - `chunk_id`（如 `c003`）；
  - 一行專案 context（選填，給跨塊命名一致性用）。
- **產出**：features 清單，每筆 `{feature_id, label, description, confidence, source_nodes}`：
  - **`feature_id` 必以 `chunk_id` 前綴命名空間**（如 `feat-c003-auth`）→ 結構性保證跨塊不撞 id。
  - `source_nodes` ⊆ 該塊節點。
  - **不產 `relations`、不產 `project_summary`**（皆跨塊資訊，留給 §4 工具 / coordinator）。
- 回傳**只含 features**（不回 views）→ coordinator context 不累積結構量、天花板才高。
- subagent 對其 chunk 內做的就是現有單-agent 的 L1 分組（按功能分組節點），只是範圍縮到一塊。

## 4. chunk_merge 工具（決定性、新增）

**檔案**：`core/structure_view/chunk_merge.py`（純函式核心）+ `mcp/tools/chunk_merge_tool.py`（MCP 轉接）。唯讀（讀 structure-view）、回傳 payload、**不寫 snapshot、不需 gate**。

**TOOL_SCHEMA**：
```json
{
  "codebase_path": "str (必)",
  "chunks": [ {"chunk_id": "str", "features": [
      {"feature_id":"str","label":"str","description":"str","confidence":"high|medium|low",
       "source_nodes":["node_id"], "trigger_description":"str?", "confidence_reason":"str?"} ]} ]
}
```

**決定性處理**：
1. **收齊 + 驗 id**：union 所有 chunk 的 features。`feature_id` 跨塊重複 → 回 `{"error": ...}`（點明衝突 id；協定的命名空間規則本應防止，工具仍驗）。
2. **node→feature 映射**：由各 feature 的 `source_nodes` 建 `{node_id: feature_id}`。一節點被多 feature 認領 → 記 warning、決定性取 `feature_id` 字典序首者（chunk 互斥下只可能發生在單一 subagent 內部誤標）。
3. **推導 relations**：複用 `load_views(codebase_path)` 取各 node 的 `out_edges`；對每條 `u→v`（`v` 在 views 內、`v≠u`），若 `featureOf(u)` 與 `featureOf(v)` 皆存在且不同 → 候選 relation `{from_feature: featureOf(u), to_feature: featureOf(v), relation: <邊型別 calls|imports|extends>, relation_type: "static"}`。**按 `(from_feature, to_feature, relation)` 聚合去重**。端點缺 feature 的邊 → 略過並計數。
4. **回傳**：
   ```json
   {
     "l1_features": [ …union… ],
     "relations": [ …derived static… ],
     "rollup": {
       "feature_count": int, "relation_count": int,
       "skipped_edges_no_feature": int, "double_assigned_warnings": ["node_id…"]
     }
   }
   ```
   經 `_response_envelope.wrap` 包裹（注入 next_actions），與其他工具一致。

**為何 relation 全由工具推導、subagent 不產**：relation 是讀「node→feature + 結構邊」的純結構工作，純程式比 LLM 準且完整（不漏跨塊邊）；subagent 本看不到跨塊邊。`relation_type="static"` ⟹ 可被既有 `integration_check` 驗成 backed。

## 5. 天花板守衛 + 不可行回饋

**對 `chunk_planner` 純加法**（新增欄位，不破壞既有輸出）：

- `plan()` 新增單一參數 `max_total_tokens`（可設，保守預設 `2_000_000` ≈ 20×預設預算）。
- 判斷（決定性、無歧義、單一上限）：在 triage 最前面比 `total_est_tokens > max_total_tokens` → **不切就短路**回 `regime: "too_large"`、`feasible: false`、`reason`（含實際 `total_est_tokens` 與觸發的 `max_total_tokens`）。否則照 §2 既有 small/medium/large。
- `feasible` 欄位**一律輸出**（small/medium/large 時為 `true`），讓協定有單一判斷點。
- **不設 `max_chunks` 硬上限**（經實測確認後的刻意取捨，非「冗餘」）：`max_total_tokens` 守的是 **feasibility 軸**（結構總量／最終 merge+write payload 能否產出 ∝ 節點數）——這正是「能不能翻譯」的牆。`chunk_count`（≈ `total/target`）守的是**另一軸：派發成本**（要派幾個 subagent）；因 `target_tokens` 可調，小 target 會讓 chunk 數與 total 脫鉤（v170 實測：total 固定 992k，target 100k→11 塊、1k→1074 塊）。但 chunk 數爆多是**慢/貴、非不可行**（最終 payload 仍 ∝ 節點數、不變），故**不設硬上限、改用協定軟提醒**（見下），符合 best-effort 的 modest 取捨。

**協定第 0 步**（CLAUDE.md）：執行 agent 先 `plan()`：
- `feasible == false` → **不派發**，回饋使用者：
  > ⚠ 專案過大（估計 ~`{total_est_tokens}` tokens、`{chunk_count}` chunks，超過分塊翻譯上限 `max_total_tokens={…}`）。**無法使用 LLM 翻譯功能。** 可選：縮小分析範圍（指定子目錄）、或明確調高 `max_total_tokens` 重試（風險自負，可能在合併/寫入階段失敗）。
- `feasible == true` 且 `needs_split == true` → 分塊 dispatch+merge（§2–§4）。
  **派發成本軟提醒**：若 `rollup.chunk_count` 偏高（建議門檻 30），先**告知不擋**：
  > ℹ️ 將派發 `{chunk_count}` 個 subagent（耗時／成本較高）。如要降低，可調高 `target_tokens` 減少塊數後重試。
  使用者要繼續就繼續——這是成本透明，非可行性限制。
- `needs_split == false` → 現有單-agent 直翻。

**為何在 plan() 早判**：派發前、決定性、可設——在浪費 N 個 subagent 前就誠實擋下並告知極限，而非攻頂失敗。

## 6. 範圍 / 非目標（誠實邊界）

- **接受 feature 碎裂**：不做語意去重（稠密專案碎裂無法避免、語意去重需跨塊視野違背切分目的、成本不符 best-effort 目標）。
- **chunked 模式只產 `static` 結構 relation**：不產「概念/inferred」relation（無邊的流程關係）；這是 best-effort 簡化。單-agent 直翻路徑不受影響、仍可產 inferred。
- **不做大型通吃**：`too_large` 明確回饋無法翻譯（§5）；企業級分層（chunk-of-chunks）出範圍。
- **不與 `analyze_changes` 增量結合**：第一版只做整專案 chunked 翻譯（增量×分塊留後續）。
- **The Door 不 spawn subagent**：派發是執行 agent 的事（協定文件）；工具只提供切分計畫與決定性合併。
- **不改 gate / 不 bump 契約 / 不動 viewer / 不動單-agent 既有路徑**。

## 7. 介面落點

- `core/structure_view/chunk_merge.py`（新）：純函式 `merge(codebase_path, chunks) -> dict`（+ 內部 helper：node→feature 映射、relation 推導、聚合）。
- `mcp/tools/chunk_merge_tool.py`（新）：`TOOL_SCHEMA` + `async def execute`，回 `wrap(payload, …)` 或 `{"error":…}`；於 `mcp/server.py` 三點註冊（import / Tool entry / dispatch）。**唯讀、不入 C3 gate**。
- `core/structure_view/chunk_planner.py`（純加法改）：`plan()` 加 `max_total_tokens` 參數、輸出 `feasible` + `too_large` regime。
- `CLAUDE.md`（改）：新增「大專案分塊翻譯協定」段（第 0 步 plan→feasible 分流、`chunk_count` 派發成本軟提醒、subagent 任務規範、chunk_merge→edge_residue→snapshot_write 鏈、too_large 回饋敘述）+ 工具表加 `chunk_merge` 一列。
- 是否加 CLI：本 spec 不需（dispatch 是 agent 行為，CLI 無對應人類操作）。

## 8. 測試方向

**chunk_merge 核心（合成 features，不依賴磁碟用合成 views / 真實 fixture 用 python_simple）**：
- **id 唯一**：跨塊重複 feature_id → error。
- **node→feature 映射**：一節點兩 feature → warning + 字典序首者；正常 → 正確映射。
- **relation 推導**：構造「featureX 的節點 call featureY 的節點」→ 推出 `X→Y, relation=calls, static`；同對多邊 → 聚合成一條；端點無 feature 的邊 → skip + 計數。
- **relation 型別**：邊型別 calls/imports/extends 正確帶入 `relation`。
- **決定性**：同輸入同輸出。
- **真實 fixture**（python_simple，6 nodes）：把節點分成 2 個假 chunk 的 features，merge 後斷言 `app.py::login`→`auth.py::authenticate_user` 的 calls relation 被推出（跨假 feature）。
- **rollup 欄位齊**。

**chunk_planner 守衛（§5）**：
- `total_est_tokens > max_total_tokens` → `feasible=false, regime=too_large, reason` 有值、且**未切分**（短路、無 chunks 計算）。
- 正常規模 → `feasible=true`（small/medium/large 皆然）。
- 既有 small/medium/large 測試不回歸（feasible 欄位純加）。

**MCP 轉接煙霧測試**：`chunk_merge_tool.execute` 正常路徑（回 envelope 含 l1_features/relations/next_actions）+ 錯誤路徑（缺 codebase_path、重複 feature_id）；server 註冊（`"chunk_merge" in REGISTERED_TOOL_NAMES`）。

測試鏡像 repo 結構（`tests/unit/core/structure_view/`、`tests/unit/mcp/tools/`）。
