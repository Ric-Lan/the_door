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

---

# 8. 理論基底（三輪過濾後帳本）— 2026-06-04 理論討論成果

> 本節是 §0~§7 之上的概念升級：乙案的雜訊處理已從「逐面標註」演化成一個**座標模型**。
> 性質仍是**種子/理論**，非 spec。**剔除紀錄（§8.4）是本節最耐久的資產**——它擋下個對話把已否決的理論（量子塌縮 / Dither / 基數=K / 生產端熔斷）當權威搬回。

## 8.1 核心原則（已確認，使用者拍板）

> ▲ **已升級**：本節是 A 面起步時的原始命題。**現行權威版＝ §8.10 的統一命題（膜模型）**；下列「加法不減法」的範圍已由 §8.12 修正②收窄。本節保留為脈絡起點，讀時以 §8.10/§8.12 為準。

**The Door 吐給消費端 LLM 的每一份輸出，其「用途／意義」必須由結構本身承載（明確標示或呈現形式不同），不能靠 prompt 補述。**

兩個不可漏的限定：
1. **專案級、一次性、全面套用**（非模組級）。只挑一面做＝製造新不一致。→ 延到重構 campaign 收尾後當獨立 pass。
2. **Q1 鐵律＝加法不減法，但僅限 A 側（讀/OWA）**：讀出開放殘餘時永不減法（真相含 legacy enum、自由文字）。**B 側（寫/CWA）相反——嚴格封閉 enum**（見 §8.12 修正②）。統一為寫嚴讀寬分側施作。結構化是讓 LLM 判斷更準，不是替它預先裁決/過濾。

## 8.2 承重理論骨幹（過濾後＝脊椎，其餘皆推論或稜鏡）

| 代號 | 理論 | 角色 |
|---|---|---|
| **A** | 判斷分工：工具是 fact-finder 非裁決者（事實審/法律審分離 + 脈絡盲⇒裁決無效） | 脊椎。下游「不給分數/不關閘/只標事實」皆源於此。 |
| **B** | 意義經結構送達、不靠 prompt（符號學所指須結構承載 + Norman affordance） | 脊椎。與 A 正交。 |
| **C** | 翻譯即驗核投影（technical→functional，為特定讀者做的有損分層投影） | 產品前提。 |
| **D** | 寫嚴讀寬（Postel：寫入 fail-closed，讀出寬容、分類而不關閘） | 脊椎。 |
| **E** | 直覺主義/拒絕排中律（格內古典邏輯、格外拒絕 P∨¬P；誠實不完備＝邏輯必然） | **本輪新增支柱**。 |
| 鐵律 | 加法不減法/標註不過濾 | **B×D 的推論**，非獨立公理。 |
| 哲學定錨 | 本體論→認識論轉向 | **本體論未消失，被「嚴格寫入契約」封界**；那條界線＝本體論/認識論分界。→ §8.10：被封界的本體論＝**膜內 B（CWA）側**；認識論＝**膜外 A（OWA）側**。同一條線、兩個名字。 |

## 8.3 雜訊處理形式：座標模型（核心成果）

**範式轉換**：從「定義雜訊**是什麼**（本體，發散、注定失敗）」轉向「定義系統**如何感知/定位**雜訊（認識，有界）」。逃出無限窮舉的合法性全靠此轉向。

```
前三主軸（信心/世系/範圍）         ← 每元素都有座標・格內・古典邏輯
  └─ 殘餘格 → 第四軸：缺口性質       ← 條件軸・只在 off-grid 取值・格外・直覺主義
        │     封頂 ≤4 值（見下）
        └─ 連性質都命不出 → 觸底旗標「存在未刻畫內容」  ← 一個 bit・洩壓閥
              └─ 連『有東西』都察覺不到 → unknown-unknown  ← 不可表示・由「永不刪」政策守・非軸守
```

- **三主軸（格內・古典）**：`confidence`（high/low）・`provenance`（current/legacy/unknown）・`scope`（in/out/unrecognized）。每值自帶意義（守 B）。軸須正交、不可同縫別名。
  - ▲ **`provenance` 不是次要/退化軸**（§8.9 曾誤判其在 edge 面退化）：§8.10 接點①證明它是 **B 側的承重軸**（enum 對比集版本相對，改一值全體差異重平衡）。它在 A、B 兩面都承重。界線見 §8.13-O3（pre-stamp 快照 provenance=unknown）。
- **第四條件軸 = 缺口性質（格外・直覺主義）**，封頂 ≤4 值，分類的是「**不知道的方式**」而非「不知道的東西」：
  - `evolutionary`：契約演進造成、**可回收**（擴約後回格內）。
  - `reserved`：自由文字、**刻意永久開放、永不上格**（唯一不可且不該回收者）。
  - `indeterminate`：靜態不可判定（動態派發類）、真值本身未定。
  - `corrupt`：讀不出、不在相容光譜上（製圖學上＝「海圖破了」第三類，非未知之地）。
- **觸底旗標**＝洩壓閥：新冒出的「不知道的方式」先掉進旗標，**不逼第四軸加值**——這是第四軸能維持低基數的機制。
- **unknown-unknown**：原則上不可表示（如康德物自身），只能靠寬讀留負空間，讓日後脈絡更足的讀者自己認出。
- **殘餘格恆帶三件**：`性質`(第四軸) ＋ `基數`(量) ＋ `比例`(佔全體 %)。
- **雜訊的嚴格定義** = 高 **K(x│contract)**（以契約當解壓器的條件柯氏複雜度）；**非** K(x)，**非**基數。此定義自動解釋 `evolutionary` 可回收（換解壓器→條件 K 下降）。
- **兩層輸出**：**事實層**（單調、永不減法、保真，含內在內容/bytes）／**呈現層**（可逆壓縮：聚合/摘要，**但壓縮 token 必須帶座標＋基數使可下鑽還原**，否則＝暗箱裁決＝偷渡減法）。
- **權責切分**：生產端**只有框架權、沒有裁決權**（給座標/保尺寸/刻邊緣）；`留/丟`、`熔斷` 等決定**全在消費端**在其任務脈絡裡下。

## 8.4 理論收貨帳本（收 / 補充稜鏡 / 剔除，附理由）

> 紀律：每條過「能換具體改動 ＋ 不過度設計 ＋ 不同縫別名」三檢。理論當磨刀非背書。

| 理論 | 判定 | 理由 / 失效點 |
|---|---|---|
| 本體論→認識論 | **收（框架）** | 逃出窮舉的合法性來源。收窄：本體論被嚴格契約封界、未消失。 |
| 直覺主義/非排中律（布勞威爾） | **收（新支柱 E）** | 誠實不完備＝邏輯必然。**劃範圍：格內古典、格外直覺主義**。是被剔除「量子塌縮」的 sound 替身。 |
| 柯氏複雜度（條件版） | **半收** | 雜訊嚴格定義＝高 K(x│contract)，解釋可回收性。 |
| 符號學（皮爾斯無限符號過程） | 補充稜鏡 | 「操作型定錨/habit」是 B 的別名。**修正**：座標是「錨定＋延遲」非「切斷」（切斷會把裁決偷渡回生產端）。 |
| 製圖學 Terra Incognita | 補充稜鏡＋檢驗尺 | 與座標模型同構；獨立檢驗四值（fog/high-sea/torn-chart），反證 corrupt＝另類。 |
| 藝術體制論（迪基） | 補充稜鏡 | 口號「框架權≠裁決權」（A 的利落講法）。**劃範圍**：身分由框架賦予，但**內容仍內在保真**（非純體制論）。 |
| 康德 感性形式/物自身 | 補充稜鏡 | 認識論轉向別名。加值：釘死最底層「原則上不可表示」。失效點：康德感性形式先天固定，我們的軸契約可變。 |
| 留白/老子「當其無」/互補原理 | **三名一事→收成一條** | 同一概念出現三次（同縫別名）。收成操作規則「不填空、只刻邊」＝已是第四軸設計。 |
| 標記性 markedness（語言學） | 補充稜鏡 | 給「例外＝有標記、正常＝無標記」一個家。 |
| RAG 向量空間 | **核留・殼剔** | 留「查詢相對門檻＋多軸定位＋永不刪」；剔 embedding（不可讀座標＝違反 B）/ANN/vector-DB（通用三檢全中）。 |
| 量子 波函數塌縮 | **剔除/警示** | 過度宣稱疊加態——我們座標寫入時即確定位置，變的是消費端門檻。只在 `indeterminate` 格成立；全域套用誘人存機率分佈（往 RAG 漂）。 |
| 音響 Dither/噪底 | **剔除** | 機制錯配（dither＝注入去相關噪音；我們＝保留原生真相）。殘餘＝「報基數」已從聚合題導出，非新。 |
| 基數＝柯氏複雜度 | **剔除** | 範疇錯誤：基數是計數、K 是描述長度，可任意背離。 |
| 生產端「熔斷」機制 | **剔除（意圖保留、位置移正）** | 生產端關閘＝違反 A＋寬讀。改：生產端只報比例，熔斷是消費端決定。 |

## 8.5 待確認（理論層級未解的真死結）

- **待確認①（分流的制度記憶）**：消費端的「放棄」要不要、能不能變成可持久化事實？卡在 A 禁區（工具不能裁決）vs「全體消費者每次重付分流成本」之真痛。可能出路＝放棄由 agent 寫回成一條 doubt/註記（但範圍會擴）。**未解。**
- **待確認②（聚合算不算減法）**：呈現層「非破壞壓縮」與「加法不減法」的邊界。暫定判準：**壓縮 token 帶座標＋基數使可下鑽＝非破壞；帶不出＝偷渡減法**。判準已立、邊界案例未窮舉。

## 8.6 通用性交叉驗證（2026-06-04 執行，三法交叉）

**結論先行**：座標模型在**框架層獲驗證**——4 個成熟領域獨立收斂到其核心動作，主要案例通過證偽；但有 **3 個 spec 前必解的軟點（F1/F2/F3）**。

### 驗證法一：跨域 prior-art 收斂（獨立領域落到同一形式）
| 外部領域 | 收斂到的動作 | 關鍵事實 |
|---|---|---|
| 開放世界假設 OWA/CWA（語意網 OWL/SHACL） | **直接命中 D 寫嚴讀寬** | SHACL 用 **CWA 驗證（寫嚴）**、OWL 用 **OWA 推理（讀寬）**——成熟系統**獨立**做出同一切分。OWA「不知為真即未知、非偽」＝拒絕排中律（證實 E）。OWA 是**為最異質系統（web）而選**＝通用性外部背書。 |
| 拒絕選項/選擇性預測（Chow 1957、SelectiveNet、conformal prediction） | flag/abstain ＋ 切點有成本 | 「不確定就棄權」是 60 年成熟實務。切點成本必然存在、必須有人付——我們放消費端（守 A）。 |
| Dempster-Shafer（未承諾質量） | confidence(不確定) vs flag(無知) 分離 | DST 把一部分信念**留給全集＝無知/未承諾質量**＝觸底旗標。**DST 區分 ignorance≠conflict**→反向揭露可能缺第 5 模式（F3）。 |
| 型論 unknown vs any、W3C PROV | 旁證 | `unknown`＝消費端用前須先確立；PROV＝世系作一級元資料。 |

### 驗證法二：證偽（主動找破口）
- **通過**：主要案例找不到「需要新『維』而非新『值』」的雜訊（volatility 等屬 signal-quality、不在雜訊空間 → S1：模型只治雜訊/例外空間，不宣稱是 signal 的完整標註 schema）。
- **S2**：`confidence` 是生產端**自身認識狀態**（安全），但不可漂成 severity/importance（去暗示命名是承重規則、非可選）。
- **F1（軟點）**：gap-kind **互斥性未立**——corrupt+reserved、evolutionary+indeterminate 可共現。須定**優先序 lattice 或允許有界子集**，否則 ≤4 封頂漏。
- **F2（軟點）**：兩層輸出的**可逆性 contingent on 發現管道**——消費端不知能下鑽則「可逆」為空。→ 待確認②與發現管道（§2）**耦合、須合併解**。
- **F3（軟點，外部理論揭露）**：DST 的 ignorance≠conflict 指出可能缺第 5 模式 **`conflicting`**（多來源/多規則互斥斷言，如 scope_rule vs name_match）。須對真實面驗證後決定收不收。

### 驗證法三：自我應用（dogfood 試點 audit_conformance）
座標模型套上 audit 自身輸出，**重新分割了 §3 原四類（非僅重貼標）**：`domain_violation`＝**格內**（欄位認得、值越界）→ 歸主軸；`forward_noise`/`missing_required`＝`evolutionary` 缺口；`corrupt`＝corrupt。→ 模型**做真功（re-partition），把「格內違規」與「格外缺口」分開**。

### 驗證到什麼程度（誠實界定）
- **站得住（框架層）**：范式（本體論→認識論）＋三脊椎動作（A/D/E）均有獨立成熟領域背書；通用性原則獲 OWA 外部背書。
- **未到（須收口）**：3 軟點 F1（互斥）/F3（conflict 第 5 模式）/F2（發現耦合）尚在理論層開放，spec 前必解。
- **資料來源**：OWA/CWA、reject-option、Dempster-Shafer 三領域以 web 查證（2026-06-04）。

## 8.7 整體方針（據驗證結果，避免隨意修改）

1. **採座標模型為全專案唯一標註形式**（一套軸、專案級慣例、非逐面碼）——守核心原則①。
2. **寫嚴讀寬正式立法為 CWA-寫 / OWA-讀**：寫入端嚴格契約＝定義「正常」（例外的補集）；讀出端開放世界、分類而永不關閘。
3. **切點成本歸消費端**（拒絕選項教訓）；基礎設施只供 `座標＋基數＋比例`，使消費端廉價下切。
4. **不 big-bang，序列執行**：① 理論收口 **F1/F3**（gap-kind 集合與互斥）→ ② 試點 **audit_conformance**（最小、自我應用已驗 re-partition）→ ③ 從試點萃取慣例 → ④ 才向各面推廣。守「避免隨意修改無應得效果」。
5. **F2：待確認②與發現管道合併成一個子問題解**（可逆性依賴可發現性）。
6. **待確認①（放棄的制度記憶）延後**——唯一觸 A 禁區的真死結，不阻擋其餘，試點後再回。

> 這一刀為概念上最大的一刀；主要原則＝通用性。專案已從「點線面」進展到「立體結構（座標模型）」。

## 8.8 第二輪驗證：對真實碼的經驗落點（2026-06-04，grep + read）

驗證從理論轉入真實碼。**結果：F3 收掉（負結果，certified）、F1 定向、揪出兩個真實 landing point（F4/F5）；兩層輸出經實證已存在。**

- **兩層輸出＝已實例化（實證）**：`core/llm/edge_projection.py::project_edges_for_prompt` 把 `{name_match_ambiguous, skipped_dynamic}` 邊折成 per-caller hint 餵 prompt、snapshot 保留全量 → 事實層（保真）/呈現層（壓縮）**非假說、已存在**。

- **F3 收掉（無第 5 模式 `conflicting`）**：`core/extraction/edge_builder.py::_resolve` 是**嚴格優先序 cascade**（dynamic→scope_rule→import_alias→name_match fallback、first-match-wins），產出單一 resolution ＋ *ambiguity* 標記（`name_match_ambiguous`），**從不記錄 conflict**。The Door 單一抽取真相源＋優先序收斂 → 完全坐在 DST 的 *ignorance* 側、無 *conflict* 側。DST 距離讓我去找、grep 證實其**結構性缺席**。**gap-kind 維持 4；spec 不建 conflict 處理。**

- **F1 定向（gap-kind＝單值優先序、非共現子集）**：沿用現碼 `_resolve` 慣例，gap-kind 取優先序 `corrupt > indeterminate > evolutionary > reserved`。此優先序**是知識上被迫的**（corrupt 讀不出→無法得知是否也 evolutionary），故安全、不違加法不減法。

- **F4（新 landing point｜邊解析丟敗者）**：`_resolve` 優先序收斂**靜默丟棄落敗解析**（scope_rule 贏→name_match 替代從不記錄）。對 under-determined 邊＝把**可知**的替代在寫入端減掉＝真實的加法不減法違反點。屬 ambiguity（落 confidence 軸）非 conflict。

- **F5（新 landing point｜呈現層壓縮失準）**：`project_edges_for_prompt` 雖證實兩層存在，但壓縮**失準**：①hint 用 `set` 去重 → **丟基數**（50 條折成 1 看不出）；②把 `name_match_ambiguous`(ignorance) 與 `skipped_dynamic`(indeterminate) **兩個不同 gap-kind 併一桶** → **丟座標**。依待確認②判準＝**偷渡減法**。修方：hint 帶 `{caller:{method:count}}` ＋ 保留 resolution-kind。

### 第二輪結論
座標模型**對真實碼可落地、且已部分實例化**；驗證不只「站得住」，還**產出兩個具體改動點（F4/F5）**——試點 audit 之外的真實標的。**gap-kind 集合鎖定為 4、互斥改為優先序——刻度收口。** 剩 F2（發現耦合）、待確認①（制度記憶）為理論層開放。

## 8.9 第三輪驗證：通用性壓力測試（一套軸 × 三異質面，2026-06-04）

直接證偽核心原則①。同一套軸（`confidence/provenance/scope` ＋ 條件 `gap-kind` ＋ `flag` ＋ 兩層 `性質/基數/比例`），**不改、無 per-surface tweak**，套上三個性質迥異的面：

| 軸 | audit_conformance（診斷） | F4 edge `_resolve`（解析） | F5 `project_edges_for_prompt`（投影） |
|---|---|---|---|
| confidence | 退化＝high（jsonschema 確定性） | **主軸**＝resolution tier（scope_rule高→name_match低） | low（殘餘桶） |
| provenance | **主軸**＝produced_under vs current | 退化＝current（diff 才點亮） | 退化＝current |
| scope | 欄位出當前 schema＝out | **主軸**＝`_resolve` 本就算 scope-status | unrecognized |
| gap-kind | JSONDecode→corrupt；缺必填/多欄→evolutionary；enum/range→**格內** | `skipped_dynamic`→indeterminate（`name_match_ambiguous`＝格內低信心、非 gap-kind） | **桶把兩 gap-kind 併一起**＝F5 病灶 |
| flag | 無法歸類的違規 | **`_resolve`→[]＝無法解析的呼叫被靜默抹除**（U2 新） | 連 method 名都命不出 |
| 兩層 | 違規(事實)＋非合規%(基數/比例) | 全解析含替代(事實)＋候選數 | **失準：set 丟基數、併桶丟座標**＝F5 修方 |

**結論**：
- ✅ **原則①survive 最直接證偽**：零新軸、零 per-surface tweak，一套軸放下三面全部雜訊。
- 🎯 **U1（最強正面）**：`confidence`＋`scope` **本就在 edge 碼裡**，被超載進單一 `resolution` 字串（`scope_rule`/`name_match` 同時編碼 scope-status＋confidence-tier）。模型不是外加異軸，是**命名並拆分**碼裡已長出的軸 → **通用性是 discovered 非 imposed**（碼內版的 prior-art 收斂）。
- 🎯 **模型不只 fit、還 diagnose**：精準點出 F5 把 `name_match_ambiguous`(格內) 與 `skipped_dynamic`(indeterminate) 併桶；並揭露 **corrupt 在 store 被三種不一致處理**（`audit_conformance` report ／ `_load_all_snapshots` silent-skip+log ／ `get_structure` warn+None）——無統一模型正是病因。
- **U3（概念關鍵）**：`provenance` 在單版 edge 面**退化為常數 current**（diff 才點亮）。**通用性 ≠ 每軸處處變化，＝每軸處處良定義；各面輪流有一條主軸**（audit→provenance；F4→confidence+scope；F5→兩層）＝真正 spanning basis 的特徵。
- **外邊界（乾淨）**：模型只治**認識論資料雜訊**，不治 **operational/input 錯誤**（job-conflict／`conflicting_flags`／vid 碰撞）——那些維持純 error。S1 邊界再確認。
- **誠實成本**：`resolution` 是**持久化欄位、下游消費**；拆軸＝真實契約遷移。**模型通用 ≠ 遷移便宜。**
- **claim 有界**：本輪只測 3 面（含最硬的 edge 超載面）；snapshot/scope/doubt/L1-L2/viewer API 未測。

## 8.10 膜模型：A 與 B 是同一張膜的兩面（2026-06-05 整合）

> **取代「§8 幾乎只寫 A」的框架。** A（雜訊軸）與 B（訊號詞彙意義）共用同一機制，分居嚴格寫入契約這層膜的兩側。

**統一命題（取代 §8.1 的單面版，作為整份文件新脊椎）**：
> 每個輸出元素都攜帶它在某結構空間裡的「**位置**」；意義永不靠散文定義，永遠靠**關係定位**。**嚴格寫入契約＝膜**：膜內＝封閉訊號（B：結構主義對比位置）、膜外＝開放雜訊（A：不確定性座標），兩側同受寫嚴讀寬（**CWA-寫 / OWA-讀**）。自由文字＝契約明文宣告的開放窗。

| | A（雜訊軸） | B（訊號詞彙） |
|---|---|---|
| 膜的哪側 | 格外（契約補集） | 格內（契約之內） |
| 世界假設 | OWA 開放（不可窮舉） | CWA 封閉（enum＝完整集） |
| 意義機制 | 不確定性座標 | 結構主義差異位置（索緒爾：價值＝差異） |
| 對應 round-1 | OWL-OWA-讀寬 | SHACL-CWA-寫嚴 |

**B 理論化（補原始動機那一半）**：
- B 的問題：enum 每值意義住 docstring/prompt，消費端讀不到（`doubt_transition.target_state` 無 enum 即此）。
- B 的陷阱＝A 同款（皮爾斯無限符號過程，散文定義發散）。逃生口＝定位「**操作位置**」非散文定義。
- B 形式＝暴露**操作位置**（前件＝可轉入條件／後件＝產生的效果／對比＝與兄弟值的差異／共依＝必填欄位；**多半已有內部單一來源、如 `DoubtLifecycle`**）＋**極短指稱注解**（補語法捕捉不到的人類意圖殘餘；面對遞迴必須短，「不寫論文」）。
- 訊號三類：封閉 enum（B 主場）／自由文字（`reserved` 窗）／欄位用途（簡單標籤、較不遞迴）。

**三接點（連貫性驗證；裂縫都變接點）**：
1. **B 需要 A 的 `provenance`**：對比集版本相對（改一 enum 值，全體差異重新平衡）→ **更新 §8.3／§8.9：provenance 不是 edge 面退化次軸，是 B 的承重軸**。A↔B 在 provenance 咬死。
2. **`reserved` ＝兩面共用邊界物件**＝CWA 世界裡明文宣告的 OWA 窗（故其處方＝「別動、保留」）。
3. **兩面同構**：結構化主體＋不可化約極小殘餘（A：座標＋觸底旗標；B：操作位置＋短注解）。

**三翻轉（你「先釐清 B 再回顧 A」的方法論逼出）**：
1. **A 不能單獨 spec**：provenance 被 B 徵用、`reserved` 共用邊界——單切 A＝只造半張膜。
2. **甲案重構一直在替 B 鋪料**：`DoubtLifecycle`／`BaselineResolver`／models 套件化＝B 要 surface 的「操作位置」結構。甲不只清債，是長 B 地基。
3. **doubt 是「整張膜」典範整合試點**（同時有 B-enum〔state/resolution.type〕＋A-noise〔free-text=reserved、低信心偵測〕＋已建 `DoubtLifecycle`）→ **推翻早輪「doubt 邊際遞減」判斷**：它是唯一能一次驗 A+B+膜的面。

## 8.11 第四輪驗證：生成性（prospective）——未來預設構建是否符合哲學？

問題轉向：前三輪是 **retrospective**（既有碼是否已符合）；本輪問 **prospective**（未來新邏輯的**預設構建**是否符合）＝測哲學是「事後曲線擬合」還是「生成性預測」。

**三層證據 ＋ 一條誠實界線**：
1. **是吸引子（有預測內容、非擬合）**：既有碼**獨立**長出模型的部分（`resolution` 內含 confidence+scope；`edge_projection` 兩層）＝**在不知哲學下趨同** → 哲學描述的是吸引子，未來構建會**部分自然趨同**。
2. **但非自我強制（違反點為證）**：同一碼也漂移（F4 丟敗者／F5 併桶／corrupt 三處理）。預設的自然漂移方向＝**過早收斂（圖方便）**。故符合**不自動**。
3. **故須化為生成性預設（construction primitive），且可行，靠兩個互補機制**：
   - **affordance 遞迴到生產端**（B 不只用在消費端 LLM，也用在**開發者/agent**）：唯一受祝福的輸出構造路徑 afford 合規輸出，繞過才有摩擦＝讓對的容易。
   - **make illegal states unrepresentable（型驅動）**：primitive 型別收座標/操作位置，**無**裁決/分數欄位、**不帶基數不能 emit 殘餘** → 結構性不合規變**不可構造**＝讓錯的不可能。
   - （affordance 與型別＝**互補非別名**：一個讓對的容易、一個讓錯的不可能。）
4. **誠實界線**：只強制**結構**合規，非**語意**正確。值判錯（信心填錯）仍靠生產端判斷＋characterization test。**型管形狀、管不到判斷。**

**戰略含義**：這把乙案從「三個補丁（audit/F4/F5）」升成**概念上最大的一刀**——交付物是**生成性構造預設（膜 primitive，一件、兩模式、服務膜兩側）**；三面 retrofit 成首批實例＝證明 primitive 成立。**通用性因此從逐面紀律變結構性必然**（每個經 primitive 建的新面自動通用、自動服務膜兩側）。

## 8.12 第五輪驗證：膜 primitive 型別草圖 ＋ 撞現有契約（2026-06-05，把 §8.11 生成性主張往下壓一輪證偽）

**型別草圖**（結構推演、非實作）：一個 emission 原語 `MembraneElement{ payload, position }`，**型別本身無獨立裁決/分數欄位**。`position` ＝ discriminated union，4 變體：
- `SignalPosition`（B／CWA／格內）：`contrasts`(封閉兄弟集)＋`preconditions`＋`consequences`＋`co_requires`＋短 `gloss`。
- `NoisePosition`（A／OWA／格外）：`confidence`＋`provenance`＋`scope`＋選填 `gap_kind`(優先序)＋`cardinality`(聚合時)；或 `flag`(presence-only)。
- `RelayedVerdict`：`score` ＋ **強制 external provenance**（CVSS-from-OSV）——裁決**僅在帶外部來路時可構造**。
- `ReservedPassthrough`：free-text payload、不要求結構（CWA 明文宣告的 OWA 窗）。

**可行性裁決（撞契約找裂）**：
- ✅ **primitive 住在「emission/呈現邊界」、非持久化層** → snapshot 照舊存 `resolution`(事實層)、primitive 在 emit 時**投影**。**最怕的「持久化遷移衝突」大半溶解**。
- ✅ **與 Finding A 互補不衝突**：`_write_snapshot`(strict schema)＝膜的**寫/CWA 側**；primitive＝**讀側**的膜感知 emitter。Finding A 造膜、乙案造膜感知 emitter，完美 compose。
- ✅ **B 模式可用既有 JSON Schema 表達**：`enum`＝contrasts、`if/then`＝preconditions、`description`＝gloss。**無需新傳輸層**。

**草圖逼出的三個模型修正（最有價值的證偽收穫）**：
1. **U1 不完整**：`resolution` 編碼的是 confidence ＋ scope ＋ **method（scope/alias/name）三件**。method 是生產端內部、對消費端塌進 confidence、留事實層 → 呈現層＝confidence+scope，method 不上消費面。
2. **「加法不減法」只是 A 側（OWA/讀）律**：B 側（CWA/寫）律＝**嚴格封閉 enum**。§8.1「只能加法不減法」是 A 側規則被誤述成普世。統一律＝**寫嚴讀寬分側施作**（替 `doubt_transition.target_state` 補 enum＝B 側嚴格約束、正確，即使它「減掉」原本可接受的輸入）。
3. **裁決規則磨利**：禁的是**自鑄裁決**；**轉述的外部裁決（CVSS）＝帶 provenance 的事實、必須可轉述**。型別＝「verdict 可構造 iff provenance 為外部」。

**F6（新 landing point，草圖＋grep 撞出）**：`core/vulnerability/vulnerability_scanner.py` 在 OSV 無分時鑄造 `CVSS_MIDPOINTS` 後援分（預設 5.5），**與轉述的外部分呈現無別** → 自鑄裁決偽裝成外部事實。缺分應標 `indeterminate`/flag、非捏造中點。primitive 型別會讓「捏造中點」**不可構造**。

**「一件 primitive」的誠實界定**：是**一條 emission 路徑／一個 base 型**＋有界 4 變體 position union（2 主＝Signal/Noise ＋ 2 特例＝RelayedVerdict/ReservedPassthrough），**非單一扁平型**。

**第五輪結論**：§8.11 的生成性 primitive 主張**通過可行性證偽、且更便宜（emit 邊界非持久化）、與 Finding A 的膜 compose**；草圖另產出 3 個模型修正 ＋ 1 個現存違反（F6）。乙案現有**四個 retrofit 試點**：audit／F4／F5／**F6（漏洞 CVSS 後援）**。

## 8.13 收尾：理論定稿 ＋ 一致性勘誤 ＋ 遺漏核對（2026-06-05）

> **給「未來起 spec 的人」的單一權威入口。** 文件分三層：§8.1–8.5＝現行模型（已隨下表勘誤校正）；§8.6–8.12＝驗證歷程（保留 round 序、round 間自我修正）；本節定稿其上。§0–§7＝原始 audit-pilot 種子（§8 開頭已宣告「§8 是 §0–§7 之上的概念升級」，故 §0–§7 視為被 §8 supersede 的早期框架）。

### 一、理論定稿（五輪後 canonical 立場，一頁）
- **脊椎＝統一命題（§8.10）**：每個輸出元素攜帶其在結構空間的「位置」；意義靠關係定位非散文定義；**嚴格寫入契約＝膜**，膜內 B（CWA／封閉訊號／結構主義對比）、膜外 A（OWA／開放雜訊／不確定性座標），同受寫嚴讀寬。
- **承重理論**：A 判斷分工／B 意義經結構／C 翻譯投影／D 寫嚴讀寬／E 非排中律（§8.2）。
- **A 側形式（§8.3）**：3 主軸＋條件 gap-kind（≤4、優先序 `corrupt>indeterminate>evolutionary>reserved`）＋觸底旗標＋寬讀負空間；殘餘格恆帶 `性質+基數+比例`；雜訊嚴格定義＝高 `K(x│contract)`。
- **B 側形式（§8.10/§8.12）**：暴露操作位置（前件/後件/對比/共依，多有內部單一來源如 `DoubtLifecycle`）＋極短 gloss；可用既有 JSON Schema 載（enum/if-then/description）。
- **生成性（§8.11/§8.12）**：哲學是吸引子非強制力；落成**膜 primitive**（一 emit 路徑＋4 變體 position union；emit 邊界非持久化；compose Finding A）才讓未來構建結構性合規。
- **四 retrofit 試點**：audit／F4 邊解析／F5 邊投影／F6 漏洞 CVSS 後援。
- **仍開放**：F2（發現耦合＝待確認②＋§2 發現管道，合解）、待確認①（放棄的制度記憶）——須試點經驗才有料。

### 二、一致性勘誤（round 間自我修正索引；下為「現行版」）
| 早輪陳述 | 修正於 | 現行版 |
|---|---|---|
| §8.1/§0「只能加法不減法」(讀作普世) | §8.12 修正② | 加法不減法＝**A 側(讀/OWA)律**；B 側(寫/CWA)＝嚴格封閉 enum。統一為寫嚴讀寬分側。 |
| §8.3/§8.9「provenance 退化次軸」 | §8.10 接點① | provenance＝**A、B 兩面承重軸**（B：對比集版本相對）。 |
| §8.9 U1「resolution 編 2 件」 | §8.12 修正① | 編 **3 件**＝confidence+scope+**method**；method 留事實層、不上消費面。 |
| §3 schema 演化四類（並列） | §8.9 re-partition | `domain_violation`＝**格內**（歸主軸）；僅 forward_noise/missing_required(→evolutionary)/corrupt 在格外。 |
| §3「❌ risk_level 平禁」 | §8.12 修正③ | 禁**自鑄**裁決；**轉述外部裁決（CVSS）＝帶 provenance 事實、可轉述**。 |
| §1/§3「audit 是首個試點」 | §8.10 翻轉③ | doubt＝整張膜典範整合試點；audit 是 4 個 retrofit 之一。 |

### 三、遺漏核對（原 §0–§7 理論點是否被 §8 吞掉）
逐項核對，**三點需明確接回**（其餘已被涵蓋）：
- **O1｜決策充分性（§3 總綱）**：「只吐會改變消費端信任決定的事實、且事實為真」＝**A（fact-finder）的操作判準**（下界＝可行動、上界＝不越界裁決）。§8 有 A 但沒寫此判準 → **接回**：它正是 primitive「禁自鑄裁決（上界）」與「殘餘須可行動／帶證據（下界）」的來源。
- **O2｜結構即證據、免翻譯層（§3）**：每類自帶決定所需證據（expected/found）→ 已被 §8.3「每值自帶意義」＋§8.10「B 操作位置」涵蓋，**補記同源**（A 的 gap-kind 證據與 B 的操作位置是同一要求的兩面）。
- **O3｜版本戳界線（§5）**：provenance 主軸需快照帶契約版本戳；**既有快照 provenance=unknown、技術租金面向未來、對既有資料不回**。§8 升 provenance 為承重軸卻未帶此界線 → **接回**：B 的對比集版本相對性，對 pre-stamp 快照退化為 unknown，與 §5 同一限制。

### 四、收尾結論
理論基礎已夯實且內部一致：脊椎（膜）／刻度（軸＋gap-kind）／通用性／生成性五輪驗證 ＋ 勘誤校正 ＋ 遺漏接回。**下一步＝起 spec（門口待命）**；spec 起點建議＝膜 primitive 最小型別 ＋ 首個 retrofit（見 §8.14：census 支持 doubt 為整膜試點）。

## 8.14 重塑範圍普查（first-pass census，2026-06-05）

> **校正一個混淆**：前五輪是「在樣本上驗證概念」，**不是「普查重塑範圍」**。乙案＝**重塑**（改輸出契約）≠ 重構（甲，零契約改動）；範圍**定義上＝全部 LLM-facing 輸出面**。本節為首次結構普查，把「未測」降成「已盤點毛範圍」。

**毛範圍（gross，~40+ 面；前五輪僅驗 4 ≈ 10%）**：
- **MCP 工具：24 個**（analyze/diff/doubt_*/scope_*/snapshot_*/timeline/scan/extract/update/validate/render/estimate/history/verify_contract/localize_datamodel/...）。
- **MCP 輸出咽喉：`mcp/tools/_response_envelope.py::wrap`——24/24 工具全路由經它（已 grep 證實）**＝單一 chokepoint。
- **Viewer API：6 handler 域**（analysis/annotation/catalog/diff/graph/project，21 端點）＋ 序列化咽喉 `core/ui/serializers.py`（Finding B 已標＝乙案切入點）＝第二輸出路徑。
- **Renderer/Serializer：~10 個**（diff/scope/timeline/datamodel/vulnerability/report/mermaid/structure/edge_projection/...）；**已驗 2**（edge_projection=F5、vulnerability=F6）。
- **L1/L2/diff 自然語言**：`core/llm/prompts.py`＝C 投影面、另一 emit 模式。

**範圍拓樸（關鍵）**：重塑**非 ~40 獨立編輯**，而是——
- **輸出側收斂到 2 個 chokepoint**（MCP `_response_envelope` ／ viewer `ui/serializers`）→ 膜 primitive 落此 2 處覆蓋大部分輸出。**輸出側管得住。**
- **成本集中在分散的「輸入/詞彙側」**：~24 工具 input schema ＋其 enum（doubt state/resolution.type/scope/gap_kind…）每值意義＝**標的 B（原始動機）。長尾在此。**
- **內容分類器 ~10 renderer**：各自決定 signal/noise/verdict → 逐面。
- → **重塑範圍 ≈ 2 輸出咽喉（多 A 側）＋ ~24 輸入詞彙點（B 側）＋ ~10 內容分類器。**

**誠實界線（連普查也是 first-pass）**：本節為**檔案層普查**，**未**做「逐面 × 膜側（signal/noise/verdict/reserved）」分類表、**未**確認 prompts/CLI 路徑。**起 spec 前真正 deliverable＝那張完整分類表**；本節只盤毛範圍與拓樸。

**對方針影響**：成本集中於 B 側詞彙（~24 input vocab）→ 試點宜選**能 exercise B 側者＝doubt**（§8.10 翻轉③），非只 A 側 audit。**census 數字反證 doubt 為整膜試點。**

## 8.15 重塑範圍重訂：垂直表徵棧不變量審計（2026-06-05）

> **校正 §8.14（水平 emission 切片）。** 重塑＝原則變更，範圍須以「膜不變量」審**垂直表徵棧**，非列 output 面。
> **Q：需否重用原始理論架構驗證？→ 必須**：用膜當審計尺；一審即發現 **output 違反是症狀、模型層才是根**。

**棧**（bounded against 機制層：I/O / tree-sitter parsing / HTTP plumbing＝不載意義、出界）：

| 層 | 不變量審計發現 | 樣本 |
|---|---|---|
| **資料模型** | 🔴 **系統性根因**：~13 膜詞彙欄位（8 檔）全 bare `str`＋valid set/每值意義住**註解**（連 docstring 都不是）→ 消費端讀不到。B 側違反在此扎根。 | doubt `current_state`(6值)／`resolution`／`severity`／`scope_state`／`diff_state`(且 :14 五值 vs :29 三值不一致)／各 `confidence` |
| 生產/分類 | 過早塌縮 | F4(_resolve 丟敗者)／F6(scanner 鑄中點)／corrupt 三處理 |
| 持久化/schema(=膜) | Finding A 已造寫嚴 chokepoint；**schema 檔位置待定位**（src 下無 json） | `_write_snapshot`／`_get_snapshot_schema`／doubt-record.schema |
| emission | 傳播模型層的非結構 | §8.14：envelope／serializers／renderer×10 |
| 消費/顯示 | **未審** | viewer 前端 |

**審計反轉（最重要）**：**output 違反（F4/F5/F6）是症狀，模型層才是根。** output 面只忠實傳播模型層「意義住註解、enum 是 bare str」。只重塑 output 不動模型＝治標。**真正的重塑從模型層起、向上傳播。** ← 坐實使用者「侷限在 output」之糾正。

**座標模型在模型層垂直驗證（重用理論架構的收穫）**：
- `confidence` **遍佈**（snapshot/analysis×3/pipeline/diff）＝模型層**獨立長出**此軸（U1 碼內收斂垂直版）。
- **`confidence_reason` 已與 confidence 成對存在**＝`reserved` 窗在模型層**現成**。
- `scope_state`＝scope 軸；doubt/diff `current_state`＝B enum——A 軸與 B enum 模型層皆在。
- **唯 `provenance` 缺席**＝版本戳 gap（坐實 O3）：整套軸裡**唯一需「新增」者**，其餘皆「把既有 bare str 結構化」。

**誠實界線**：模型層豐富取樣（非窮舉）；**schema 層位置待定位**（膜本身、必須定位）；顯示層未審。下一步＝定位 schema 層 ＋ 審顯示層。

## 8.16 垂直審計補完：schema 層（膜）＋ 顯示層（2026-06-05）

**schema 層定位＝`the_door/schemas/`，11 個 schema＝膜本身（非一張、11 張契約）**：ast-raw／diff-result／doubt-record／l1-output／l1-5-output／l2-output／narrative／scope-definition／snapshot／timeline-result／update-report。

**膜層審計（讀 `doubt-record.schema.json`）——決定性**：
- enum 載**封閉集（contrasts、CWA✓）但零每值意義**：`current_state` 6 值、`description:"當前狀態"`＝**欄位級、非每值**；`resolution.type` 3 值**連 description 都無**。
- 轉換**文法（preconditions）不在 schema**——住 `DoubtLifecycle`(Python)。schema 有「值」無「文法」。
- `reason`＝free-text `oneOf null|string`＝**`reserved` 窗在膜層確認**。
- → **膜是「半膜」**：Finding A 已造 CWA 強制（寫嚴），但**膜語意空心（有集無意義）**。B 在 schema 層的工作＝用 JSON Schema 現成機制（`oneOf`+`const`+`description` per value）把每值意義填進膜——**機制已在、未用**（坐實 §8.12「B 可用既有 JSON Schema 載」）。

**顯示層審計（viewer JS）**：`confidence/resolution/severity/state` 在 **9 模組 56 處**重度使用（ui-doubt 18／ui-list 10／ui-detail 7…）。但每值意義不在資料裡 → 顯示層**要嘛在 JS 重複一份（第 N 份 copy）、要嘛給人看 bare enum**——兩者皆違反（屬哪種待一讀確認、但皆違反）。`provenance` 在顯示層亦 **0**（全棧缺席一致）。

**垂直審計完成——五層 through-line**：
| 層 | B 側違反（每值意義不結構） |
|---|---|
| 模型 | 意義住註解 |
| 生產 | （A 側：過早塌縮 F4/F6/corrupt 三處理） |
| schema(膜) | 有集無意義、文法不在膜（半膜） |
| emission | 傳播非結構（§8.14） |
| 顯示 | 重複或丟 |

**綜合**：同一語意事實（「explained vs fixed vs accepted_risk 是什麼」）在**全棧無一處結構化**——只活在 docstring／`DoubtLifecycle`／可能 JS。違反是**垂直 through-line、非局部**。
**理論架構垂直驗證通過**：膜不變量五層一致適用；`confidence`/`scope` 五層皆現、`provenance` 五層皆缺（＝唯一淨新增＝版本戳 O3）、`reserved` 窗模型+schema 已現。**模型不只 output 層成立，是全棧不變量。**

---

# 9. 寫 spec 的流程（使用者 2026-06-05 指定；務必遵守，防幻覺/失焦/目的偏移）

> 理論與範圍調查已收尾（§8 全部）。本節是「理論 → spec」的橋，是給未來逐份寫 spec 的人的**固定流程**。

1. **先拆解需要重塑的範圍成清單＋步驟**：依垂直五層（§8.14–§8.16），**按「through-line」逐線拆**——一條 through-line ＝ 一個語意事實貫穿的五層路徑。例：
   - **doubt 線**：`models/doubt.py:35 current_state` → `schemas/doubt-record.schema.json` → `core/scope/doubt_lifecycle.py` → emission(`_response_envelope`/doubt tools) → `viewer/js/ui-doubt.js`。
   - 其他線：resolution 線（`extraction.py:38`→edge_builder→edge_projection→viewer）、severity 線（`vulnerability.py`→scanner→renderer）、confidence 線（遍佈）、scope 線、diff_state 線…
   - **先列全部 through-line ＋ 每線步驟**，再逐線寫 spec（一線一 spec 或數線一 spec，依大小）。
2. **每寫一份 spec 前，重新回核本理論文件**——逐項確認該 spec 符合討論的理論哲學：
   - 膜不變量（§8.10）：意義靠結構位置、非散文/prompt。
   - 寫嚴讀寬**分側**（§8.12 修正②）：B 側（CWA）嚴格封閉 enum；A 側（OWA）加法不減法、永不關閘。
   - fact-finder（§8.2 A）：禁自鑄裁決；外部裁決（CVSS）＝帶 provenance 的事實、可轉述。
   - B 操作位置（§8.10）：enum 暴露前件/後件/對比/共依，優先用內部單一來源（如 DoubtLifecycle）。
   - `provenance` 是唯一淨新增軸（版本戳）；其餘皆「把既有 bare str 結構化」。
   - 剔除紀錄（§8.4）：不得把量子塌縮/Dither/基數=K/生產端熔斷搬回當依據。
3. **目的＝防漂移**：內容持續累積，**每份 spec 都要主動重錨理論**（讀 §8.10/§8.13/§8.2/§8.4），避免幻覺、失焦、目的偏移。
4. **沿用既有紀律**：先對真實碼 spike；spec 寫完跑 7 點審查（第 4 點 grep 驗 API 名）；characterization test 先行（動輸出契約前的安全網）；文件給 Claude Code 讀（結構化、exact code、零佔位符）。
