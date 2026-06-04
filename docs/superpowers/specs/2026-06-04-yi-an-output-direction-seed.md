# 乙案種子：基礎設施輸出方向（意義經結構送達 LLM）＋ audit_conformance 首個試點

> **日期**：2026-06-04　**狀態**：種子（pre-spec；整體方向待下個對話討論定調）
> **性質**：本檔不是完整 spec。它收斂「乙案」這一輪概念討論的成果，給下個對話一個具體立足點。
> **承接**：memory `todo_output_direction_assessment`（乙案延後版命題）、`project_finding_b_closed_no_b3`（Finding B 收工、ui/serializers.py＝乙案切入點）、B-2 `DoubtLifecycle`（乙案 doubt 面地基）。

---

## 0. 一句話命題（乙案，待下個對話確認/收窄）

**基礎設施輸出的「意義」，要經由結構／呈現送達消費端 LLM，而不是靠 prompt。** 橫跨所有 LLM-facing 面（MCP schema / snapshot / scope / doubt / L1-L2 / 診斷），須一致地做。**它是「改輸出契約」，與「內部重構」性質相反**——所以留到重構 campaign（Finding A/B 等）收尾後，當獨立 campaign 啟動。

**鐵律（Q1 風險，沿用 Finding A 寫嚴讀寬）**：結構化**不可**從「標註」滑成「過濾」——**加法不減法、寬容讀、保自由文字、動輸出前先補 characterization test**。

> ⚠️ 整體方向（範圍、優先序、是否全面 vs 逐面）**尚未定**，是下個對話的主題。本種子只確立**設計原則**與**第一個具體試點**，不預設整體路線。

---

## 1. 為什麼選 audit_conformance 當第一個試點

`SnapshotStore.audit_conformance()`（`core/diff/snapshot_store.py:260`）是 Finding A 留下的**唯讀契約校驗**：逐一把磁碟上每份 snapshot 對照現行 schema 重驗，回報不合格者。**現況問題（本輪挖出）**：

1. **發現端**：它**零外部呼叫者**——沒有 CLI、沒有 MCP tool、不在 CLAUDE.md 表、不在任何 `next_actions`。**LLM 目前無法得知它存在。**
2. **輸出端**：回 `list[{version_id, file, error}]`，其中 `error` 是 `str(jsonschema.ValidationError)`＝**原始驗證器殘渣、不可行動**。消費端得自己重新詮釋才知道「嚴不嚴重、該怎麼辦」。

兩頭都不接消費端 → 它「介在有跟沒有之間」。**正因兩個缺口都落在「意義如何送達消費端 LLM」上，它天然就是乙案在 doubt/診斷面的最小、最具體試點。** 修好它＝替乙案打一個可複製的樣板。

**使用情境（本輪確立）**：audit_conformance 是**讀取端 agent 的「上場前信任檢查」工具**——當 agent 要倚賴一批**可能來自舊契約**的歷史快照時，由它自己判斷後取用。
- 起疑訊號**來自脈絡、非資料內容**（「這批快照是舊版本寫的」「使用者剛升級/手改過檔」「我要做高風險跨版本比較」）；光讀值判斷不出合不合約。
- 它真正擋的是**「載得進來、但已偏離收緊後 schema」的沉默瑕疵**（讀不出來的損毀檔，其他路徑本就會報）。

---

## 2. 發現管道：LLM 怎麼知道有這個工具（現況三層）

The Door 現有的工具發現機制有三層，audit_conformance **三層全缺席**；正做要選它走哪幾條：

| 層 | 機制 | 現況 | 對 audit 的用法 |
|---|---|---|---|
| L1 | MCP `list_tools` 註冊表（`mcp/server.py`）：`name` + **一句話 description** | audit 無 tool 檔、不在表 | 寫一句精準 description（agent 自主取用靠它） |
| L2 | CLAUDE.md「Commands & MCP tool reference」表：`Use when…` 語意 | audit 不在表 | 補一列「什麼情境用」 |
| L3 | `_response_envelope.wrap` 推送的 `next_actions`（StateInspector + NextActionSuggester） | 無 action 提及 audit | status 偵測版本落差時，**主動推**「跑稽核」 |

**兩種使用定位 → 對應兩條管道（不互斥，正做兩者都接）**：
- **agent 自主判斷取用** ＝ 靠 L1 + L2（description + when-to-use）。
- **機械式安全網** ＝ 靠 L3（status 偵測版本落差 → 推 next_action）。主戲是前者，後者是後備。

---

## 3. 輸出內容的理論基底（已過濾；理論當磨刀非背書）

> 本節是本輪核心成果。每條都過「能換具體欄位 + 不過度設計 + 不虛假堆疊」三檢。被剃除者見 §3.x「剔除紀錄」。

### 總綱：決策充分性
**只吐「會改變消費端那個信任決定」的事實——不多、不少；且事實必須為真。**
- **下界（不能太少）**＝可行動：不丟原始 jsonschema 殘渣。
- **上界（不能太多）**＝不越界裁決：不替消費端算「信任分數」或下最終裁決（agent-as-LLM：判斷權在 agent）。

### 上界主論證：脈絡盲 ⇒ 裁決無效（事實審/法律審分離）
工具**結構上拿不到消費端當下的上下文**。同一個 schema 破壞，A 任務致命、B 任務可容忍 → **工具給分數＝基於虛無上下文的無效審判**。工具定位為**事實發現者（fact-finder）**，嚴禁進入裁決層。

### 上界操作規則：去暗示、去情感命名
欄位一律陳述事實、不得帶裁決暗示。
- ✅ `breaking_changes_count: 3`、`produced_under: "vX"`、`current: "vY"`
- ❌ `risk_level: "high"`（越界裁決）、裸 `contract_drift: true`（偏弱，改用 produced_under/current 配對，自帶病因又不越界）

### 下界操作規則：每一類自帶「它那個決定所需的證據」（結構即證據、免翻譯層）
- `domain_violation`（值超出收緊後範圍/列舉）→ 必附 `expected: [...], found: <v>`
- `missing_required`（舊契約缺新必填欄位）→ 必附是哪個欄位
- `forward_noise`（多出現在不認得的欄位）→ 必附是哪些欄位
- （`corrupt`／讀不出來 → 另類，標明不在相容性光譜上）
- ⚠️ **不宣稱**「形狀與行動物理合一/直接映射 agent 內部 action 函數」——只到「**不需要翻譯層**」，不替消費端內部結構打包票。

### 分類骨幹：schema 演化相容性（四類有背書、非拍腦袋）
對應 Avro/Protobuf 的 backward/forward compatibility 標準判準：加選填＝相容（forward_noise）；變必填/移除＝向後破壞（missing_required）；收窄型別/列舉＝定義域破壞（domain_violation）；讀不出＝損毀（corrupt，另類）。**只用四個列舉值，不上型別子型格。**

### 姿態：Postel 寫嚴讀寬
報告不改寫、唯讀、退出碼 0、**分類而不關閘**（沿用 Finding A：寫入 fail-closed＝寫嚴；audit＝寬讀那一側，不刪不擋只標）。

### 組織軸：provenance 世系（兩層輸出）
根本病因＝「這份快照出生於舊契約版本」，違規明細只是症狀。輸出**兩層**：
- **頂層**：`produced_under: vX`（或 `unknown (pre-stamp)`）＋ `current: vY`。
- **底層**：四類 + 每類自帶證據的違規明細。

### 3.x 剔除紀錄（過頭/疊影版本，不寫進設計）
- **信任分數 / severity 評分** — 越界裁決、脈絡盲、搶 agent 判斷。
- **遷移引擎**（自動改寫舊快照）— 違反寬讀（動了人家資料）、超出診斷職責。
- **型別子型格 / 形式相容代數** — 四類列舉已足，過度形式化。
- **程序正義（procedural justice）** — 不只冗餘：對 fact-finder 重心錯（診斷第一義務是**事實為真**，非過程透明；假陽性不管多透明都有害）。
- **麥克魯漢冷熱媒體 / 負空間** — 當論據＝圖解非證成、與 agent-as-LLM 同柱雙重計數；最多保留「極致冷工具」當記憶標籤。
- **Gibson + Norman 兩理論家並列** — 收成單一操作規則即可；且 Affordance／乙案／語用言語行為＝「意義經結構」三別名，三名一事不堆（乙案＝地基、Affordance＝操作化、語用＝欄位濾網）。
- **通則**：上界被「冷媒體＋負空間＋事實審＋程序正義」頂了四次的錯覺＝虛假支撐堆疊。實為**一原則（agent-as-LLM）＋一新規則（去暗示命名）＋一新論證（脈絡盲）**。

---

## 4. 過濾後的論據地圖

```
總綱：決策充分性（只吐改變信任決定的事實；事實必須為真）
  ├─ 上界（不越界裁決）
  │     主論證 = 脈絡盲⇒裁決無效（事實審/法律審分離）
  │     操作規則 = 去暗示去情感命名（breaking_changes_count；禁 risk_level）
  ├─ 下界（可行動）
  │     操作規則 = 每類自帶決定所需證據（expected/found…），結構即證據、免翻譯層
  ├─ 分類骨幹 = schema 演化相容性（四類：forward_noise/missing_required/domain_violation/corrupt）
  ├─ 姿態 = Postel 寫嚴讀寬（報告不改寫、退出 0、分類不關閘）
  └─ 組織軸 = provenance 世系（兩層：頂層 produced_under/current；底層分類違規）
砍除：信任分數、遷移引擎、型別子型格、程序正義、媒體理論當論據
補充鏡（非柱）：診斷即促成行動 → 只當「這欄會促成動作嗎？不會就砍」的濾網
```

---

## 5. 版本戳前置與其界線（技術誠實）

provenance 主軸需要 snapshot 記錄**出生時的契約/schema 版本戳**。**界線**：
- 版本戳**只惠及它落地之後寫的快照**。
- **所有既有快照都沒戳** → 對它們 `produced_under = unknown (pre-stamp)`，**底層分類違規清單退不掉、仍是主要證據**。
- 故「技術租金」的回報**面向未來快照**，對既有資料還不回來。**不削弱「該做」，只是 spec 不可開它給不出的空頭支票。**

---

## 6. 正做的範圍（已定）＋ 待下個對話拍板的點

**範圍＝正做**（非窄做）：暴露成 MCP tool + 重設計輸出語意分類 + 選好發現管道。窄做（只接線、輸出維持原樣）已否決＝留半成品。

**待下個對話（先談乙案整體方向，再回到本試點）**：
1. **乙案整體方向**：範圍/優先序、全面 vs 逐面、哪些 LLM-facing 面先做（此為主議題）。
2. 版本戳：要不要把「給 snapshot 補契約版本戳」當本試點的前置小補丁（連帶餵 status 版本落差偵測）？
3. 發現管道：L1+L2+L3 全接，還是先 L1+L2（自主取用）、L3（status 推送）待版本戳後？
4. 本試點是否就當乙案的**樣板刀**先落地（spec→plan→characterization→impl），再據經驗推廣到其他面。

---

## 7. 寫成正式 spec 前必做（沿用既有紀律）
- **先補 characterization test** 釘 audit_conformance 現有行為（動輸出契約前的安全網；Q1 鐵律）。
- spec 寫完跑 7 點審查；第 4 點 grep 真實碼驗 API 名（`audit_conformance`/`_get_snapshot_schema`/`wrap`/`StateInspector`/`NextActionSuggester` 皆已存在、本輪 grep 確認）。
- 文件給 Claude Code 讀：結構化、exact code、零佔位符。
