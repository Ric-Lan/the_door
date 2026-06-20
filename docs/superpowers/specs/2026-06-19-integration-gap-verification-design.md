# 設計探索 spec：整合落差驗證（Integration-Gap Verification）

> **狀態：探索中（未承諾落地）。** 這是一個想法的設計骨架，用來判斷「要不要做、要不要開成支線、用什麼落地形式」。
> 本文件**不是**已核可的實作計畫。所有標 `【未決】` 的岔路都還沒拍板。
>
> 日期：2026-06-19 ／ 觸發者：使用者（非技術利害關係人視角的新支線提案）

---

## 1. 問題（給非技術讀者的一句話）

> 經過 The Door 產出的功能卡片，**怎麼確定整個專案是「真的能被使用」，而不只是「做出來了」？**

使用者原始例子：
> 「如果我做了資料庫架構設計及後端的專案，但產出的專案後端**完全沒有跟資料庫相連**，或是**部分聲稱需要相連的功能卻沒有**。」

核心是：**功能卡上「宣稱有的依賴」 vs 程式碼結構上「真的存在的連線」之間的落差**。一張功能卡可以描述得很完整、卻在結構上是孤島；一條「後端→資料庫」的宣稱依賴，可以在 AST 圖上**根本沒有任何 edge 對應**。

## 2. 已定範圍（使用者已選）

| 軸 | 選定 | 說明 |
|---|---|---|
| 驗證性質 | **靜態整合落差** | 在 The Door 已看得到的 node/edge + 功能依賴裡，找「宣稱有依賴、結構上沒對應連線」。**不是**執行期「真的能跑/真的連上 DB」——The Door 從不執行目標專案。 |
| 機制定位 | **The Door 輸出當基礎 → 使用者自然語言確認** | 宣稱來源（描述自動推 vs 使用者輸入設計意圖）是同一條執行路徑，不構成分岔。新價值必須在**基礎/素材層**（多產出一份整合真相），不在對話層。 |

### 2.1 範圍邊界（誠實標註，這是 The Door 的固有限制）

- The Door 的結構是 **AST 級**（function/class/method + `calls`/`imports`/`extends`/`implements`）。
- **資料庫常常不是一個程式碼節點**——它可能是 SQL schema 檔、連線字串、ORM 設定、外部系統。若 DB 存取沒有以程式碼 import/call 出現，AST 圖**可能看不到那條邊**。
- 推論：本支線能可靠偵測的是「**功能 A 的程式碼有沒有真的引用/呼叫到功能 B 的程式碼**」。當「被依賴方」本身在 AST 圖上不存在（純外部 DB），偵測會退化成「這條宣稱無法被結構佐證」——這要誠實呈現為**低信心/無法判定**，不可洗成「一定沒接上」。

## 3. 關鍵發現：偵測引擎已存在，但與使用者面斷開

這是本支線最大的槓桿——**核心邏輯不用從零發明**。

### 3.1 已有的東西
- `core/validation/relation_check.py` 的 `RelationCheck`：對 `relation_type == "static"` 的功能關係，要求兩個 feature 的 `source_nodes` 之間**存在 AST edge path**，否則報
  `Static relation 'X' → 'Y' has no corresponding AST edge path`。**這字面上就是整合落差偵測。**
- 它**已接上** `OutputValidator`，且 `OutputValidator` 經 `mcp/server.py:208` 的 `validate_output` MCP 工具可被觸發（`validate_tool.py` 是空的棄用檔，真正實作在 server.py 內聯）。
- L1 的 **validation schema**（`schemas/l1-output.schema.json`）有 `relation_type: static|inferred` + `inferred_reason` 的完整區分。

### 3.2 為什麼它「碰不到使用者真正看到的層」
| 斷點 | 現況 |
|---|---|
| **不在主鏈** | CLAUDE.md 的 agent-as-LLM 主鏈是 `extract_structure →（產 L1）→ edge_residue → snapshot_write`，**沒把 `validate_output` 當必經閘**。整合落差判定是可選、孤立的。 |
| **持久化丟資訊＋static 分支不可達** | 真正落盤的 `RelationSummary`（`models/snapshot.py`）只有 `from_feature/to_feature/relation`（例 `feeds_into`）。更關鍵：`snapshot_write` 的 `relations` 入參 schema **根本不收 `relation_type`**（`required:[from_feature,to_feature,relation]`）→ 現行持久化路徑產出的 relations **永遠沒有 `relation_type`** → `RelationCheck` 的 `static` 分支對實際資料**結構性不可達**，這個整合落差檢查在 live flow 裡**根本觸發不到**。 |
| **沒被攤開** | 就算跑了，輸出是一串 validation **錯誤字串**，從沒做成功能卡上的「✅有撐／❌沒撐」結論給非技術讀者。 |
| **判定偏鬆** | `RelationCheck._has_path` 用 **BFS 全圖傳遞可達性**（transitive reachability），不是直接邊。連通的 codebase 裡幾乎都可達 → 可能**漏報**真正的落差（除非完全沒接，如純外部 DB 例）。 |

**一句話結論：已建好的只是「偵測管線」（給定 static 關係 + 結構，能算有無 edge path）；本支線真正的硬核——一個*不循環的*宣稱來源、避免循環、把結論攤給非技術讀者——尚未建。`RelationCheck` 是可重用的零件，不是已完成的 80%。**

### 3.3 載重風險：循環性（這條支線成敗的真正命題）

`RelationCheck` 只有在「有人**獨立於結構**地宣稱『這裡該有依賴』、而結構上剛好沒有」時才抓得到落差。但在現行 agent-as-LLM 流程裡，**relations 是 agent 從同一份結構讀出來的**：缺邊時 agent 通常根本不會建那條關係、也不會標 static → 宣稱與結構天生自洽，**比了等於沒比**。

因此「宣稱來源」不能是 agent 對結構的事後讀取，必須來自更獨立的東西：

- **功能卡描述的語意**（「儲存使用者資料」← 語意上就該碰到某個儲存/DB 功能），由 agent 判讀後**反查**結構有沒有撐；或
- **使用者輸入的設計意圖**（「後端應連 DB」），逐條拿去比對結構。

這正是 §5.1/§5.2 在處理的事——但它是**整條支線的中心命題**，不是次要設計選項。若無法建立一個不循環的宣稱來源，本支線退化成 `validate_output` 換皮，應**判定不做**。

## 4. 與已判定「不做」的支線的分界（避免繞回舊路）

| 已砍支線 | 本支線為何不同 |
|---|---|
| **互動問答**（仿競品，判定不做：能力已內含於 `analyze_changes → AI 敘述`） | 本支線交付的是**確定性計算的整合真相**（每條宣稱：有撐/沒撐 + 證據邊），AI 的自然語言確認**站在這份基礎上**回答，而非在原始 edges 上手揮。新價值在素材層、不在對話層——正好通過先前定的判準。 |
| **雜訊軸延伸**（隱性介面偵測 / 逐邊依賴信心，判定不做） | 那是 per-edge 信心 / 隱性介面。本支線是 **feature 對 feature 的宣稱-實連布林 + 證據**，給非技術讀者看「有沒有接起來」，不是逐邊信心訊號。 |

> ⚠️ **守門提醒（給審查用）**：本支線有兩個證偽風險。①**循環性**（§3.3）——若宣稱來源仍是 agent 對結構的事後讀取，宣稱與結構天生自洽，比了等於沒比。②**換皮**——若結論是「跑一次 `validate_output` 就夠、不需新素材/持久化/使用者面」。任一成立則**判定不做**，與互動問答同理。落地與否的閘門＝§6。

## 5. 設計空間（含未決岔路）

### 5.1 資料：整合落差判定要長在哪一層？【未決 D3】
- **選項 A — 復活 relation_type 進 snapshot 層**：讓 agent 寫 relations 時帶 `static/inferred`，持久化保留，snapshot 內就能算 backing。改動面廣（schema/contract/agent guide/snapshot model）。
- **選項 B — 新增獨立 MCP 工具（如 `integration_check`）**：讀 snapshot 的 features + structure-view 的 edges，**現算**每條宣稱 relation 的 backing，輸出結論物件。不動既有持久化 schema，加法、低耦合。**初步傾向**。
- **選項 C — 純 viewer 衍生**：前端讀 features + edges 自己算。最輕，但邏輯散到前端、AI 拿不到結構化結論。

### 5.2 哪些宣稱「應該要有結構佐證」？【未決 D2，假陽性控制】
- **嚴格全查**：每條功能依賴都要求有 AST edge backing。簡單，但 `feeds_into` 這類概念/管線式關係可能本就沒有直接呼叫邊 → **可能喊狼**。
- **分型**（沿用 static/inferred 精神）：只有「應為實連」的關係要求 backing；概念關係標 inferred、要求一句理由、不要求邊。較準、較貼近 `RelationCheck` 既有設計。
- 取捨：嚴格全查出成果快但吵；分型準但要 agent 多標一個欄位。

### 5.3 「有撐」的定義鬆緊【未決 D4】
- 沿用 `RelationCheck` 的**傳遞可達**（鬆，會漏報）。
- 改成**直接邊 / 有限跳數**（嚴，更貼「真的直接接上」語意，但需定義門檻）。
- 兩者都應在結論裡帶**證據**（撐起這條宣稱的實際 edge 路徑，或「找不到任何路徑」）。

### 5.4 push vs pull【未決 D1，使用者未拍板】
- **push 優先（建議）**：主動算並攤一份「N 條宣稱、M 條沒接上、K 個孤立功能卡」清單當起點，非技術 PM 不用先知道該問什麼；pull 在其上深問。
- **純 pull**：使用者問、AI 才答。貼近使用者原話，但缺主動指出問題的能力。
- **純 push**：一鍵整合健檢報告、不做對話。最快出成果、最少彈性。

### 5.5 非技術讀者的呈現形式【未決，使用者明言「落地形式未定」】
候選：功能卡上的徽章（✅接上／❌沒接上／⚠無法判定）＋ 一句白話；或獨立「整合健檢」面板；或 diff 層的「這版有沒有把該接的接上」。**本 spec 不鎖定 UI**。

## 6. 落地與否的判準（這份 spec 真正要回答的事）

在投入實作前，需先對以下取得「是」。閘門以**可觀察條件**定義，避免主觀判斷：

驗證載具＝**一個故意斷開的 target**（例：後端有 `save_user()` 但完全不 import/call DB 模組；外加 N≥3 條已知良好的真實依賴當對照組）。

1. **新素材是否真的不存在於現行使用者面？** —— 已坐實「是」（§3.2：relation_type 不持久化、static 分支不可達、結論不攤開）。
2. **偵測有效性（真陽性）**：在故意斷開的 target 上，工具須**命中那條已知落差**（標 ❌沒撐），並附可檢視的證據（找不到任何 edge path）。漏掉 → 證偽。
3. **假陽性控制（不喊狼）**：對 N 條已知良好依賴，工具須**全部標 ✅有撐、零誤報**；對「被依賴方不是程式碼節點」者須標 ⚠無法判定、**不得**標 ❌。
4. **非循環性**：宣稱來源須可追溯到「描述語意」或「使用者輸入」，而非 agent 對結構的事後讀取（§3.3）。可由 demo 中「宣稱」與「結構」分別獨立產出來核驗。
5. **非換皮**：交付須含新的結構化結論 + 使用者面，而非只跑既有 `validate_output`。

> 若 (2)(3)(4) 任一證偽 → 比照互動問答**判定不做**，本文件轉為「已評估、不落地」紀錄。

## 7. 初步建議（非承諾）
> ⓘ 歷史段落：spike 已完成、決議見 §9（D3 由「現算不動 schema」放寬為「加法持久化」）。本節僅留探查當時的推理軌跡。

- **先解中心命題（§3.3 宣稱來源）**：未確定一個不循環的宣稱來源前，下面的工具/UI 選型都是空談。
- 走 **D3 選項 B（獨立 `integration_check` MCP 工具，現算不動 schema）** + **D2 分型** + **D4 帶證據的直接/有限跳數** + **D1 push 優先、pull 疊上**。
- 理由：加法、低耦合、可先做成**純讀**的結論物件，跑 §6 的 (2)(3)(4) 三道閘，再決定要不要持久化與做 UI。符合使用者「先驗需求存在、不急著加功能、不橡皮圖章」的偏好。
- **下一步不是寫 code**，而是：先用真資料（含一個「故意斷開」的 target）做一次手動 demo，坐實 §6 的 (2)(3)(4)。通過才進 writing-plans。

## 8. 待辦/開放問題清單
> §5 的未決項已於 §9 決議；本清單僅留歷史軌跡。
- [x] **【中心命題】§3.3 不循環的宣稱來源** → §9：relation_type 表「期待」（語意/意圖），工具去驗證，非事後讀邊
- [x] §6(2)(3)(4) 真資料 demo → spike 完成、判定 **GO**（spike-report）
- [x] D1 push/pull → 工具層回完整報告（push-data）；push/pull **UX 留前端步驟**
- [x] D2 嚴格全查 vs 分型 → **分型（static/inferred）**
- [x] D3 工具落點 → **獨立 `integration_check` 工具 + 加法持久化 relation_type**（B 放寬為「加法動 schema」）
- [x] D4 有撐定義鬆緊 → **帶證據 + `max_hops` 參數（預設 2 跳）**
- [ ] §5.5 非技術呈現形式 → **下一步驟**（前端 UX 置入，本輪不做）
- [ ] 確認 §2.1 的「DB 非程式碼節點」邊界在目標客群實務中多常見（影響本支線價值密度）

## 9. 決議與工具化設計（核可 2026-06-20）

spike 判定 GO 後，使用者拍板 D2/D3/D4，並以「之後要做跨版本 diff、不持久化不實際」為由，把 D3 從「完全不動 schema」**放寬為「加法式動 schema」**。以下為核可的實作設計。

### 9.1 持久化（加法、不 bump contract）
- `snapshot_write` 的 `relations` 入參新增**選填** `relation_type`（`static`|`inferred`）+ `inferred_reason`（`inferred` 時必填一句理由）。
- `RelationSummary`（`models/snapshot.py`）／snapshot JSON／`l1-output.schema.json` 一併帶這兩欄。
- **純加法** → 舊 snapshot 仍合法、**不 bump `SNAPSHOT_CONTRACT_VERSION`**（依 contract §6：純加法不 bump）。
- **舊資料（relations 無 relation_type）** → `integration_check` 標 `not_assessed`，**絕不**誤判成 ❌。

### 9.2 新工具 `integration_check(codebase_path, version_ref, max_hops=2)`
讀**持久化的 typed relations** + structure-view edges，逐條判定並回傳結構化結論：

| relation_type | 判定 | 證據 |
|---|---|---|
| `static`，有 ≤`max_hops` 跳的 edge path | `backed`（✅） | 撐起的實際 edge 路徑 |
| `static`，無路徑 | `gap`（❌） | 「找不到 ≤max_hops 跳路徑」 |
| `static`，被依賴方節點不在圖中 | `undetermined`（⚠） | 「目標非程式碼節點」 |
| `inferred` | `conceptual` | 回報 `inferred_reason`，不查邊 |
| 無 relation_type（舊） | `not_assessed` | — |

- `max_hops`：參數化、預設 **2**（給間隔、日後好調）；`1`＝只認直接邊。路徑搜尋沿用/比照 `RelationCheck._has_path` 的 BFS，**加跳數上限**。
- 回傳含 per-relation 判定 + project-level rollup（N static / M gap / K undetermined）。

### 9.3 非循環性守則（guide 級，C7 無法 gate）
- `relation_type=static` 代表**期待**「這裡該是真的程式連線」（來自功能語意/意圖），**不是**「我看到有邊才標」。`integration_check` 是去**驗證**此期待——落差正是「期待 static 但結構沒有」時才有意義。
- agent-as-LLM guide 明寫此條（種子 §5 固有缺口：純行為/意圖無法以 hook 強制，靠 guide + 執行帳本）。

### 9.4 註冊與文件
- `mcp/server.py` 註冊 `integration_check`；CLAUDE.md 工具參考表 + agent-as-LLM 鏈補上；`relations` 寫法說明補 `relation_type`/`inferred_reason`。

### 9.5 測試
- 沿用 spike 的故意斷開 fixture 當基底，補 `static`/`inferred`/`untyped`/非程式碼節點四類 + `max_hops` 邊界（1 vs 2 跳）的單元測試。
- snapshot_write 加欄的回歸：舊 payload（無 relation_type）仍通過、persist 後讀回一致。

### 9.6 範圍邊界（本輪不做）
- §5.5 非技術前端呈現（功能卡徽章 / 健檢面板）＝**下一獨立步驟**，依 UX 原則設計後另開 spec/plan。
