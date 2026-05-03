# The Door — Product Specification
## Code Visualization for Non-Technical Stakeholders

> **專案名稱：** The Door（讓非工程師入門認識工程師產出的門）
> **文件狀態：** Active Spec（AI-native 工作上下文用）
> **設計約束：** 架構可行性優先、落地性極大化、降低 token 消耗與硬體需求
> **架構原則：** LLM-centric — 功能識別與翻譯由 LLM 執行，系統負責約束 LLM 的輸入與輸出
> **執行原則：** AI-medium-agnostic — 任何能讀取本機檔案的 AI 媒介都能執行本專案
> **讀取策略：** 世代四 — AST 拓撲引導讀取，讀取順序由依賴結構決定，不由 LLM 猜測

---

## 0  核心命題

把程式碼的「結構與變化」翻譯成功能語言圖形，讓不讀程式的人能直接**驗核**開發單位的產出是否符合承諾。

翻譯方向：技術語言 → 功能語言。圖形不是裝飾，是驗核介面。

### 0.1  架構哲學：LLM-Centric

**根本認知：** 程式碼的功能識別與分類是語意問題，不是規則問題。試圖用 AST 規則窮舉所有程式碼模式，等於在做一個永遠寫不完的分類器。The Door 不是模型專案，不追求覆蓋所有程式碼風格。

**設計選擇：**
- LLM 負責所有功能識別、分類、翻譯
- AST（tree-sitter）一律使用，負責將程式碼結構化為 JSON 原料，不做分類決策
- 系統的核心 IP 是「如何約束 LLM 的輸入與輸出」，不是「如何用規則分類程式碼」
- 接受 LLM 的能力邊界，用輸出約束確保結果符合專案需求
- 統一處理流程，不因專案大小而切換不同路徑

**這意味著：**
- 跨語言問題不需要 AST 層解決 — L1 問的是「能做什麼」，LLM 不在乎底層語言
- AST 清理規則不需要窮舉 — LLM 自己能判斷什麼是基礎設施、什麼是業務邏輯
- 新框架、新語言不需要新增規則 — LLM 天然具備泛化能力

### 0.2  執行哲學：AI-Medium-Agnostic

**根本認知：** The Door 不是一個 web app，也不是一個綁定特定 API 的服務。它是一套可被任何 AI 媒介執行的工具鏈。只要 AI 媒介能讀取本機檔案、執行本地指令、呼叫 LLM，就能跑 The Door。

**The Door 的產品形態：**
```
The Door = 本地工具鏈（CLI）+ MCP Server + 約束 prompt + 輸出 schema + 驗證規則
         ≠ web app
         ≠ 特定 API 的前端
```

**支援的 AI 媒介（不限於以下）：**

| AI 媒介類型 | 範例 | 如何執行 The Door |
|---|---|---|
| **MCP Client** | **Claude Desktop、Cursor、任何 MCP-compatible AI** | **直接呼叫 The Door MCP Server 的工具，零整合成本** |
| IDE Agent | Kiro、Windsurf、GitHub Copilot | Agent 呼叫 The Door CLI，讀取 workspace 中的 codebase |
| CLI Agent | Claude CLI、Aider | 直接在終端機執行 The Door CLI，指定目標路徑 |
| AI Desktop App | Claude Desktop、ChatGPT Desktop | 透過本機檔案存取權限讀取 codebase，執行 The Door |
| Web UI（自建） | 自建互動式介面 | 前端呼叫後端 API，後端執行 The Door CLI |
| CI/CD Pipeline | GitHub Actions、GitLab CI | Pipeline 中執行 The Door CLI，輸出結果作為 artifact |

**執行流程（與 AI 媒介無關）：**
```
任何 AI 媒介
  → 呼叫 The Door（MCP tool 或 CLI）：the-door analyze <codebase-path>
  → [本地] tree-sitter-language-pack 結構提取 → 結構原料 JSON
  → [本地] 拓撲分析（純本地，無 LLM）→ topology 欄位寫入結構原料 JSON
  → [本地] osv-scanner 漏洞掃描（選配，與拓撲分析並行）
  → AI 媒介依 topology.batch_assignment 分批將結構原料 JSON + 約束 prompt 送給 LLM
  → [本地] 輸出驗證（jsonschema + 四項語意檢查）
  → 輸出標準化結果：
     ├── L1 + L1.5 功能圖形（Mermaid 文字）
     ├── L1 + L1.5 自然語言敘述（JSON）
     ├── 信心標記 + 未歸類節點清單（JSON）
     └── 漏洞摘要（JSON，若有）
```

**關鍵設計決策：**

1. **The Door CLI + MCP Server 是雙核心交付物。** CLI 負責 AST 提取、輸出驗證、渲染格式生成；MCP Server 讓所有 MCP-compatible AI 媒介零摩擦接入。
2. **約束 prompt 是可攜帶的。** prompt 以檔案形式存在於專案中，任何 AI 媒介都能讀取並使用。
3. **輸出格式是標準化的。** 不管哪個 AI 媒介執行，輸出的 JSON 和 Mermaid 格式一致，渲染結果可預期。
4. **LLM 選擇由使用者決定。** The Door 不綁定特定 LLM 供應商。AI 媒介用自己的 LLM（API 或本地模型）。

**兩種執行模式：**

| 模式 | 說明 | 適用場景 | 可用 Phase |
|---|---|---|---|
| **完整模式** | AI 媒介呼叫 MCP tool 或 CLI 做 AST 提取 → 拿到結構原料 → 自己呼叫 LLM → 拿到結果 → 呼叫 CLI 做輸出驗證和渲染 | IDE Agent、MCP Client、CLI Agent | Phase 1-min 起可用 |
| **一鍵模式** | CLI 內建 LLM 呼叫（使用者設定 API key 或本地模型），一個指令完成全部流程 | 非技術使用者、CI/CD Pipeline | **Phase 1-full 才實作**（見 §9 B7） |

兩種模式輸出結果完全一致，差別只在 LLM 呼叫由誰發起。一鍵模式需要 CLI 內建 LLM 呼叫層（多供應商支援、API key 管理、錯誤重試、本地模型切換），實作成本獨立，不在 Phase 1-min 範圍內。

### 0.3  信任架構設計

**可信度目標：夠高到讓疑義可見。** 不取代工程師或 QA 的功能驗收。目標是讓原本完全無法參與驗核的非工程師單位，能識別「這個地方看起來不對，需要追問」。

**不確定性來源：**

LLM-centric 架構下，不確定性主要來自單一來源：LLM 的語意推斷。AST 提供的結構資訊是確定的（函式存在就是存在），不確定的是 LLM 對這些結構的功能詮釋。

| 不確定性類型 | 來源 | 緩解機制 |
|---|---|---|
| 功能識別偏差 | LLM 對業務功能的判斷不準確 | 輸出約束 + 信心自評 + 未歸類節點清單 |
| 推斷飄移 | 同一 codebase 不同時間產生不同結果 | 確認後快取，AST 未變化不重新生成；提供重新生成觸發條件（見 §4.1 標記系統） |
| 幻覺 | LLM 虛構不存在的功能或關係 | AST 結構作為事實錨點，LLM 輸出必須可追溯至 AST 節點；推斷關係分層驗證（見 §4.1 第四層） |
| 遺漏 | LLM 未能識別某些功能 | 信心自評 + 未歸類節點清單 |

**兩個設計原則：**

1. **可見性優先**：LLM 的不確定性必須顯示，不能為了「看起來乾淨」而隱藏標記
2. **疑義路徑**：圖形必須設計「使用者發現疑義時的處理路徑」

**一個硬性禁令：**

**禁止幻覺與過度解釋。** LLM 不知道的就標記為不知道，不得為了讓輸出「看起來完整」而虛構功能、關係或描述。寧可輸出一個標記為「信心低」或「未歸類」的誠實結果，也不要一個看起來漂亮但不可靠的結果。這是整個信任架構的底線。

### 0.4  商業價值定位

```
程式碼產出
  → 工具自動轉譯為功能語言圖形 + 自然語言敘述
  → 非工程師單位能夠獨立判讀
  → 驗收疑義在交付前被識別、追蹤、解決
  → 溝通成本 ↓、返工成本 ↓、驗收通過率 ↑
```

**工具責任邊界：**
- 負責：把輸入的程式碼忠實轉譯，標示不確定性，讓疑義可見
- 不負責：確保使用者輸入的程式碼是完整的、未被篩選的
- 不負責：覆蓋所有程式語言和框架的所有模式（接受 LLM 能力邊界）

---

## 1  目標使用者

不讀程式碼，但需要確認「開發產出是否符合承諾」。

| 角色 | 使用時機 | 核查問題 |
|---|---|---|
| 產品經理 PM | 等待開發期間確認進度 | 這個 feature 完成了嗎？有沒有超出範圍？ |
| 專案經理 SPM | Sprint 跟追期 | 開發方向有沒有跑掉？ |
| 發布經理 | 上線前確認更新內容 | 工程師說改了 A，圖形上是否真的只有 A 有變化？ |
| QA / PO | 測試階段概觀確認 | 這次 build 包含哪些功能？有沒有多或少？ |
| 甲方 / 上層 | 里程碑審閱 | 系統整體結構是否符合當初的規劃方向？ |

---

## 2  問題定義

**現有工具的根本缺口：**
- 現有工具給的是「結構圖」（工程師用）
- The Door 要給的是「功能圖」（驗收者用）
- 差別：結構圖回答「怎麼寫的」；功能圖回答「能做什麼」

**非工程師的四個核心問題：**

| # | 問題 | 對應層級 |
|---|---|---|
| 1 | 這個系統能做什麼？ | **L1** 功能總覽 |
| 2 | 各區塊負責哪一段？彼此如何關聯？ | **L1.5** 結構概覽 |
| 3 | 這次更新動了哪裡？嚴不嚴重？ | Diff 視圖 + 影響範圍標記 |
| 4 | 有沒有哪裡看起來特別複雜或危險？ | **L2** 熱點標記 / AI 推斷警示 |

---

## 3  圖形層級模型

預設顯示 L1。L1.5 / L2 以下點擊展開。圖形輸出為 Mermaid.js 渲染，非圖片格式。

| Layer | 名稱 | 受眾 | 來源 | 顯示內容 | 核心問題 |
|---|---|---|---|---|---|
| **L1** | 功能總覽 | 所有人（預設） | LLM 詮釋 | 系統能做什麼、有幾個主要功能、功能間的因果關係 | **這個系統能做什麼？** |
| **L1.5** | 結構概覽 | 所有人（視角切換） | LLM 詮釋 | 系統由哪些部分組成、各部分負責哪一段、彼此如何串聯；觸發方式標注（HTTP / 排程 / 事件） | **各區塊負責哪一段？彼此如何關聯？** |
| **L2** | 功能連動圖 | 驗收導向（點擊展開） | LLM 詮釋 + LLM 異常識別 | 模組層次互動關係；死碼標示；邏輯死路標示；信心標記 | **有沒有異常？有沒有我不知道的東西？** |
| **L3** | 函式呼叫圖 | 技術驗收（點擊展開） | AST 直接輸出 | 函式層次呼叫鏈 | `getUserData()` → `validateToken()` → … |
| **L4+** | 深層呼叫路徑 | 工程師（按需展開） | AST 直接輸出 | 條件分支、參數傳遞 | 工程師定位問題用 |

**各層的語言規則：**
- L1：純功能語言。不出現任何技術詞彙（無 `Service`、`Handler`、`Controller`、`Loader`、`IoC`）。用一般人的話說「這個系統能做什麼」。
- L1.5：過渡語言。可以出現模組名稱，但必須附帶功能說明。不出現技術實作細節（無 decorator 名稱、無 class 結構、無 import 關係）。觸發方式用人話標注（「由用戶操作觸發」「定時自動執行」「由其他功能完成後觸發」）。
- L2 以下：技術語言，受眾已是有基礎的驗收者或工程師。

> **L1 的根本定性：** L1 回答的是「這個系統能為使用者做什麼」，不是「這個系統長什麼樣」。系統結構（由哪些部分組成、如何串聯）是 L1.5 的內容。兩者都由 LLM 詮釋。

> **L1.5 存在的原因：** 非工程師在理解 L1 之後，下一個自然問題是「好，那這些功能是由哪些部分在跑的？它們怎麼搭在一起？」。L1.5 是這兩個問題之間的橋接層，讓使用者能在不進入技術細節的情況下建立對系統架構的基本輪廓。

> **L1 與 L1.5 的 UI 切換語意：** 這不是「展開更多細節」，而是「從功能視角切換到結構視角」。兩者是同等地位的平行視角，不是階層關係。UI 上 L1 和 L1.5 應以並列 tab 或切換按鈕呈現，而不是巢狀展開——避免使用者以為 L1.5 只是 L1 的補充資訊。

**程式碼顯示原則：** L1–L1.5 完全不顯示程式碼或技術識別符。L2 顯示模組名稱（不顯示實作）。L3 起顯示函式名稱。

### 3.1  輸出規範

**處理流程：**
```
使用者輸入程式碼
  → AST 解析（本地）→ 結構化原料 JSON（不做分類，只提取結構）
  → 使用者送出 → LLM 透過拓撲引導讀取（可能多輪），最終彙整產出 L1 + L1.5
  → 預設顯示 L1；平行視角切換至 L1.5；點擊展開 L2
```

**L1 + L1.5 輸出時序說明（多輪讀取後彙整）：**

L1 + L1.5 在拓撲引導讀取完成後一次輸出，不是逐批累積。多輪讀取的中間結果保存在記憶體（Phase 1-min）或敘事鏈 JSONL（Phase 1-full）中，最終批次結束後系統以最終 JSON 覆蓋輸出。

- `feature_id` 在第一批讀取時分配，後續批次可補充該節點的 `source_nodes`，但不重新分配 ID
- L1.5 的 `related_features` 引用的是最終確認後的 `feature_id`，不是中間批次的暫時 ID
- 若多輪讀取後 LLM 對某 L1 節點的判斷改變，以最終批次的判斷為準，並記入敘事鏈

**L1 輸出內容（功能總覽）：**
- 這個系統能做什麼（一段話總結）
- 主要功能清單（每個功能一句功能語言描述）
- 功能間的因果關係（「完成 A 後自動觸發 B」）
- 觸發方式標注（用戶操作 / 定時排程 / 自動觸發），不使用技術詞彙

**L1.5 輸出內容（結構概覽）：**
- 系統由哪些區塊組成、各區塊負責哪一段功能
- 區塊間的關聯性（哪個區塊呼叫哪個、哪個區塊被哪個觸發）
- 觸發機制說明（用人話：「由 HTTP 請求觸發」→「當用戶送出請求時」，「排程觸發」→「系統定時自動執行」，「事件觸發」→「由另一個功能完成後自動通知」）
- 系統基礎設施統一收攏為一個區塊，不拆散進入主要結構

**輸出形式（可切換，切換不重新呼叫 LLM）：**
- `形式 A`：卡片式功能總覽（L1）+ 結構關係圖（L1.5，Mermaid.js）+ 右側說明欄
- `形式 B`：純自然語言敘述，依 L1 → L1.5 順序展開

### 3.2  異常標示規範

L2 層起啟用。異常識別由 LLM 根據 AST 結構資訊判斷，不由 AST 規則預定義。

| 異常類型 | 定義 | 顏色 | 符號 |
|---|---|---|---|
| **死碼** | 無任何呼叫來源，且 LLM 判斷非框架回呼 | 🔵 藍灰色 | `◎` |
| **邏輯死路** | LLM 判斷此路徑在現有條件下無法被執行到 | 🟡 黃色 | `⚠` |
| **不確定邊界** | LLM 無法確定此節點的用途或呼叫來源 | ⬜ 淺灰色 | `⊙` |
| **已知漏洞** | 依賴的套件存在已知 CVE（osv-scanner 偵測） | 🔴 高危 / 🟠 中危 | `⚑` |

嚴重程度優先序：已知漏洞 > 邏輯死路 > 死碼 > 不確定邊界。同一節點命中多類，以最高優先級符號顯示，其餘列入自然語言敘述欄。

### 3.3  自然語言敘述規範

**預設：並列欄模式**（圖形左側為主視圖，右側說明欄隨選取節點動態更新）
**選項：Hover 模式**（適合螢幕空間較小的場景）

**生成策略：**

| 層 | 生成方式 | 語言規則 | 快取策略 |
|---|---|---|---|
| L1 | LLM 生成 | 純功能語言，零技術詞彙 | 快取，AST 未變化不重新生成；可手動觸發重新生成（見 §4.1 標記系統） |
| L1.5 | LLM 生成（與 L1 同一敘事鏈） | 過渡語言，模組名稱需附功能說明 | 同 L1 |
| L2 | LLM 生成 | 技術語言 | 每次重新分析時更新 |
| L3+ | AST 直接輸出 | 技術語言 | 每次由 AST 計算 |

**L1.5 觸發方式的語言約束（寫入 prompt，由 LLM 執行翻譯）：**

| 技術描述 | L1.5 人話版本 |
|---|---|
| HTTP route handler | 當用戶送出請求時觸發 |
| Agenda / Cron job | 系統定時自動執行，與用戶行為無關 |
| EventSubscriber / @On | 由另一個功能完成後自動通知觸發 |
| IoC constructor injection | 系統啟動時自動配置，不需手動呼叫 |
| Middleware | 每次請求進來前自動執行的前置檢查 |

> 以上對照表作為 prompt 的語言約束範例，不是窮舉規則。LLM 遇到未列出的技術模式時，依相同原則自行翻譯為人話。

### 3.4  層級切換規範

- **L1 ↔ L1.5：** 平行視角切換（tab 或切換按鈕），不是展開關係
- **L2 展開：** 點擊節點或展開按鈕進入下一層，再點擊收合
- **預設層數：** 使用者可設定預設顯示到哪一層（L1 / L1.5 / L2），預設值為 L1
- **全展開 / 全收合：** 工具列快捷按鈕

---

## 4  核心能力（MVP 必要條件）

### 4.1  自動生成（code → 圖形）

**架構原則：AST 提供原料，LLM 做所有判斷，系統約束 LLM 的輸出。**

**處理流程：**
```
[本地，無 LLM]
程式碼輸入 → AST 解析（tree-sitter-language-pack）
  → 輸出：結構原料 JSON
     （檔案清單、函式清單、類別清單、呼叫關係、裝飾器、import 關係）
  → 這是原料，不做任何分類判斷

[使用者送出時，LLM 呼叫 — L1 + L1.5 生成]
結構原料 JSON → LLM（含輸出約束 prompt）
  → LLM 同時完成：
     ① 識別業務功能 vs 基礎設施（分類）
     ② 將業務功能組織為 L1 節點（功能群組）
     ③ 為每個 L1 節點生成功能語言敘述（翻譯）
     ④ 生成 L1.5 結構概覽（結構視角）
     ⑤ 對每個節點自評信心程度（信心標記）
  → L1 的節點數、名稱、邊界由 LLM 判斷，不由規則預定義

[使用者點擊展開 L2 時，LLM 呼叫 — L2 生成]
結構原料 JSON（對應 L1 節點的子集）→ LLM
  → LLM 識別模組間連動關係 + 異常標記
  → 輸出：L2 節點 + 連動關係 + 異常標記 + 信心自評
```

**AST 的角色：結構化壓縮器（必要元件，一律使用）**

AST（tree-sitter-language-pack）一律對所有輸入的程式碼執行結構提取，不區分專案大小。支援 305+ 語言，`pip install tree-sitter-language-pack` 單一套件即可，不需要逐語言管理 grammar。

**為什麼一律使用：**
- 統一處理流程，不需要判斷「這個專案該不該用 AST」的額外邏輯
- 結構化 JSON 比原始碼更穩定、更可預測，LLM 輸出品質更一致
- token 消耗可控，大型 codebase 不會撞 context window
- AST 提取的結構資訊（呼叫關係、import 關係）是 LLM 無法從原始碼片段中可靠推斷的

**AST 提取的原料（保留足夠上下文，不過度壓縮）：**
- 檔案清單與目錄結構
- 函式 / 類別 / 方法的名稱與位置
- 函式間的呼叫關係（靜態可見的部分）
- import / require 關係
- 裝飾器 / 註解（原樣保留，不做解讀）
- 函式參數與回傳型別（若語言有型別標注）
- 文件字串 / docstring（原樣保留，這是 LLM 理解功能的重要線索）
- 關鍵註解（TODO、FIXME、業務說明類註解）

**AST 不做的事（所有判斷交給 LLM）：**
- 不判斷什麼是基礎設施 → LLM 判斷
- 不判斷什麼是業務邏輯 → LLM 判斷
- 不判斷死碼 vs 框架回呼 → LLM 判斷
- 不做裝飾器優先序分類 → LLM 判斷
- 不做非同步呼叫模式偵測 → LLM 判斷

**LLM 約束設計（核心 IP）**

LLM 的輸出品質由四層約束控制：

**第一層：輸入約束（控制 LLM 看到什麼）**
- 一律送 AST 結構原料 JSON，不送原始程式碼（統一流程，降低 token 消耗）
- JSON 按當前需要的層級裁剪（L1 不需要函式內部細節）
- docstring 和關鍵註解保留在 JSON 中，確保 LLM 有足夠語意線索

**AST 拓撲引導讀取策略（世代四）：**

大型 codebase 一次全送不實際（context window 限制）。世代四的解法：**在呼叫 LLM 之前，先用 AST 建立全域依賴拓撲圖，讓讀取順序由結構決定，不由 LLM 猜測。**

```
[純本地，無 LLM，AST 提取完成後立即執行]

第一步：拓撲分析
  → 對所有節點計算：
     - 入度（被多少其他節點呼叫）
     - 出度（呼叫多少其他節點）
     - 入口節點（is_entry_point：入度為 0，且帶有框架入口裝飾器
       或出度 > 0 且檔案位置在 routes/handlers/controllers 目錄）
  → 建立拓撲排序清單

第二步：批次分配優先序規則
  ① is_entry_point = true 的節點 → 一律 batch=1（無論入度高低）
  ② 剩餘節點依 in_degree 由高至低排序，依序分配批次
  → 此規則確保 HTTP handler、CLI entry、排程入口等零入度業務核心
    永遠在第一批讀到，不被高入度 utility 函式（logger、config loader）擠佔

第三步：LLM 沿拓撲路徑逐層分析
  → 每批輸出：當前批次的 L1 骨架更新 + 信心評估
  → 信心高的節點不再追加其依賴（剪枝，節省 token）
  → 信心低的節點標記，下一批優先補充其依賴
```

**is_entry_point 判斷規則（AST 層，不需 LLM）：**
- 帶有已知框架入口裝飾器（`@app.route`、`@Controller`、`@Get`、`@Post`、`@Cron`、`@EventSubscriber` 等），或
- 入度為 0 且出度 > 0 且檔案路徑包含 `routes/`、`handlers/`、`controllers/`、`views/`、`endpoints/`

> **設計說明：** HTTP handler、排程觸發點等框架入口節點入度天然為 0（沒有其他程式碼呼叫它們，它們被框架呼叫）。若僅以入度高低排序，這些業務入口會落在後面的批次，導致 LLM 先讀到大量 utility 函式而不是業務核心。is_entry_point 規則確保批次優先序反映業務重要性，而不只是依賴計數。

**拓撲計算規格：**
- 計算工具：純 Python（networkx，MIT）或自行實作 DFS，無 LLM 成本
- 輸入：AST edges（`calls | imports | extends | implements`）
- 輸出：`{ node_id, in_degree, out_degree, topology_rank, is_entry_point, batch_assignment }` 陣列
- 計算時間：與節點數線性相關，千節點級 codebase < 1 秒
- 結果寫入 AST 結構原料 JSON 的 `topology` 欄位，供 LLM 呼叫層使用

**拓撲引導相對世代三的改進：**

| 面向 | 世代三（漸進式） | 世代四（拓撲引導） |
|---|---|---|
| 讀取順序決策者 | LLM（猜名稱） | AST 拓撲結構（有依據） |
| 業務入口保證 | 不保證 | 保證——entry_point 節點必在 batch=1 |
| 核心邏輯保證 | 不保證 | 保證——高入度節點優先於其他非入口節點 |
| 貪婪追加問題 | 存在 | 消除——追加由拓撲決定 |
| token 效率 | 不可預測 | 可預測——剪枝機制主動跳過高信心節點 |

**敘事鏈（narrative chain）：**
- 每一批的讀取紀錄、拓撲排名、LLM 判斷過程都保存為敘事鏈
- 敘事鏈記錄：每批讀了哪些節點（及其拓撲排名與 is_entry_point 狀態）、LLM 做了什麼判斷、哪些節點被剪枝
- 有問題時可以沿著敘事鏈回查：「這個 L1 節點是在第幾批、拓撲排名第幾、基於哪些依賴判斷出來的？」
- **敘事鏈持久化：** Phase 1-full 才啟用，以 JSONL 格式（每行一條記錄，append-only）寫入本地，跨 session 可接續。Phase 1-min 使用記憶體版本，session 結束後不保留。

**輪次上限：** 預設最多 5 批。超過上限仍有未歸類節點的，標記為 `[資訊不足：未完整讀取]`。拓撲引導確保業務入口和核心邏輯在前幾批讀到，上限觸發時遺漏的通常是低入度的葉節點（工具函式、helper），對 L1 影響有限。

**第二層：原始碼回查機制（AST JSON 不足時的補救路徑）**

AST 結構化後可能丟失 LLM 判斷所需的上下文。系統提供回查路徑，讓 LLM 在不確定時能查看原始碼片段，而不是猜測。

- LLM 在輸出中可標記 `needs_source_review: true`，附帶 `review_reason`（說明為什麼 AST JSON 資訊不足）
- 系統收到此標記後，自動擷取對應 AST 節點的原始碼片段（函式體 / 類別定義），送給 LLM 進行二次判斷
- 二次判斷的結果標記為 `[AI 推斷：已回查原始碼]`，信心程度由 LLM 重新自評
- 回查範圍限制：只送被標記節點的原始碼片段，不送整個檔案（控制 token 消耗）
- 回查次數限制：每個節點最多回查一次，防止無限迴圈

**回查觸發條件（寫入 prompt 約束）：**
- 函式名稱無法推斷功能（如 `process()`、`handle()`、`run()`）且無 docstring
- 裝飾器或註解屬於 LLM 不認識的框架
- 呼叫關係在 AST JSON 中不完整（如動態呼叫、反射）
- 節點的業務歸屬無法從名稱和上下文判斷

**第三層：輸出約束（控制 LLM 產出什麼）**

**核心原則：不知道就說不知道。禁止幻覺，禁止過度解釋。**

- 強制輸出格式：JSON schema 定義每個層級的必要欄位
- 語言約束：L1 禁止技術詞彙（prompt 中列出禁用詞清單 + 正面範例）
- 結構約束：每個 L1 節點必須關聯至少一個 AST 節點（防止幻覺）
- 信心自評：每個節點必須附帶 `confidence: high | medium | low` 及理由
- 未歸類節點：LLM 必須列出無法歸類的 AST 節點清單（防止遺漏）

**禁止幻覺約束（寫入 prompt，硬性規則）：**
- 禁止描述 AST 中不存在的功能或關係
- 禁止推測程式碼的「意圖」超出名稱、docstring、呼叫關係能支撐的範圍
- 禁止補全 AST 中缺失的靜態呼叫關係（AST 沒有的靜態邊，LLM 不能直接畫上去；若 LLM 推斷存在非靜態關係，必須標記 `relation_type: "inferred"` 並說明推斷依據）
- 若 LLM 無法判斷某節點的功能，必須歸入 `unclassified_nodes`，不得強行歸類
- 若 LLM 對某個功能描述沒有把握，必須標記 `confidence: low` 並說明原因，不得用模糊語言掩蓋不確定性

**禁止過度解釋約束（寫入 prompt，硬性規則）：**
- L1 敘述必須基於 AST 結構中可見的事實，不得加入推測性描述
- 「這個函式可能用於...」「這個模組看起來像是...」等推測性語言禁止出現在 `confidence: high` 的節點
- 功能描述的粒度必須與 AST 提供的資訊量匹配：資訊少則描述簡短，不得為了「看起來完整」而擴充描述

**第四層：輸出驗證（系統自動檢查 LLM 輸出）**

輸出驗證由 `jsonschema`（MIT）執行格式檢查，其餘四項語意檢查由 CLI 自行實作：

- **格式檢查**：輸出是否符合 JSON schema（`jsonschema` 驗證，Draft 2020-12）
- **覆蓋率檢查**：LLM 輸出的 L1 節點 + unclassified_nodes + infrastructure_nodes 是否覆蓋了 AST 中所有節點
- **語言檢查**：L1 敘述中是否包含禁用技術詞彙
- **錨點檢查**：每個 L1 節點是否可追溯至至少一個 AST 節點（防止幻覺：不存在於 AST 中的功能 = 幻覺）
- **關係驗證（分層）：**
  - `relation_type: "static"` 的 feature_relations：每條邊必須在 AST edges 中找到對應路徑（嚴格驗證）
  - `relation_type: "inferred"` 的 feature_relations：僅驗證兩端的 feature_id 均可追溯至 AST 節點（寬鬆驗證），推斷關係本身允許 AST edges 中不存在

> **設計說明（兩層關係驗證）：** LLM 有能力識別 AST 靜態分析無法追蹤的關係（非同步呼叫、事件驅動、IoC 注入等）。若要求所有關係均有 AST edge 對應，等於禁止 LLM 補全靜態盲點，與 LLM-Centric 架構矛盾。解法是分層驗證：靜態關係嚴格驗，LLM 推斷關係只驗錨點，推斷依據記入 `relation_type` 和 `confidence_reason`，讓使用者能判斷可信度。

驗證失敗時：自動重試一次（附帶失敗原因），仍失敗則標記 `[輸出驗證失敗]` 並顯示原始 AST 結構。

**LLM 呼叫策略：**
- L1 + L1.5 透過拓撲引導讀取產出（可能多輪），最終結果在同一個敘事鏈中彙整為一次輸出
- L2 展開時才觸發額外 LLM 呼叫（只送對應節點的子集 JSON）
- 切換顯示形式不重新呼叫 LLM
- L1 + L1.5 敘述快取，AST 結果未變化時不重新翻譯

**標記系統：**
- `[AI 推斷：信心高]` / `[AI 推斷：信心中]` / `[AI 推斷：信心低]` — LLM 自評
- `[AI 推斷：已回查原始碼]` — 經過原始碼回查後的判斷
- `[AI 推斷：推斷關係]` — LLM 推斷的非靜態關係（非同步呼叫、事件驅動、IoC 等）
- `[資訊不足：未完整讀取]` — 拓撲引導讀取達到輪次上限仍無法判斷

**重新生成觸發條件（使用者可手動觸發，不依賴 AST 變化）：**
- 使用者認為 LLM 初次生成的 L1 描述有偏差（例如功能定性錯誤、遺漏主要功能）
- UI 提供「重新生成此節點」按鈕：清除快取 → 以相同 AST 原料重新呼叫 LLM
- 重新生成的結果若與前次不同，標記 `[AI 推斷：重新生成，與前次不同]`，讓使用者能比較兩次結果
- 重新生成紀錄寫入敘事鏈（Phase 1-full 後持久化）

**信心低時的處理策略：**
觸發 `[AI 推斷：信心低]` 時，依序執行：
1. 系統檢查該節點是否標記 `needs_source_review: true`
   - 若是 → 先執行原始碼回查（§4.1 第二層），取得原始碼片段後重新判斷
   - 若否 → 進入步驟 2
2. 系統自動將該節點的上下游依賴資訊補充送給 LLM 進行二次推斷
3. 若信心提升 → 更新標記為 `[AI 推斷：信心中（補充上下文）]` 或 `[AI 推斷：已回查原始碼]`
4. 若仍然低 → 維持 `[AI 推斷：信心低]`，說明欄補充具體原因，並記錄於敘事鏈
5. 不得為了提升信心而過度解釋 — 信心低就是信心低，如實呈現

### 4.2  Diff 視圖

顯示「這次和上次的差異」。

**「上次」的三種觸發方式：**
- git tag / commit SHA（技術用戶）
- 日期選擇器（非技術用戶）
- 手動標記的「版本快照」

**Diff 三個比對維度：**

| 維度 | 定義 | 顏色 |
|---|---|---|
| 節點新增 / 移除 | 功能模組整體出現或消失 | 🟢 新增 / 🔴 移除 |
| 節點屬性變更 | 模組名稱或功能描述改變 | 🟠 淺橘 |
| 依賴關係變更 | 兩模組之間的呼叫關係新增或移除 | 🟠 深橘（優先級高於屬性變更） |

### 4.3  範圍邊界驗核

- PM / SPM 可事先定義「這個 sprint 應包含哪些功能」
- 圖形自動標記：在範圍內 `✓` / 超出範圍 `⚠` / 範圍內未完成 `○`
- 發現 `⚠` 時有明確下一步：標記疑義 → 通知對應工程師 → 等待說明或校正
- 疑義狀態機完整定義（含超時升級機制）在 Phase 3 實作；概念設計在 Phase 0a 先行驗證

### 4.4  自動同步

自動同步只更新 AST 原料，不觸發 LLM。

```
code commit
  → [自動，本地] AST 重新解析 → 更新結構原料 JSON
  → [不自動] LLM 翻譯不觸發

使用者下次開啟時：
  → 工具提示「上次分析後有 N 個結構變更，是否重新翻譯？」
  → 使用者決定是否送出 → 才觸發 LLM 單次呼叫
```

### 4.5  影響範圍分析

點選任何節點 → 顯示「如果此節點發生變化，哪些其他節點受影響」。

**計算深度規則：**
- 預設：只顯示直接依賴（一層）
- 展開：使用者可點擊「展開間接影響」逐層展開
- 上限：展開深度不超過使用者設定的預設顯示層數

基於 AST 依賴關係圖計算，不需要額外 LLM 呼叫。

### 4.6  匯出功能（Phase 1-full 後）

- Mermaid 文字一鍵複製
- SVG 匯出（Mermaid.js 原生支援）

### 4.7  漏洞資訊層（osv-scanner 整合）

**架構：**
```
[本地，與 AST 並行，不阻塞主流程]
程式碼輸入 → osv-scanner 掃描 lockfile / manifest
  → 輸出 { package, version, cve_id, severity }
  → 寫入結構原料 JSON 的 vulnerabilities 欄位

[圖形渲染時]
漏洞資訊隨結構原料一併送給 LLM
  → LLM 在 L2 輸出中標記受影響的功能模組
L1 功能群組 → 若群組內含漏洞節點，群組邊框以 🔴 / 🟠 高亮
```

**顯示規則：**

| 嚴重程度 | CVSS | 圖形標記 |
|---|---|---|
| 高危 | ≥ 7.0 | 🔴 `⚑` 節點紅框 |
| 中危 | 4.0–6.9 | 🟠 `⚑` 節點橘框 |
| 低危 | < 4.0 | 不標記於圖形，僅列入漏洞摘要側欄 |

**技術邊界：**
- 掃描對象：lockfile / manifest，不分析原始程式碼
- 支援離線模式（`--offline`，本地 OSV 資料庫）
- 資料隱私：只傳送套件名稱 + 版本號，不傳送原始碼

---

## 5  系統架構分層

**產品形態：The Door CLI + MCP Server + 約束 prompt 檔案 + 輸出 schema**

**技術選型：**
- **CLI 主程式：Python**（tree-sitter-language-pack 有 Python binding；生態豐富；安裝方式：`pip install` / `pipx` / `uvx`）
- **語言支援：** `tree-sitter-language-pack`（MIT，305+ 語言，單一套件，on-demand 下載）
- **拓撲分析：** `networkx`（BSD-3）或自行實作 DFS，純本地，無 LLM 成本
- **輸出驗證：** `jsonschema`（MIT，Draft 2020-12，格式驗證）
- **MCP Server：** `mcp` Python SDK（Apache 2.0，`pip install mcp`）
- **渲染生成：Node.js**（Mermaid.js 原生 Node.js；用於 Mermaid 文字 → SVG 轉換）
- **跨平台：** Windows / macOS / Linux 全支援
- **安裝方式：** `pip install the-door`（Python 部分）+ `npx` 或 bundled Node.js（渲染部分）

```
the-door/
  ├── cli/                    # The Door CLI 主程式（Python）
  │   ├── ast-extract         # tree-sitter-language-pack 結構提取
  │   ├── topology            # AST 拓撲分析（入度/出度/排名/is_entry_point/批次分配）
  │   ├── progressive-read    # 拓撲引導讀取引擎（敘事鏈管理；Phase 1-full 起持久化）
  │   ├── validate            # 輸出驗證（jsonschema 格式 + 四項語意檢查 + 關係分層驗證）
  │   └── render              # Mermaid 渲染生成（Node.js）
  ├── mcp/                    # The Door MCP Server（Python，mcp SDK）
  │   ├── server.py           # MCP Server 主程式
  │   └── tools/
  │       ├── extract.py      # tool: extract_structure（呼叫 cli/ast-extract + cli/topology）
  │       └── validate.py     # tool: validate_output（呼叫 cli/validate）
  ├── prompts/                # 約束 prompt 檔案（可攜帶，AI 媒介讀取使用）
  │   ├── l1-constraint.md    # L1 + L1.5 約束 prompt（含拓撲優先序提示 + 推斷關係標記規則）
  │   ├── l2-constraint.md    # L2 約束 prompt
  │   └── language-rules.md   # 語言約束（禁用詞清單 + 正面範例）
  ├── schemas/                # 輸出 JSON schema（jsonschema 驗證用）
  │   ├── ast-raw.schema.json # AST 結構原料格式（含 topology 欄位）
  │   ├── l1-output.schema.json
  │   ├── narrative.schema.json # 敘事鏈格式（JSONL，含批次 + 拓撲資訊）
  │   └── log.schema.json
  └── config/                 # 使用者設定（LLM API key、本地模型路徑等，Phase 1-full 後啟用）
```

**MCP Server 架構：**

The Door MCP Server 讓所有 MCP-compatible AI 媒介（Claude Desktop、Cursor、任何支援 MCP 的工具）零摩擦接入，不需要任何自定義整合。

```python
# 兩個核心 MCP tool
@mcp.tool()
def extract_structure(codebase_path: str) -> dict:
    """
    從 codebase 提取 AST 結構原料 JSON（含拓撲分析結果）。
    輸出可直接配合 prompts/l1-constraint.md 送給任何 LLM。
    """

@mcp.tool()
def validate_output(llm_output: dict) -> dict:
    """
    驗證 LLM 輸出的格式、覆蓋率、語言約束、錨點、關係分層。
    回傳驗證結果 + 失敗原因（若有）。
    """
```

MCP Server 啟動方式：
```bash
# 直接啟動（供 Claude Desktop 或其他 MCP client 連線）
the-door mcp-serve

# 或透過 mcp SDK 標準方式
python -m the_door.mcp.server
```

**資料流向（AI-Medium-Agnostic）：**
```
AI 媒介（MCP Client 或 CLI）指定 codebase 路徑
  → [CLI / MCP tool] AST 結構提取（tree-sitter-language-pack，一律執行）
  → [CLI，純本地] 拓撲分析（入度/出度/is_entry_point/批次分配，寫入 topology 欄位）
                  + osv-scanner 漏洞掃描（選配，與拓撲分析並行）
  → [CLI / MCP tool] 輸出結構原料 JSON（含 topology 欄位）
  → [AI 媒介 或 CLI] 依 topology.batch_assignment 分批送 LLM + 約束 prompt
  → [CLI / MCP tool] 輸出驗證（jsonschema 格式 + 四項語意檢查 + 關係分層驗證）
  → [CLI] 渲染生成（Mermaid 文字 + 自然語言敘述 JSON）
  → AI 媒介以自己的方式呈現結果
```

| 層 | 技術方向 | 歸屬 | 策略 |
|---|---|---|---|
| 輸入層 | 本地檔案路徑 / git repo | CLI | 自己實作 |
| AST 結構提取層 | tree-sitter-language-pack（MIT，305+ 語言） | CLI | 直接使用，一律執行 |
| **拓撲分析層** | **networkx（BSD-3）或自行實作 DFS** | **CLI** | **AST 提取完成後立即執行，純本地，無 LLM，結果寫入 `topology` 欄位** |
| 漏洞掃描層 | osv-scanner (Apache 2.0) | CLI | 直接使用，選配 |
| 結構原料層 | JSON（自訂 schema，含 topology 欄位） | CLI 輸出 | 自己定義 |
| **約束 prompt 層** | **Prompt 檔案（.md）** | **專案內檔案，AI 媒介讀取** | **核心 IP** |
| **輸出 schema 層** | **JSON schema 檔案** | **專案內檔案** | **自己定義** |
| **MCP Server 層** | **mcp Python SDK（Apache 2.0）** | **CLI 功能的 MCP 包裝** | **直接使用** |
| LLM 呼叫層 | 任何 LLM（API 或本地） | AI 媒介 或 CLI（一鍵模式，Phase 1-full 後） | 不綁定供應商 |
| 輸出驗證層 | jsonschema（MIT）+ 四項語意檢查 + 關係分層驗證 | CLI | jsonschema 直接使用；語意檢查自己實作 |
| 渲染生成層 | Mermaid 文字生成 | CLI | 自己實作 |
| 圖形渲染層 | Mermaid.js (MIT) / D3.js (BSD-3) | AI 媒介的 UI 層 | 由 AI 媒介決定如何渲染 |
| Diff 引擎 | JSON 文字 diff | CLI | 自己實作 |
| 影響範圍分析層 | AST 依賴關係圖 | CLI | 自己實作，無額外 LLM |
| 範圍驗核層 | 使用者定義範圍 → 自動比對 | CLI | 自己實作 |

### 5.1  JSON Schema 定義

**結構原料 JSON（AST 輸出，送給 LLM 的原料）：**

AST 只提取結構事實，不做任何分類標記。拓撲分析結果寫入 `topology` 欄位，供讀取順序引導使用。

```json
{
  "files": [
    {
      "path": "string",
      "language": "python | typescript | java | ..."
    }
  ],
  "nodes": [
    {
      "node_id": "string",
      "type": "function | class | method",
      "name": "string",
      "file": "string",
      "language": "string",
      "decorators": ["string"],
      "parameters": ["string"],
      "return_type": "string | null",
      "docstring": "string | null",
      "comments": ["string"]
    }
  ],
  "edges": [
    {
      "from": "node_id",
      "to": "node_id",
      "type": "calls | imports | extends | implements"
    }
  ],
  "topology": [
    {
      "node_id": "string",
      "in_degree": 0,
      "out_degree": 0,
      "topology_rank": 1,
      "is_entry_point": true,
      "batch_assignment": 1
    }
  ],
  "vulnerabilities": [
    {
      "cve_id": "string",
      "package": "string",
      "version": "string",
      "severity": "critical | high | medium | low",
      "cvss": 0.0,
      "source": "osv-scanner"
    }
  ]
}
```

**`topology` 欄位說明：**
- `in_degree`：被其他節點呼叫的次數，數字越高表示越核心
- `out_degree`：呼叫其他節點的次數
- `topology_rank`：全域拓撲排名，1 為最優先讀取
- `is_entry_point`：帶有框架入口裝飾器，或入度為 0 且出度 > 0 且檔案位置在 routes/handlers/controllers 等入口目錄
- `batch_assignment`：預先計算的批次分配。is_entry_point=true 一律 batch=1；其餘依 in_degree 由高至低排序分配批次

**LLM 輸出 JSON（L1 + L1.5）：**

```json
{
  "l1": {
    "summary": "string（一段話總結系統功能）",
    "features": [
      {
        "feature_id": "string",
        "label": "string（功能語言，零技術詞彙）",
        "description": "string（功能語言敘述）",
        "trigger": "user_action | scheduled | auto_triggered",
        "trigger_description": "string（人話描述觸發方式）",
        "confidence": "high | medium | low",
        "confidence_reason": "string",
        "source_nodes": ["node_id（對應 AST 節點）"],
        "needs_source_review": false,
        "review_reason": "string | null"
      }
    ],
    "feature_relations": [
      {
        "from": "feature_id",
        "to": "feature_id",
        "relation": "string（功能語言描述因果關係）",
        "relation_type": "static | inferred",
        "inferred_reason": "string | null（relation_type=inferred 時必填，說明推斷依據）"
      }
    ],
    "unclassified_nodes": ["node_id（LLM 無法歸類的 AST 節點）"],
    "infrastructure_nodes": ["node_id（LLM 判斷為基礎設施的節點）"]
  },
  "l1_5": {
    "blocks": [
      {
        "block_id": "string",
        "label": "string（模組名稱 + 功能說明）",
        "responsibility": "string",
        "trigger_mechanism": "string（人話）",
        "related_features": ["feature_id"]
      }
    ],
    "block_relations": [
      {
        "from": "block_id",
        "to": "block_id",
        "relation": "string",
        "relation_type": "static | inferred",
        "inferred_reason": "string | null"
      }
    ],
    "infrastructure_block": {
      "label": "系統基礎設施",
      "components": ["string"]
    }
  }
}
```

**敘事鏈格式（JSONL，Phase 1-full 起持久化）：**

```jsonl
{"batch": 1, "strategy": "topology_guided", "nodes_read": [{"node_id": "auth_route", "topology_rank": 1, "in_degree": 0, "is_entry_point": true}, {"node_id": "auth_service", "topology_rank": 2, "in_degree": 12}], "llm_judgment": "識別到用戶管理和驗證為核心功能群組，信心高", "pruned_nodes": [], "pending_low_confidence": ["notification_tasks"], "timestamp": "ISO8601"}
{"batch": 2, "strategy": "topology_guided", "nodes_read": [{"node_id": "notification_tasks", "topology_rank": 8, "in_degree": 2, "is_entry_point": false}], "llm_judgment": "確認通知為非同步任務，補充上下文後信心由低升至中", "pruned_nodes": ["base_model", "config_loader"], "pending_low_confidence": [], "timestamp": "ISO8601"}
```

**LOG 格式（版本快照，用於 Diff）：**

```json
{
  "version_id": "string",
  "commit_hash": "string | null",
  "git_tags": ["v1.2.0"],
  "trigger": "commit | pr_merge | manual",
  "timestamp": "ISO8601",
  "l1_snapshot": {
    "feature_id": {
      "label": "string",
      "description": "string",
      "source_node_count": 0,
      "confidence": "high | medium | low"
    }
  },
  "analyzed_files": ["string（本次分析涵蓋的檔案清單）"],
  "vulnerabilities": []
}
```

### 5.2  多語言處理

LLM-centric 架構下，多語言不是特殊問題：

- AST 以 `language` 欄位標記每個節點的來源語言
- LLM 在 L1 層不關心底層語言，只關心功能語意
- 跨語言依賴在 L1.5 / L2 由 LLM 自行識別並標注
- 不需要 AST 層的跨語言合併策略

**tree-sitter-language-pack 涵蓋範圍：** 305+ 語言，包含所有主流語言（Python、TypeScript、Java、Go、Rust、Ruby、PHP 等），MIT 授權，on-demand 下載。

**不支援的語言：**
- 直接將原始碼送給 LLM 辨識（跳過 AST 結構提取）
- 若 LLM 也無法辨識 → 拒絕處理該檔案，標記為 `[不支援的語言]`
- 不為不支援的語言開發新的解析器 — 接受工具的能力邊界

### 5.3  圖形渲染方案

**The Door CLI 輸出 Mermaid 文字，渲染由 AI 媒介的 UI 層負責。**

| 輸出格式 | 說明 | 消費者 |
|---|---|---|
| Mermaid 文字 | CLI 直接輸出，可被任何 Mermaid 渲染器處理 | 所有 AI 媒介 |
| JSON（L1 + L1.5 敘述） | 結構化資料，AI 媒介可自行決定呈現方式 | 所有 AI 媒介 |
| SVG | Mermaid.js 渲染後的圖形（若 AI 媒介支援） | Web UI、IDE |
| MD 純文字 | 最低限度的文字模擬圖形（fallback） | CLI 終端、無 UI 環境 |

**Phase 對應：**

| Phase | 渲染方式 |
|---|---|
| Phase 0a | MD 純文字模擬（零成本驗證） |
| Phase 1-full | CLI 輸出 Mermaid 文字；AI 媒介自行渲染 |
| 進階 | Kroki（MIT，25+ 格式，本地 Docker）按需啟用 |

Kroki 本地部署：`docker run -p 8000:8000 yuzutech/kroki`

---

## 6  授權策略

| 授權類型 | 代表專案 | 商用策略 |
|---|---|---|
| MIT | tree-sitter, tree-sitter-language-pack, Mermaid.js, Ollama, jsonschema, networkx | ✅ 直接使用 |
| Apache 2.0 | Qwen3, Mistral 7B, osv-scanner, mcp Python SDK | ✅ 直接使用 |
| BSD-3 | D3.js | ✅ 直接使用 |
| MIT + Commons Clause | AppMap libraries | ⚠ 只參考資料格式與 Diff 設計概念，不觸發限制條款 |
| GPL v2/v3 | Gource 等 | ⚠ 借鑒概念可以，不抄程式碼 |
| AGPL | 部分 SaaS 工具 | ⚠ 謹慎評估 |
| 商業 / BSL | IcePanel 等 | 🚫 只參考產品設計邏輯，不碰程式碼 |

> **MCP 協定本身：** MCP 於 2025 年 12 月由 Anthropic 捐給 Linux Foundation 下的 Agentic AI Foundation，是真正的開放標準，非單一廠商協定，商用無障礙。

---

## 7  市場現況與缺口確認

| 工具 | 自動讀 code | 非工程師可讀 | Diff / 驗核 | 主要缺口 |
|---|---|---|---|---|
| IcePanel | ✗ 手動建模 | ✅ C4 分層 | ✅ 版本追蹤 | 圖形需工程師手動維護 |
| CodeSee | ✅ 自動生成 | ✗ 工程師用 | ✅ PR diff | 受眾是工程師 |
| Swark | ✅ AI 讀 repo | ✗ 技術圖 | ✗ | 輸出是技術架構圖，非功能語言 |
| Miro | ✗ 手動 | ✅ | ✗ | 協作工具，不是驗核介面 |

**市場缺口：** 沒有任何工具同時做到 ① 自動從 code 生成 ② 功能語言圖形（非工程師直接可讀）③ Diff + 範圍邊界驗核。

---

## 8  執行順序（Phase 規劃）

| Phase | 名稱 | 交付物 | 驗收場景 | 前提 |
|---|---|---|---|---|
| **0a** | 圖形語言規範（結構層） | L1–L2 圖形語言定義 + Diff 視覺符號 + 範圍邊界協定 + 疑義路徑概念設計；不含信心標示 | 給 PM / 發布經理看 paper prototype，能在 10 分鐘內回答「這次改了哪裡」並識別出至少一個刻意埋入的疑義點，且能說出「發現疑義後的下一步」 | 無 |
| **1-min** | LLM 約束管線最小實作 + MCP Server 核心 + 拓撲分析模組 | AST 結構提取 + 拓撲分析（入度/出度/is_entry_point/批次分配）+ LLM 約束 prompt（B6 第①–⑥項）+ 輸出驗證（jsonschema + 語意檢查 + 關係分層驗證）；MCP Server 兩個核心 tool；完整模式（AI 媒介呼叫）；在 3 份開源測試 codebase 上跑出結果 | **L1 功能識別準確率 ≥ 70%**；**覆蓋率 ≥ 90%**；**拓撲引導 token 節省率 ≥ 20%（相對不用拓撲引導的全送方式）**；LLM 輸出通過驗證；至少一個 MCP client 成功呼叫完整流程；entry_point 節點確認全數分配至 batch=1 | Phase 0a 完成；B6 第①–⑥項完成 |
| **0b** | 信心標示規範 | 根據 Phase 1-min 實測數字設計信心標示視覺規範；整合進 Phase 0a 形成完整 Phase 0 交付物 | 非工程師能區分「這個標記代表需要追問」vs「這個標記代表可信任」；授權清單完成確認 | Phase 1-min 完成 |
| **1-full** | LLM 翻譯引擎（完整）+ 敘事鏈持久化 + 一鍵模式 | 讀取 code → L1–L2 圖形輸出（含信心標記）+ 拓撲引導批次讀取完整實作 + 敘事鏈 JSONL 持久化（跨 session 可接續）+ 重新生成觸發功能 + 一鍵模式（CLI 內建 LLM 呼叫，多供應商支援）+ API 成本模型量級估算 + B6 第⑦–⑬項約束完成 | L1 品質達 Phase 0b 閾值；低信心項目正確顯示警示標記；跨 session 敘事鏈可接續；剪枝機制正確跳過高信心節點；一鍵模式可用 | Phase 0b 完成 |
| **2** | Diff 引擎 | 版本比對 → 新增 / 移除 / 修改視覺標記；三種「上次」觸發方式均可運作 | 非工程師能獨立操作，不依賴工程師說明，完成「這次和上次的差異在哪」的確認 | Phase 1-full 完成 |
| **2.5** | 漏洞資訊層 | osv-scanner 整合；L2 節點正確顯示 `⚑`；L1 功能群組邊框高亮；說明欄顯示 CVE ID + 嚴重程度 + 行動建議 | 非工程師能從圖形識別「哪個功能模組有安全風險」，不需閱讀 CVE 清單 | Phase 2 完成 |
| **3** | 範圍驗核層 | PM 定義範圍 → 圖形自動比對；疑義狀態機完整實作（含超時升級機制） | PM 定義假設 sprint 範圍，工具正確標記超出範圍項目，疑義追蹤流程可完整走完含超時升級 | Phase 2.5 完成 |
| **4** | 歷史時間軸層 | 功能演進時間軸：功能從何時出現、中間改了幾次、現在狀態 | 驗核者能回答「這個功能在過去三個月的演進路徑是否符合承諾」 | Phase 1-full–3 驗證完成後疊加 |
| **5** | 即時動態層 | coding 中的即時變化圖形 | Phase 1–4 驗證完成後獨立 UX 評估 | Phase 4 完成 |

**Phase 0a 執行說明：**
- prototype 工具：MD 純文字模擬圖 + Claude artifact 生成互動版本，0 工程成本，今天可啟動
- 測試對象：3–5 位外部非工程師（PM 和非技術管理者各至少一人）
- paper prototype 必須包含「使用者在圖形上發現 `⚠` 後的下一步」示意場景
- **Go 標準：** 5 人中 ≥ 4 人（80%）能在 10 分鐘內完成驗收場景
- **停損條件：** ≥ 3 輪迭代後仍有 > 50% 測試對象無法完成 → 圖形語言規範根本性重設計

**Phase 1-min 執行說明：**
- 實作 The Door CLI 核心：AST 結構提取指令（`the-door extract <path>`）
- **實作拓撲分析模組（`the-door topology <ast-json>`）：** 計算入度/出度/is_entry_point/批次分配，寫入 topology 欄位
- 設計約束 prompt 檔案初版（B6 第①–⑥項：輸入裁剪 + L1 輸出 schema + 語言約束 + 信心自評 + 未歸類節點 + 錨點約束）
- 實作輸出驗證指令（`the-door validate <llm-output>`），整合 jsonschema 格式驗證 + 關係分層驗證
- **實作 MCP Server 核心兩個 tool（`extract_structure`（含拓撲分析） + `validate_output`）**
- **Phase 1-min 的敘事鏈為記憶體版本，session 結束後不持久化**（持久化移至 Phase 1-full）
- 在 3 份開源 codebase 上測試，量化：功能識別準確率（≥ 70%）、覆蓋率（≥ 90%）、token 節省率（≥ 20%）
- 同步測試 API 模型 vs 本地模型（Ollama + Qwen3/Mistral）的品質差距
- **驗證至少一個 MCP client（Claude Desktop 或 Cursor）能成功呼叫完整流程**
- **驗證 is_entry_point 節點（HTTP handler 等）全數分配至 batch=1**

---

## 9  阻擋項（動工前必須先定義）

| # | 阻擋項 | 為什麼阻擋 | 解法方向 |
|---|---|---|---|
| **B1** 🔴 | 圖形語言規範未定義 | 工程師會照自己直覺做，非工程師仍然看不懂 | Phase 0a：paper prototype → 非工程師測試 |
| **B2** 🟡 | 本地端 LLM 翻譯品質未驗證 | 本地模型（Ollama + Qwen3/Mistral 7B）與 API 模型的品質可能有差距，需分開建立基準 | Phase 1-min 同步驗證本地端路徑；差距過大則標注「品質較低」警示 |
| **B3** 🟠 | Diff 視圖 + 疑義升級機制設計未定義 | 沒有 diff，驗核動作無法發生；疑義若無超時 / 升級機制，會永遠停在「已標記」 | Phase 2 前定義三種觸發方式的 UX；Phase 3 前定義疑義超時升級狀態機 |
| **B4** 🟠 | 授權清單未完成 | 所有依賴需逐一確認 | 依附錄 B 清單，在 Phase 0b 前逐一確認 |
| **B5** 🔴 | Phase 0a 測試對象來源未確認 | 沒有真實非工程師測試對象，Phase 0a 無法完成 | Phase 0a 啟動前確認 3–5 位外部非工程師測試對象（PM 和非技術管理者各至少一人） |
| **B6** 🔴 | LLM 約束 prompt 設計未完成 | LLM-centric 架構下，prompt 設計是核心 IP。若約束不夠，LLM 輸出品質不可控 | Phase 1-min 啟動前完成約束 prompt 第①–⑥項；Phase 1-full 前完成第⑦–⑬項 |
| **B7** 🟠 | 一鍵模式 LLM 供應商支援範圍未定義 | 一鍵模式需要 CLI 內建 LLM 呼叫層，涵蓋多供應商 API key 管理、錯誤重試、本地模型切換，實作成本獨立且不低，若未定義範圍會讓 Phase 1-full 工作量膨脹 | Phase 1-full 啟動前定義：支援哪些 API 供應商、本地模型切換的方式（Ollama / 直接 llama.cpp）、API key 管理方式 |

**B6 LLM 約束設計清單（分階段）：**

**Phase 1-min 前必須完成（①–⑥）：**
① 輸入裁剪策略（不同層級送不同粒度的 AST 原料）
② L1 輸出 JSON schema（強制格式，jsonschema 驗證，含 relation_type 欄位）
③ L1 語言約束（禁用技術詞彙清單 + 正面範例）
④ 信心自評約束（每個節點必須附帶 confidence + reason）
⑤ 未歸類節點約束（LLM 必須列出無法歸類的節點）
⑥ 錨點約束（每個 L1 節點必須關聯至少一個 AST 節點）

**Phase 1-full 前完成（⑦–⑬）：**
⑦ 基礎設施收攏約束（提示 LLM 將基礎設施統一歸類，不拆散進 L1）
⑧ L1.5 輸出 JSON schema
⑨ L2 輸出 JSON schema + 異常識別約束
⑩ 輸出驗證規則（格式 / 覆蓋率 / 語言 / 錨點 / 關係分層五項檢查的實作規格）
⑪ 原始碼回查機制（needs_source_review 觸發條件 + 回查範圍限制 + 次數限制）
⑫ 禁止幻覺約束（禁止描述 AST 中不存在的功能；靜態關係需有 AST edge；推斷關係需標記 relation_type 和 inferred_reason）
⑬ 禁止過度解釋約束（描述粒度必須與 AST 資訊量匹配；禁止推測性語言出現在高信心節點）

---

## 10  已知風險

**根本性風險（影響工具定性）：**
- **LLM 能力邊界：** LLM 對某些 codebase（極度 legacy、混淆過的、高度 meta-programming）可能產出低品質結果。這是已知且接受的限制。緩解機制：信心自評 + 未歸類節點清單。不追求 100% 覆蓋。
- **組織權力工具化：** 工具一旦用於「核查」，就成為組織內的權力工具。工程師可能開始管理圖形的呈現而不是管理程式碼本身。緩解機制有限，使用者需自行注意組織動態。

**操作性風險（影響工具可靠性）：**
- **圖形篡改風險：** 圖形生成邏輯必須對工程師透明但不可介入。「透明」和「可介入」必須拆開設計。
- **AI 推斷飄移：** LLM 在不同時間點對同一 codebase 可能產生不同結果。緩解機制：快取機制，AST 未變化時不重新生成；使用者可手動觸發重新生成並比較兩次結果。
- **初次生成偏差：** LLM 的初次輸出可能因命名不規範或缺少 docstring 而定性偏差。緩解機制：重新生成觸發功能（見 §4.1 標記系統）；快取固化的是已被使用者接受的結果，使用者認為有偏差時可主動清除快取。
- **語意漂移無法被 label 變更偵測：** 節點 label 不變但功能範圍擴大，傳統 Diff 看不出來。緩解機制：LOG 儲存 `description` 並在 Diff 時比對，偵測到語意漂移時標記 🔵「功能說明已更新，請重新確認」（見 §12.2）。
- **LLM 幻覺：** LLM 可能虛構不存在的功能或關係。緩解機制：三重防線 — ① prompt 層禁止幻覺約束 ② 錨點檢查（每個 L1 節點必須可追溯至 AST 節點）③ 關係分層驗證（靜態關係嚴格驗 AST edge，推斷關係驗錨點存在）。
- **過度解釋：** LLM 可能為了讓輸出「看起來完整」而擴充描述超出 AST 資訊能支撐的範圍。緩解機制：prompt 層禁止過度解釋約束 + 描述粒度必須與 AST 資訊量匹配。
- **AST 結構化資訊不足：** tree-sitter 提取後可能丟失 LLM 判斷所需的上下文。緩解機制：原始碼回查路徑（needs_source_review）。
- **輸出約束被繞過：** LLM 可能不完全遵守 prompt 約束。緩解機制：輸出驗證層（jsonschema + 語意檢查 + 關係分層驗證）自動檢查，失敗時重試或標記。

**體驗性風險（影響工具採用）：**
- **動態焦慮：** 即時動態（Phase 5）可能製造焦慮而非清晰。Phase 5 最後疊加，且需要獨立 UX 設計評估。
- **LLM 回應延遲：** 大型 codebase 的拓撲引導讀取可能需要多輪 LLM 呼叫。緩解機制：每輪結果即時可見 + 快取策略。

### 10.1  降級策略

| 情境 | 降級行為 |
|---|---|
| LLM API 不可用 | 取用上一次分析成果，標示分析日期 + 分析時的檔案版本 / 清單 |
| tree-sitter 解析某檔案失敗 | 直接將該檔案原始碼送給 LLM 辨識 |
| LLM 也無法辨識某檔案 | 拒絕處理該檔案，標記 `[不支援的語言]`，不影響其他檔案的分析 |
| 輸出驗證反覆失敗 | 最多重試 2 次，仍失敗則標記 `[輸出驗證失敗]` 並顯示原始 AST 結構 |
| 拓撲引導讀取達到輪次上限 | 輸出當前結果，未歸類節點標記 `[資訊不足：未完整讀取]` |

### 10.2  使用延續性

The Door 不支援多人同時操作同一分析，但支援不同人先後使用同一分析的延續性：

- 每次分析結果（L1 + LOG + 敘事鏈 JSONL，Phase 1-full 起）儲存在本地，下次使用時可接續
- 不同使用者可以在不同時間點對同一 codebase 執行分析，各自獨立
- 若需要在前一次分析基礎上深挖，系統載入上次的敘事鏈繼續追加
- 前後分析的邏輯一致性由敘事鏈保障 — 若新的分析結果與前次不一致，系統標示差異點

---

## 11  AI-Native 開發工作流程

```
使用者（Ric）提供：  方向、判斷、驗收標準、真實情境反饋
AI 執行：            分析、設計、實作、文件、壓力測試、迭代
```

**各 Phase 工作分配：**

| Phase | AI 角色 | 使用者角色 |
|---|---|---|
| 0a | 設計顧問，產生圖形語言草案 + MD prototype + Claude artifact（含疑義路徑概念場景） | 決策者；協調 3–5 位外部非工程師測試對象 |
| 1-min | 工程師，實作 AST 結構提取 + 拓撲分析模組（含 is_entry_point 規則）+ LLM 約束 prompt（B6 第①–⑥項）+ 輸出驗證層（jsonschema + 關係分層驗證）+ MCP Server 核心兩個 tool；選取 3 份開源 codebase 跑出品質基準；量化拓撲引導 token 節省率（目標 ≥ 20%） | 測試者，確認 ground truth；驗收品質數字可量化；確認 MCP 接入體驗；確認 is_entry_point 批次分配正確 |
| 0b | 設計顧問，根據 1-min 品質數字設計信心標示視覺規範 | 驗收者，確認非工程師能區分信心標記；確認授權清單 |
| 1-full | 工程師，實作完整 LLM 翻譯引擎 + 信心標記 + API/本地端雙路徑 + 拓撲引導讀取引擎 + 敘事鏈持久化（JSONL）+ 重新生成觸發功能 + 一鍵模式 + B6 第⑦–⑬項約束 | 測試者，提供真實 code 測試；驗收品質達標；確認跨 session 接續；確認重新生成功能；確認一鍵模式可用 |
| 2 | 工程師，實作 Diff 引擎（三種觸發方式 + 三個比對維度 + 語意漂移偵測） | 驗收者，確認非工程師能獨立操作 |
| 2.5 | 工程師，整合 osv-scanner；實作漏洞 overlay + 圖形標記 + 說明欄 | 驗收者，確認非工程師能從圖形識別安全風險 |
| 3 | PM 工具設計者，實作範圍定義介面 + 疑義狀態機 + 超時升級機制 | 第一個 PM 使用者，試用並反饋 |
| 4 | 工程師，實作歷史時間軸（LOG 序列重建） | 驗收者 |
| 5 | 工程師，實作即時監聽層（獨立 UX 評估後） | 驗收者 |

**AI 工具選用：**
- 概念討論與決策：Claude（think-tank skill）
- 程式實作：Claude Code
- 程式碼審查：code-review skill
- 文件輸出：Claude（直接生成 md / docx）
- UI 設計驗證：Claude artifact（React 原型）

---

## 12  儲存策略

**設計原則：LOG 量極小（KB 級），儲存本身不是問題。真正需要設計的是三個問題：保留策略、版本對應、語意漂移追蹤。**

### 12.1  LOG 格式

```json
{
  "version_id": "string",
  "commit_hash": "string | null",
  "git_tags": ["v1.2.0"],
  "trigger": "commit | pr_merge | manual",
  "timestamp": "ISO8601",
  "l1_snapshot": {
    "feature_id": {
      "label": "string",
      "description": "string",
      "source_node_count": 0,
      "confidence": "high | medium | low"
    }
  }
}
```

LOG 記錄：功能節點清單、標籤、LLM 生成的功能描述（快取）、對應 AST 節點數、信心程度、分析涵蓋的檔案清單、時間戳記、commit hash、git tag。
LOG 不儲存：原始程式碼、LLM 輸出全文、圖形渲染結果、AST 結構原料。

`description` 欄位儲存 LLM 對該 L1 節點的功能說明。此欄位用於 Diff 時偵測語意漂移。

### 12.2  Diff 運作方式

對兩份 LOG 做 JSON 比對，輸出差異清單：

| 比對維度 | 觸發條件 | 圖形標記 |
|---|---|---|
| 節點新增 / 移除 | `l1_snapshot` 的 key 出現或消失 | 🟢 新增 / 🔴 移除 |
| 節點屬性變更 | `label` 改變 | 🟠 淺橘 |
| 依賴關係變更 | `source_node_count` 顯著改變 | 🟠 深橘（優先級高於屬性變更） |
| **語意漂移** | `description` 改變 | 🔵 藍色標注「功能說明已更新，請重新確認」 |

語意漂移的定義：節點 label 沒變，但 LLM 對該功能的描述實質改變（例如 `articles` 從「文章發布」演進為「文章發布、收藏與評論管理」）。此類變化不會觸發節點新增 / 移除標記，但代表功能範圍擴大，驗核者需要重新確認。

### 12.3  版本保留策略（三級）

```
Level 1（全保留）：最近 30 天的所有 LOG
Level 2（稀疏化）：30–90 天 → 每週保留一份（PR merge 版本優先）
Level 3（壓縮）：  90 天以上 → 只保留 git tag / release 對應的版本
手動快照：         使用者手動標記的版本，永久保留，不受自動清理影響
```

**規模估算：**
基於 flask-realworld 模擬數據（8 個 L1 節點，50 版演進），50 版累積 LOG 約 324 KB。
實際專案 50 版後預估 1–5 MB，三級保留策略後長期維持在 < 500 KB。

### 12.4  圖形快照（使用者手動觸發）

- 格式：Mermaid 文字，非圖片，儲存成本極低
- 系統不自動產生快照，快照與 LOG 分開儲存
- 快照用途：報告、簡報、email 附件；不用於 Diff 計算

---

## 附錄 A：C4 Model 對照

| C4 層 | The Door 對應 | 差異點 |
|---|---|---|
| Context | L1 功能分類圖 | C4 Context 偏技術語言；The Door L1 強制功能語言 |
| Container | L2 功能連動圖 | C4 Container 描述技術部署單元；The Door L2 描述功能模組互動 |
| Component | L3 函式呼叫圖 | C4 Component 給工程師；The Door L3 服務技術驗收者 |
| Code | L4+ 深層呼叫路徑 | C4 Code 層通常不建議繪製；The Door L4+ 按需展開 |

---

## 附錄 B：開源元件參考來源

| 參考 | 專案 | 授權 | 用途 |
|---|---|---|---|
| `[ref-1]` | tree-sitter | MIT | AST 核心解析引擎 |
| `[ref-2]` | tree-sitter-language-pack | MIT | 305+ 語言 grammar，單一套件，on-demand 下載 |
| `[ref-3]` | Mermaid.js | MIT | 圖形渲染主線 |
| `[ref-4]` | D3.js | BSD-3 | 進階互動圖形渲染 |
| `[ref-5]` | AppMap | MIT + Commons Clause | Diff 視覺化設計參考（只參考概念） |
| `[ref-6]` | Qwen3 | Apache 2.0 | 本地端 LLM 備用翻譯層 |
| `[ref-7]` | Mistral 7B | Apache 2.0 | 本地端 LLM 備用翻譯層（輕量） |
| `[ref-8]` | Ollama | MIT | 本地 LLM 部署工具 |
| `[ref-9]` | Kroki | MIT | 進階圖形渲染，25+ 格式 |
| `[ref-10]` | mermaid-live-editor | MIT | Mermaid 線上 / 本地編輯器 |
| `[ref-11]` | osv-scanner | Apache 2.0 | 漏洞掃描層 |
| `[ref-12]` | jsonschema (Python) | MIT | 輸出驗證層格式檢查，Draft 2020-12 |
| `[ref-13]` | mcp Python SDK | Apache 2.0 | MCP Server 實作 |
| `[ref-14]` | networkx | BSD-3 | 拓撲分析層，計算節點入度/出度/排名 |

---

## 附錄 C：架構決策紀錄（ADR）

### ADR-001：LLM-Centric 架構

**決策：** 所有功能識別、分類、翻譯由 LLM 執行。AST 只負責結構化原料。核心 IP 是 LLM 約束設計。

**原因：** 程式碼風格無限多樣，規則窮舉不可行；LLM 天然具備跨語言泛化能力；專案本意是「約束 LLM 如何執行」。

**取捨：** 放棄 AST 層精確分類；獲得架構簡潔性、對新語言/框架的零成本適應。接受 LLM 能力邊界即為工具能力邊界。

### ADR-002：tree-sitter-language-pack 取代逐語言安裝

**決策：** 改用 `tree-sitter-language-pack`（MIT）取代 `py-tree-sitter` + 逐語言安裝。

**原因：** 單一套件涵蓋 305+ 語言；on-demand 下載；所有 grammar 均為寬鬆授權；維護成本降為零。

**取捨：** 放棄對 grammar 版本的精確控制；獲得安裝複雜度大幅降低。

### ADR-003：jsonschema 整合輸出驗證

**決策：** 輸出驗證層格式檢查改用 `jsonschema`（MIT，Draft 2020-12）。

**原因：** 標準問題有成熟方案；支援 Draft 2020-12；失敗時提供結構化錯誤訊息方便 retry；消除手寫格式驗證的維護成本。

### ADR-004：MCP Server 形態

**決策：** 新增 MCP Server 形態，暴露兩個核心 tool：`extract_structure` 和 `validate_output`。

**原因：** MCP 是開放標準（2025-12 捐給 Linux Foundation）；所有 MCP-compatible AI 媒介零摩擦接入；MCP Server 是 CLI 功能的薄包裝，實作成本低。

**取捨：** 無（MCP Server 是 CLI 的補充，不是替代）。

### ADR-005：敘事鏈持久化（JSONL，Phase 1-full 起）

**決策：** 敘事鏈從 Phase 1-full 起改為持久化至本地 JSONL 檔案（append-only）。Phase 1-min 使用記憶體版本。

**原因：** 跨 session 接續讓「深挖」成為可能；JSONL append-only 實作成本低；Phase 1-min 先驗證拓撲引導有效性，確認後再加持久化，避免兩個變數同時測試。

**取捨：** Phase 1-min 的敘事鏈 session 結束後消失（可接受，此 Phase 目的是量化準確率，不需要跨 session 接續）。

### ADR-006：AI-Medium-Agnostic 執行架構

**決策：** 核心交付物是 CLI + MCP Server + 約束 prompt + 輸出 schema，不是 web app。

**原因：** AI 媒介生態快速演進，不應押注單一媒介；核心價值在約束設計和輸出品質；CLI + MCP Server 雙形態最大化覆蓋範圍。

**取捨：** 放棄開箱即用的精美 UI（由 AI 媒介各自實現）；獲得最大化可攜帶性。

### ADR-007：L1 ↔ L1.5 平行視角設計

**決策：** L1 和 L1.5 以平行視角（tab 或切換按鈕）呈現，不是巢狀展開。

**原因：** L1 和 L1.5 回答不同問題，不是同一問題的深淺版本；平行視角有明確的切換語意，降低認知負荷。

### ADR-008：移除工程師校正機制

**決策：** 移除工程師校正功能。The Door 輸出完全由 LLM 生成，改由使用者手動觸發重新生成。

**原因：** 校正的利益結構不對稱（工程師付出成本，驗核者獲得好處），難以激勵；工具定位是「讓疑義可見」；信心標記 + 未歸類節點清單 + 重新生成觸發功能已足夠讓使用者判斷可信度並在有偏差時處理。

**初次生成偏差緩解：** 使用者可對任何 L1 節點手動觸發重新生成，清除快取後以相同 AST 原料重新呼叫 LLM，結果標記 `[AI 推斷：重新生成，與前次不同]`。

### ADR-009：AST 拓撲引導讀取（世代四）

**決策：** 讀取策略從世代三（LLM 自由決定追加清單）升級為世代四（AST 拓撲引導，entry_point 節點 batch=1，其餘依入度排序）。

**原因：** 世代三 LLM 只能根據名稱猜測哪些檔案重要；HTTP handler 等業務入口入度天然為 0，純入度排序會讓它們落在後批次；is_entry_point 規則確保業務入口永遠優先讀到；拓撲計算純本地，無任何代價。

**批次優先序規則：**
1. `is_entry_point = true` → 一律 batch=1
2. 其餘節點依 `in_degree` 由高至低排序分配批次

**取捨：** 放棄世代三的 LLM 自由探索彈性；獲得讀取順序可預測性、業務入口保證優先、token 效率可量化。

### ADR-010：feature_relations 分層驗證

**決策：** `feature_relations` 新增 `relation_type: "static" | "inferred"` 欄位，幻覺檢查分兩層：靜態關係嚴格驗 AST edge，推斷關係只驗兩端錨點存在。

**原因：** LLM 有能力識別 AST 靜態分析無法追蹤的關係（非同步呼叫、事件驅動、IoC 注入等）。若要求所有關係均有 AST edge 對應，等於禁止 LLM 補全靜態盲點，與 LLM-Centric 架構矛盾。分層驗證保留 LLM 推斷能力的同時防止純幻覺。

**推斷關係的可信度保障：** `inferred_reason` 欄位必填（說明推斷依據，例如「函式名稱 send_email.delay 推斷為 Celery 非同步呼叫」），供使用者判斷可信度。圖形上推斷關係以虛線箭頭區分靜態實線。

---

*The Door — Product Specification v4.1 — 2026-04*
*讀取策略：世代四（AST 拓撲引導，entry_point 優先 + 入度排序）*
*架構原則：LLM-Centric + AI-Medium-Agnostic（CLI + MCP Server）*
*v4.1 修訂：① 拓撲批次規則補充 is_entry_point 優先語意 ② 幻覺檢查改為分層驗證（static/inferred）③ Phase 1-min 新增量化驗收閾值 ④ 敘事鏈持久化明確移至 Phase 1-full ⑤ 一鍵模式明確移至 Phase 1-full 並新增 B7 阻擋項 ⑥ 重新生成觸發條件補充至標記系統 ⑦ L1+L1.5 輸出時序補充說明 ⑧ B6 約束清單分兩階段 ⑨ 移除 Council-review 相關內容*
