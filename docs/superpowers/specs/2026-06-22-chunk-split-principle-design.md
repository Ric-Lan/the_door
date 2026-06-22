# 設計：大專案翻譯的 Chunk 切分原則（Chunk Split Principle）

- 日期：2026-06-22
- 狀態：設計已核可，待寫實作計畫
- 範圍：**只定「切分原則」**——給定 structure-view，先**評估**專案規模，再用通用原則把它切成一組「可獨立交給一個 LLM subagent 翻譯」的 chunk。**跨塊一致性 / 合併 / 實際派工留待後續 spec。**
- 關聯待辦：[[todo_large_project_subagent_dispatch]]

---

## 1. 動機（spike 已坐實的痛點）

The Door 主打路徑（agent-as-LLM：讀 structure-view → 產 L1 功能）隱含「單一 agent 一次讀完整份結構」。spike 用真實資料（v170＝The Door 自身，2782 nodes）量到：

- 要翻全專案 L1 必須消費的 region views 合計 **≈ 992k token**（單一 `the_door` region 就 ≈ 939k）。
- 每節點 ≈ 357 token（含 docstring/comment/params/decorators + 完整出入邊清單），且因 CJK docstring 多，這是 **chars/4 的保守下限**。
- → 中型專案就已**超出 200k window 約 5 倍、塞滿 1M window**。痛點真實、且在中型規模就觸發。

結論：需要把翻譯工作切成 token 預算內的 chunk 分發。本 spec 定切分原則。

## 2. 前置評估（Triage）— 先決定要不要切、哪種 regime

切分前先做輕量 triage（純結構計算）。通用基準＝**`total_est_tokens` 對 `target_tokens` 的比值**，一個連續量、非列舉專案類型：

1. 算 `total_est_tokens` ＝逐節點實估加總（與 §4 同一估計器）。
2. 用比值 `r = total_est_tokens / target_tokens` **粗分** regime：
   - **small（`r ≤ 1`）** → **不切**。回單一 chunk（＝整個專案）、`needs_split: false`。下游直接走現有單-pass 翻譯流程，**零切分成本**。
   - **medium（`1 < r ≤ large_ratio`）** → 跑 §3 平鋪階梯，產數個 chunk。
   - **large（`r > large_ratio`）** → **仍跑同一個平鋪階梯**（演算法不變、只是 chunk 多），額外吐 `regime: "large"` 提示，讓未來的 dispatch/合併層知道「塊多、跨塊一致性更重要」。
3. `large_ratio` 為**可設參數**（建議預設約 8–10×，確切值由實作計畫定）；它只切換「標籤」，不切換演算法。

**關鍵**：small/medium/large 是**評估標籤 + 要不要切**的粗分，**不驅動不同演算法**（除了 small 短路不切）。這就是「粗略、通用」——一個比值決定，沒有列舉專案類型。企業級超大型（需 chunk-of-chunks / 分層）**明確出範圍**（見 §7）。

## 3. 核心切分原則：連通性貪婪打包 + 大小保底階梯

當 triage 判定要切，對待切的節點集合套用**三層退化階梯**——越下層越通用，**任何輸入都有定義、永不撞牆**：

### Tier 1 — 連通性（cohesion，品質層）
- 由 edges（call/import/inheritance）建**無向加權圖**（權重＝兩節點間邊條數，方向/型別不分）。
- 取**連通分量（connected components）**。
- 用 bin-packing 把分量塞進 chunk：**一個分量塞得下 `target_tokens` 就整塊留同一 chunk**；多個小分量可併入同一 chunk 直到逼近預算。
- 效果：緊耦合節點（多半屬同一功能）留同塊 → 跨塊功能碎裂最少。

### Tier 2 — 切分超預算的單一分量（cohesion-aware 排序後切）
- 一個連通分量大過 `target_tokens` 時，沿一個**圖鄰近性排序**把它切成多個 ≤ 預算的子塊。
- 排序＝從分量內**最高 in_degree 的節點**起 **BFS 遍歷序**（決定性）；BFS 讓圖上相鄰的節點在序列中也相鄰，故「依序填滿就切」時切口落在連結較稀疏處 ≈ 近似最少切邊。
- **決定性 + 零重依賴**：不引圖論大套件（networkx 等），BFS + 線性掃描自寫。
- tier 標籤＝`bisect`；被切斷的邊數計入品質訊號（§5 `cross_chunk_edges`）。

### Tier 3 — 依序切原語（總定義域，不撞牆保證）
- Tier 2 的「依序填滿就切」由一個通用原語 `_slice_by_order(ordered_node_ids, est, target)` 實現：沿給定序貪婪累加估計 token、逼近預算即斷。**這就是 Tier 3**——它在**任意**節點序上都有定義、必產出合法 chunk，是整個階梯的保證底。
- 退化關係（避免 dead code、誠實對應實作）：**零邊**輸入＝每節點各自成一連通分量 → 由 **Tier 1** 直接打包（不需 Tier 3 特例）；**稠密團/單檔上千節點**＝單一超預算分量 → 由 **Tier 2** 的 BFS 排序切（仍走此原語）。故 Tier 3 不是獨立演算法分支，而是 **Tier 2 依賴的切分原語 + 保證性質**。
- **單節點本身 > 預算**的極端（§4）：該節點自成一 chunk、標 `oversized` 警示——這是此原語明確處理的退化點。

### 現實校準（誠實，避免「理論漂亮」）
多數真實 codebase 是**單一巨大弱連通分量**（幾乎什麼都 import 到某處）。此時 Tier 1 取連通分量 ≈ 整個專案一塊，會立刻落到 Tier 2 遞迴二分。所以**實務上 Tier 2（二分）才是主力工人，Tier 1 主要回收的是「真正孤立的子系統 / 測試夾具 / 周邊腳本」**。設計不假裝連通分量會神奇地剛好切好；階梯的價值在「有結構就用、沒有就保底」，而非宣稱多數專案有漂亮的天然切點。

### 為何階梯優於純 cohesion 或純 size
- 純 cohesion：遇稠密團/無邊會卡（undefined）。
- 純 size：永遠能跑但盲切、功能碎裂最重、之後合併最貴。
- 階梯＝**有結構用結構（高品質）、沒結構用大小（保證有解）**，正是「通用為主軸、沒定義過的不撞牆」。

## 4. Token 預算估計（通用的關鍵）

**鐵則：不寫死任何 per-node token 常數**（spike 的 357 是 The Door 的值，換 codebase 即失準；寫死＝典型撞牆陷阱）。

- **逐節點實估**：每個 node 的 view 序列化字元數已可得（`regions/*.json.gz`）。用保守 char→token 換算，且 **CJK 字元另計**（1 中文字 ≈ 1 token 但僅 1 char，不分開會嚴重低估）。打包累加的是**每節點實估值**，非常數×節點數。triage（§2）與切分（§3）共用此估計器。
- **`target_tokens` 為參數**：呼叫方傳入（適配 200k / 1M 不同 agent window）。預設取保守值（建議 100k，留一半給推理/輸出；確切預設值由實作計畫定）。
- **單節點 > 預算的極端**：極少見（單一超巨 docstring）。保底＝該節點**自成一 chunk** 並標警示旗標，絕不丟棄、不切壞節點。

## 5. 決定性、複用、品質訊號、輸出形態

- **純決定性**：同 structure + 同 `target_tokens` → 同一組 chunk（穩定排序 + 決定性遍歷）。可重現、可測、**零 LLM、零 token 成本**（切分是結構計算，符合 CLAUDE.md 閘門：結構分析走純程式）。
- **複用 region 當「粗切第一刀」（可選優化）**：先按現有 `region`（locality、免費）分，再只對**超預算的 region** 跑 Tier 1-3。小專案常一刀都不用切。**不改 `region_partition` 行為**——只借其輸出當 chunking 的起點。
- **品質訊號（合併雖出範圍，仍要可觀測）**：輸出附 rollup：`chunk_count`、各 chunk `est_tokens`、`cross_chunk_edges`、各 chunk 用到的 `tier`。
  - `cross_chunk_edges` 定義＝**原圖中、兩端點落在不同 chunk 的邊數**。注意把多個獨立連通分量併入同一 chunk **不產生** cut 邊（分量間本就無邊），故 cut 只來自 Tier 2/3 在分量「內部」的切口。跨塊邊越少＝功能碎裂越少＝日後合併越省。
- **輸出形態**：一份 chunk 計畫
  ```json
  {
    "target_tokens": 100000,
    "regime": "medium",
    "needs_split": true,
    "total_est_tokens": 612000,
    "chunks": [
      {"chunk_id": "chunk-001", "node_ids": ["pkg/a.py::Foo", "..."],
       "est_tokens": 84213, "tier": "cohesion"}
    ],
    "rollup": {"chunk_count": 7, "cross_chunk_edges": 41,
               "oversized_node_warnings": []}
  }
  ```
  small regime → `needs_split: false`、`chunks` 為單一「整個專案」chunk。
  **只回 node_id 清單**（agent 各自再去讀對應 view）。本 spec 只負責「算出怎麼切」，不負責派工、不負責合併。

## 6. 通用性保證（為何任何輸入都不撞牆）

- Tier 3（size-slicing）在**任意**節點集合上有定義 → 階梯一定終止、一定產出合法 chunk。
- 估計用**逐節點實測**，不依賴語言/框架/路徑慣例 → 跨 codebase 通用，遇沒見過的語言也只是「邊較少」而非「無法處理」。
- triage 用**連續比值**分流、非列舉專案類型 → 沒有「沒定義過的專案種類」。
- 零路徑名/語言/框架的列舉判斷（延續 `region_partition` 的「零路徑名寫死」精神）。

## 7. 非目標（明確排除）

- **企業級超大型專案的分層策略**（chunk-of-chunks / 粗pass再細分 / 多級編排）——目前不在考量；triage 的 `large` 只給標籤，不給分層演算法。真有需求再開獨立 spec。
- **不**做跨塊 feature 去重/衝突仲裁（合併層，後續 spec）。
- **不**做實際 subagent 派工/編排（dispatch 層，後續 spec）。
- **不**引圖論大套件（networkx 等重依賴）——啟發式自寫、保持 dependency-light（通用型基礎建設原則）。
- **不**改 `region_partition`、不改 `extract_structure` 輸出、不 bump 契約、不動 gate。
- **不**用 LLM 做切分或 triage（皆純結構計算）。

## 8. 介面落點（待實作計畫定案）

傾向新增純函式核心（如 `core/structure_view/chunk_planner.py`），輸入 `codebase_path`（讀既有 structure-view artifact）+ `target_tokens`，輸出上述 chunk 計畫（含 triage 的 regime/needs_split）。是否包 MCP/CLI 轉接由實作計畫與後續 dispatch spec 決定——本 spec 不強制。

## 9. 測試方向（驗證切分器）

- **Triage 分流**：構造 total ≤ 預算 → `regime=small`、`needs_split=false`、單一 chunk；構造 total 略超 → `medium`、多 chunk；構造 total 遠超 `large_ratio×預算` → `large` 標籤但演算法同 medium。
- **決定性**：同輸入同預算 → 同輸出（多跑數次斷言一致）。
- **預算遵守**：每個 chunk `est_tokens ≤ target_tokens`（除單節點超標的標記例外）。
- **窮盡且不重**：所有節點恰好出現在一個 chunk（聯集＝全集、兩兩不交）。
- **Tier 1 cohesion**：構造「兩個明顯分離的連通子圖（皆 ≤ 預算）」→ 斷言各自成塊或被 cut-free 打包、`cross_chunk_edges`＝0。
- **Tier 1 零邊打包**：構造「一堆零邊節點」（各自獨立分量）→ 斷言被打包進 ≤ 預算的 chunk、`cross_chunk_edges`＝0、不拋例外。
- **Tier 2 切分**：構造「單一連通但超預算」（含稠密團）→ 斷言被切成多個 ≤ 預算子塊、tier＝`bisect`、切點邊數有記錄。
- **Tier 3 原語/oversized**：構造「單節點 est > 預算」→ 斷言該節點自成 chunk、標 `oversized`、不拋例外；`_slice_by_order` 對任意序都產出合法切分。
- **CJK 估計**：含大量中文 docstring 的節點 → 斷言估值不被低估到塞爆預算。
- **真實資料**：對 v170 structure-view 跑，斷言 regime 合理、chunk 數合理、無 chunk 超預算、全節點覆蓋。
- 測試鏡像 repo 結構（`tests/unit/core/structure_view/`）。
