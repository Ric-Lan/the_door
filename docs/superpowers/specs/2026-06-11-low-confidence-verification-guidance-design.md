# Design — 非-high 信心交叉驗證引導（cross-verification guidance for non-high-confidence judgements）— 2026-06-11

> **讀者＝LLM 執行者（非人類）**：本檔以 exact／單一權威定義為準。範圍術語見 §3.3
> 「🔑 觸發處境（canonical）」——全文唯一定義，他節一律引用該名、不重述。
> （檔名 slug 仍保留 `low-confidence`；標題已放寬為「非-high」，以 §3.3 canonical 為準。）

> 承本 session a/2c 探索的方向修正（使用者主導）。核心主張：**把「補強不確定
> 判斷的證據」做成 LLM 可自由取用的工具調用引導，而非基礎設施層 hardcode 跨產出
> 交叉。** 見 [[feedback_evidence_via_tool_registry]]。
> 流程：spike(已完成、見 §2)→spec(本檔)→雙審(concept --design)→plan→雙審→TDD。
>
> **🔴 去污染註記（2026-06-11 重驗）**：本檔前一版的 §6 驗收＋「critical #2 已排除」
> 裁定被使用者判定污染作廢（援引不存在的 dogfood、把污染內省洗成 high-confidence 定論）。
> 本版 §3.3 與 §6 已依使用者重驗時的裁決重寫。§5 facts 已抽樣重讀碼確認屬實。
> 見 [[feedback_no_phantom_verification]]、[[handoff_2026_06_11_e]]。

## 1. Problem

The Door 的工具輸出帶「不確定」標記（confidence∈{medium,low}、confidence 未評估/None、
孤立節點、doubt），但 **LLM 拿到一個非-high 信心判斷（＝§3.3「觸發處境」）時，沒有任何
引導告訴它「可以用哪些已註冊工具去交叉驗證」**。結果：

- 要嘛 LLM 憑記憶/猜測翻譯非-high 信心內容（不忠實）。
- 要嘛我們在基礎設施層 hardcode「A 低信心 → 自動查 B 殘餘並塞進去」——這是**強制
  並列兩個產出**、不是強證據；且每多一個不確定來源就多一條 O(N²) 硬連線 →
  **越走越窄、為特定功能（死碼/惡意偵測）把專案極端化**。

The Door 是**通用型**基礎建設，目的是給 LLM 足夠**證據鏈**做忠實翻譯。強證據＝
**LLM 主動針對它當下的不確定、去調工具拿到的佐證**。

## 2. Spike 已驗事實（真實碼，2026-06-11，避免事後再驗）

- **缺的主要是引導、不是工具**：`extract_structure`（`server.py` 已註冊）回傳完整
  `nodes/edges/topology`，含 edge `resolution`（fresh 抽取 v170：2782 node / 7481 edge，
  resolution 分布 import_alias 43.5% / name_match 20.3% / scope_rule 19.7% /
  name_match_ambiguous 16.5% / **skipped_dynamic 0%**）。LLM 拿到後**本來就能**查任一
  節點的 callers（掃 edges where `to==X`）、resolution、in_degree → 交叉驗證「孤立/
  低信心」。**第一刀不需要新查詢工具，證據源已存在且非空。**
- **MCP 工具註冊機制已備**：`server.py` `list_tools()` / `call_tool()`，agent-LLM
  本來就能自由調用任何註冊工具（這正是使用者指的「工具註冊環節」）。
- **per-response 注入點＝`mcp/tools/_response_envelope.py::wrap`**：每個工具回應都呼叫
  `wrap` 注入 `next_actions`。現狀 `wrap` 只跑 global state-driven 的
  `NextActionSuggester`、**不看 payload 內容**。（2026-06-11 重讀碼確認：`wrap` 僅跑
  `StateInspector().inspect()` + `NextActionSuggester().suggest(state)`。）
- **`NextActionSuggester`（guidance/suggester.py）是 per-project state-driven**（`_RULES`
  全是對 `SystemState` 的 predicate：`has_dot_the_door`、snapshot 數、`warnings`、drift）→
  **結構上不適合** per-judgement 低信心引導；硬塞會把判斷層的東西塞進專案層（重蹈「走窄」）。
- **殘餘（edge-residue）目前是空的**（skipped_dynamic 0%，因輸入端 indeterminacy
  偵測器只認「外層函式名 == `__getattr__`/`getattr`」），且 `edge-residue.json` 只有
  writer 無 content reader、confidence/doubt 完全不引用它。⟹ **殘餘不能當第一刀的
  證據源**（會回空、無價值）；它是未來可註冊的第二證據源。

## 3. Decision

立一個**通用骨架**：帶不確定的工具回應，附一條 LLM 可自由取用的**交叉驗證引導**，
指向**已註冊**的證據工具。**零新工具、零基礎設施硬連線、不依賴殘餘修復。**

### 3.1 骨架（per-response，掛在 `wrap` 後置）

在 `wrap` 注入 `next_actions` 之後（或並列欄位），加一個**通用、與工具無關**的
verification-guidance 投影：

- 它**不替 LLM 判斷、不自動交叉、不塞結論**。它只宣告：「此類輸出若有不確定判斷，
  可調用這些已註冊證據工具來交叉驗證」+ 每個工具的一句用法。
- LLM 當 orchestrator：自己看 confidence、自己決定調不調、調哪個、怎麼用、結論為何。

### 3.2 證據工具清單（第一版＝零新工具）

- `extract_structure(codebase_path)` — 查節點的 callers/callees/resolution/topology
  （判斷「孤立」是真是假、低信心邊是否 ambiguous）。
- （未來增量註冊：殘餘查詢工具、`scope_verify`、`scan`……加進清單即可，零 N² 硬連線。）

### 3.3 設計叉路裁決（使用者拍板 2026-06-11）

> 前一版列 A（靜態通用宣告）vs B（infra 偵測 confidence∈{low,unknown} 才附）兩案待裁。

**裁決＝A 的機制 ＋ 觸發處境（見下 canonical）＋ 觸發是 LLM 自評。** 否決 B，理由：B 把
「哪一筆該繞回交叉驗證」誤放到**基礎設施掃 payload**——但這本來就是**引導 LLM 判斷**的
問題，不是 infra 偵測的問題；且 infra 掃 confidence enum 會漏掉「未評估(None)」與「中信心」。

**🔑 觸發處境（canonical，全文唯一權威定義；§1/§4/§5/§6 一律引用此名，不重述門檻）：**
> LLM 自評為**非-high 信心**的判斷 ＝ {未評估(confidence None) ∪ 中信心(medium) ∪ 低信心(low)}。

定案：

- **機制（A）**：`wrap` **不掃 payload、不偵測 confidence**，固定附一條靜態
  verification-guidance。基礎設施最 dumb、永不誤判「哪筆不確定」、實作最小。
- **引導內容**：觸發＝**觸發處境**（上方 canonical）。引導須分清處境內**兩種不同成因**
  （別混為一談、別把任一誤標成 noise／「不可評估」），各給對應動作：
  - **未評估**（confidence None）＝LLM **尚未執行**評估（**≠** 產出不可評估）
    → 去調 `extract_structure` 等工具**把評估補做**（可填補的流程缺口）。
  - **中/低信心**（medium／low）＝LLM **已評估、但證據不足**所顯示的中低水準
    → 去調工具**補強證據**。
  兩者都繞回交叉驗證。觸發是 **LLM 對自己當下判斷的自評**，不是 infra 對 payload 的偵測。
  > ⚠ 概念釘樁：confidence=None（未評估，feature 層）**不等於** edge 層 `skipped_dynamic`
  > （dynamic dispatch 的結構性 indeterminate）。程式上前者在 `confidence_membrane` 退
  > `NoisePosition(indeterminate)` 只是「不自鑄 default」的記帳，**不代表「未評估＝noise、
  > 該排除」**。本專案前提：解析後翻譯受限於 LLM 模型本身能力，故「未評估」與「中/低信心」
  > 都是該交叉驗證的處境。
- **性質**：這是「引導 LLM 判斷」，不是把基礎設施 smart 化。智慧留在引導**措辭**裡、
  交付給 LLM；基礎設施只負責穩定地把這條引導擺上桌。

## 4. Scope

In（第一刀）：
- `wrap`（或新 `verification_guidance` 投影模組）：附通用交叉驗證引導（靜態、涵蓋**觸發處境**）。
- 引導清單第一版只列 `extract_structure`（已註冊）。
- 測試：引導出現在工具回應、內容穩定、措辭涵蓋**觸發處境**兩成因（未評估／中低信心）、
  與既有 `next_actions` 並存不衝突。

Out（明確不做、未來增量）：
- **新查詢工具**（殘餘查詢等）——第一刀證據源用既有 `extract_structure`。
- **輸入端 indeterminacy 偵測修復**（讓殘餘非空）——獨立後續，第一刀不依賴。
- **可達性/孤立分類器、傳遞信心傳播、死碼/惡意**——那是把專案極端化，明確不做。
- **改 `NextActionSuggester` global 流程**——接入點是 per-response `wrap`，不碰 global。
- **基礎設施自動交叉/塞結論／infra 偵測 confidence**——違背「LLM 自由取用、LLM 自評
  觸發」，明確不做（即否決的 B 案）。

## 5. Backward-compat / 風險

- 純加法：`wrap` 多注入一個欄位（或 next_actions 多一條），既有消費者忽略即相容。
- 無 schema、無 `SNAPSHOT_CONTRACT_VERSION` bump（非持久化）。viewer 不讀此引導。
- **A 的已知代價（grep 實證）**：`wrap` 覆蓋所有 MCP 工具，故引導會附到**不帶信心判斷的
  回應**（project_list／render／system_status…）＝可接受的輕微雜訊；換得基礎設施零偵測、
  永不誤判「哪筆是觸發處境」。註：字串 `"unknown"` 僅 viewer 路徑（view_model）呈現未評估、
  非 MCP 膜路徑（MCP 的 None 走 `NoisePosition(indeterminate)`），勿混。
- 風險：引導措辭若太指令式 → 又變「基礎設施替 LLM 決定」。措辭須是「可選證據來源 + 用法 +
  觸發處境自評」，非「你必須查 X」。雙審把關。

## 6. Verification（兩層；artifact 層 pytest、efficacy 層 LLM@分級信心）

> **方法論（2026-06-11 使用者拍板）**：pytest 綠燈「代表目的達成」這步結論本身也是
> LLM 判斷——沒有逃離判斷這回事。故 efficacy 層的測試標準就是 LLM 自己，用**分級信心
> ＋攤開理由**表達，**禁止**援引 phantom 機制（dogfood）、**禁止**把 low/medium 洗成
> high 定論。見 [[feedback_no_phantom_verification]]。

### 6.1 Artifact 層（pytest 可驗，硬性）

- 結構斷言：帶不確定的工具回應（如 analyze_changes）含 verification-guidance；其列出的
  證據工具名 ∈ 已註冊工具集（釘「不會指向不存在的工具」）。
- 門檻斷言：引導文案明含**兩種成因**——「未評估（LLM 未執行評估）」與「中/低信心（已評估、
  證據不足）」——且各帶對應動作（補做評估 ／ 補強證據）；不把「未評估」誤標成 noise 或
  「不可評估」，不把它與 edge 層 `skipped_dynamic` 混為一談。
- 措辭斷言：引導文案為「可選/建議」語氣、含工具用法、不含強制性字眼（守「LLM 自由」）。
- 並存斷言：既有 `next_actions` 不被破壞、形狀不變。
- 通用性釘樁：引導與「死碼/惡意/可達性」零耦合（純通用證據引導）。
- 全套 `python -m pytest` 零回歸。

### 6.2 Efficacy 層（LLM 判斷 @ 分級信心，攤開理由）

對「靜態建議式引導能否讓消費端 LLM 更傾向忠實翻譯**觸發處境**（未評估／中低信心）判斷」逐項裁決：

| 子命題 | 判斷 | 信心 | 理由（可被反駁） |
|---|---|---|---|
| 引導淨正、無誤導風險 | 成立 | medium-high | 純加法、建議語氣、指向工具已註冊；最壞被忽略、不帶歪。 |
| 與專案既有影響論一致 | 成立 | high | 整套 agent-as-LLM 本就靠 CLAUDE.md／next_actions 這類 guidance 塑形行為。 |
| 引導**實質改變**行為→更忠實 | 部分成立、有上限 | **low** | spike 證 LLM「本來就能」查 callers/resolution；引導是**提醒效應**、不給新能力，邊際提升真實但小、未量測。 |

**綜合裁決**：「無害且方向正確」medium-high；「實質改變行為」誠實 **low**。此 low 即如實
寫入、由使用者決定 low 是否足夠開工——這正是 feature 自己要的低信心態度用在自身（自洽）。
**不得**把此 low 洗成「critical 已排除」之類的 high 定論。
