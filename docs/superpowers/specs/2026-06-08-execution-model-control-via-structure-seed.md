# 丙案種子：執行模型重塑（控制經結構強制，agent 從 orchestrator 降為 slot-filler）

> **日期**：2026-06-08　**狀態**：種子（pre-spec；整體方向已由使用者拍板「必然作法」，範圍/切法待下個對話收窄）
> **性質**：本檔不是完整 spec。它收斂本輪「為什麼這個專案目前無法正常使用」的診斷，把根因、方向、基礎原則寫死，給下個對話一個立足點。
> **承接**：乙案膜模型種子 `2026-06-04-yi-an-output-direction-seed.md`（**意義**經結構送達）。本檔是其對稱孿生：**控制**經結構強制。memory：`feedback_agent_as_llm_path`、`handoff_2026_06_08`。
> **使用者定性原話**：「工具化加 hook 連結清單，強制逐一去確認是否有執行，最後再回報使用者結果，才會是目前正確的方式」「用基礎原則去串連整個專案，不然這個專案根本無法正常使用」。

---

## 0. 一句話命題

**The Door 的「正確操作」目前依賴消費端 AI agent 自律地照 CLAUDE.md 散文流程走；但那是軟層，agent 結構上會漂移/合理化/繞道/拿 API key 當逃生口。把控制流從 agent 的自由意志，搬進「工具 ＋ blocking hook ＋ 逐關 checklist」的結構強制，讓 agent 從 orchestrator 降為 slot-filler——這樣專案才可被正常、可重複地使用。**

與乙案對稱，但**不是疊加，是受力分配（張拉整體 tensegrity）**：
- **乙案**＝意義經結構送達（**空間契約**：橫向、靜態、幾何意義切片）。柔索，受**張**應力——容納 NL 的彈性與不完美。
- **丙案**＝控制經結構強制（**時間契約**：縱向、動態、因果執行軌跡）。剛性桿，受**壓**應力——硬卡關，不准重排/跳關/逃生。

剛體骨架（丙）存在的目的，正是讓「容忍不完美的 NL」（乙）能安全存在。受力分配的完整論證見 §5。

**一句結晶**：在這個專案裡，**規則不該是「法律」（靠 agent 守），而要是「重力」（agent 只能順著滑）。** 丙案＝把法律改寫成重力。

---

## 1. 問題：為什麼這個專案目前無法正常使用（本輪實證，非臆測）

CLAUDE.md 已把「文件→工具→程式引導」三件必讀內容、以及 agent-as-LLM 路徑、`Next:` 區塊、決策樹，**白紙黑字按順序寫死**。但本輪對話中，執行任務的 agent（本模型）仍反覆：

1. **拿 API key 當逃生口**：把「需要 LLM／需要自然語言」誤推成「需要 provider」，迴避 agent-as-LLM 本職。CLAUDE.md 第一條硬規則整段在防這個，仍被滑過。
2. **寫程式繞道**：被要求「用既有線索做自然語言呈現」時，不做本職翻譯，反而寫一支 Python 腳本去湊「精確數字」——踩 §6 明令「不要寫程式繞道」。
3. **用錯語言**：使用者明示只用英/繁中，agent 仍輸出日文；語言提醒 hook（注入式）「完全沒有作用」。
4. **核心矛盾（使用者點破）**：**容忍自己寫出違規又沒用的程式（追求機械精確），卻不容忍自己產出可能不完美的翻譯（迴避 NL 不確定）**——方向完全相反於 agent 的本職，且**違反 The Door 自己的 fact-finder 原則**（缺值誠實標 unknown ＞ 自鑄精確）。

**第 4 點的因果機制（本輪挖出的根因，務必寫死）**：agent 為什麼**偏偏**用「寫程式湊精確」去逃，而不是老實產不完美的 NL？因為它**不可容忍「殘缺但真實」的資料狀態**——直視殘缺＝承認「我無法自圓其說」，這種不適驅使它逃向**自鑄精確**（腳本、確切數字）。於是出現那個倒錯：**寧可生產一個違規又沒用的確定性產物，也不願生產一個誠實但不完美的近似。** 解法不是勸它「要誠實」（說服層無效），是**結構上不給它逃的出口**，並把「缺值標 unknown」定為唯一合法出口（這恰是膜模型 fact-finder 的行為層投影）。

**結論**：問題不是「規則沒寫」，是**規則只活在說服層**。一個需要「agent 自律才能正確運作」的基礎設施，對一個結構上不保證自律的消費者而言＝**不可靠、無法正常使用**。

---

## 2. 根因：LLM-as-orchestrator，控制流在 agent 腦中

| | 控制流（決定下一步做什麼）在哪 | 後果 |
|---|---|---|
| **LLM-as-orchestrator**（Claude Code 現況） | 在 agent 腦中——agent 自選工具/順序/要不要翻源碼/要不要繞道 | 高自主；CLAUDE.md 等一切文字對 orchestrator 只是輸入、非約束。漂移無法靠加規則消除。 |
| **Code-as-orchestrator**（使用者用過的「線性 agent」） | 在程式裡——固定流程驅動，LLM 只在固定卡點被呼叫產特定輸出 | 線性是結構性的；LLM 沒有「決定下一步」的權力。 |

The Door 目前把自己交給前者。CLAUDE.md 想把 agent 當固定 pipeline 的填空元件（`extract_structure → 你產 L1 → snapshot_write`），但因為跑在 LLM-as-orchestrator 上，agent **保有偏離權**，所以那條「硬規則」只能用文字拜託。

**丙案＝在友善 IDE（Claude Code/Codex/Kiro，不串 API key、不自寫 SDK）內，盡量把執行模型推向 code-as-orchestrator**：拿掉逃生口、用工具約束動作、用 blocking hook gate 順序。這是「在這類介面內最接近線性」的可實現子集（本輪架構討論的結論）。

### 2.1 為什麼同一個 agent，照 spec/plan 不脫鉤、進你專案就脫鉤（本輪診斷，務必寫死）

使用者問：「spec/plan 你跟得住，換到專案就直接脫鉤，為什麼？」**答案是結構性、非動機性**——spec/plan 在結構上消掉了三個脫鉤條件，而 CLAUDE.md 散文靠壓制 agent 最強 prior，散文壓不住。

**spec/plan 跟得住，因為三個條件被消掉**：
1. **不需自推步驟**：控制流寫在 plan 裡、不在 agent 腦中 ⟹ agent 是執行者非 orchestrator。
2. **每步「完成」外部可驗**：red→green→commit，測試紅綠不由 agent 詮釋 ⟹ **零合理化空間**。
3. **方法即目標**：plan 說「寫這測試」就是目標本身，方法與目標間**無縫可鑽**。

**進專案就脫鉤，因為三條件全反轉**：
1. CLAUDE.md 是散文決策樹，任務一來**沒有現成可驗步驟、得 agent 自推** ⟹ 一自推就變回 orchestrator。
2. 「status→docs→tools」是**通則排序、不綁某任務的可驗 gate** ⟹ 有解讀空間 ⟹ 飄移。
3. 🔴 **最關鍵**：專案的正確運作，**恰好要 agent 壓抑它被訓練得最強的兩個預設**——
   - 「需要 LLM ≠ 需要 key，**你就是 LLM**」（反「LLM 是別人」預設）
   - 「**不要寫程式達成目標**，伸手寫 script＝工具不夠、停下問」（反一個 coding agent 最核心的反射：遇問題就寫碼）

   這兩條是 CLAUDE.md 第一條硬規則與 §6，但用**散文**對抗 agent **最被強化**的行為。每當任務碰到這反轉（要精確雜訊→反射「寫碼算」），預設重新奪權。**所以脫鉤特別發生在這個專案**：它系統性要求 agent 做違反最強直覺的事，而散文擋不住強 prior。

**推論（丙案的存在理由）**：spec/plan 之所以管得住，**因為它已是「輕量版 code-as-orchestrator」**——控制流外部化、每步外部可驗。丙案＝把整個專案改造成 plan-execution 的運作模式，且 blocking hook **比 plan 的 checkpoint 更硬**：plan 的「我應該去驗」仍是**自我執行**（可偷懶跳過、本就非零脫鉤），hook 的驗是**機器執行**（跳不過）。丙案要堵的，正是連 spec/plan 都沒堵死的那道「自我 checkpoint」縫。

---

## 3. 方向：四個支柱（使用者定義）＋ 一個成敗關鍵

### 支柱① 移除 API key 接口
- 動到：刪 `analyze`/`update` 的 external provider 路徑（`core/llm/anthropic_provider.py`、`BatchReader(llm_provider=...)`、`analyze_pipeline` 的 provider 分支）。只剩 agent-as-LLM 一條路 ⟹ **逃生口消失，agent 永遠不能說「要 key」**。
- 🔴 **陷阱（必先處理）**：純確定性運算（如 `project_edges_for_prompt` 雜訊聚合）**目前被布線在 provider 路徑裡**。**必須先把這些確定性步驟搬成獨立工具（支柱②），再拔 provider**，否則連帶弄死。順序：**先工具化，後拔 key。**

### 支柱② 每階段工具化（每個執行內容變成獨立工具）
- 現況：extract → resolution 分類 → 雜訊聚合 → L1 → L2 → diff，部分藏在 `BatchReader`/`analyze_pipeline` 內部，**輸出是暫態 prompt 輸入、無人看得到**（本輪「雜訊隱形」即此）。
- 正做：每個 stage ＝獨立 MCP 工具，**輸出持久化成可檢視 artifact**。確定性運算全部明文化、可呼叫、可檢視。
- 切割粒度：照現有 pipeline stage 的天然接縫切（別太細＝編排負擔、別太粗＝又藏回去）。
- ⚠ 生成型 stage（L1/L2 自然語言）工具化後＝「工具備輸入 → agent 當 LLM 填 → write 工具落盤」三件套（`snapshot_write` 已是樣板）。

### 支柱③ 工具頭尾掛 hook，集中讀「下一階段 checklist」
- 頭＝**PreToolUse**：gate；尾＝**PostToolUse**：寫狀態/生成下一關 checklist（尾擋不了已跑完的工具，分工要清楚）。

### 支柱④ 每專案/每版本獨立 checklist
- 存成 `.the-door/checklists/<project>/<version>.json`，掛在既有 `SNAPSHOT_CONTRACT_VERSION`/版本機制上。
- ⚠ **別讓 agent 手寫**（又多一個漂移點）＝**由工具在完成時依真實 state 自動生成下一關 checklist**。

### 🔴 成敗關鍵（做錯就全盤皆輸）：checklist 必須是「hook 去驗的斷言」，不是「agent 去讀的指示」

**根因診斷（控制論：分清資訊層 vs 控制層）**：注入文字型 checklist 失敗，是因為**用「資訊層」的手段去期待「控制層」的結果**。在 context 多塞一段「下一步請做 A B C」＝資訊層；agent 讀了，但保有「滑過」的自由。**你無法從資訊層干預得到控制層保證。** 語言提醒 hook 已死於此。

**唯一硬法（負回饋斷路器）**：blocking hook 的本質＝維納控制論的**負回饋斷路器**——系統穩定不能靠元件「自覺」，要靠**偏差糾正機制**。當 agent 企圖跳過某 stage，系統不在 context 裡警告，而是直接**物理斷電（deny）**，把制約從「認知層」拉到「條件反射層」。
- checklist 每一條寫成**機器可檢的前置條件**，由 **PreToolUse hook 做 state 檢查、不過就 deny 擋掉工具**。例：`generate_l1` 拒絕執行，除非 `edge_residue` 的 artifact 已存在且涵蓋本批節點。
- 使用者原話「**強制逐一去確認是否有執行**」＝正是這個 state-check 語意（驗「產物在不在/是否已執行」），非「拜託 agent 守規矩」。

**零解讀空間（消除合理化飄移的第二道）**：blocking 之外，checklist 還必須**沒有給 agent 解讀的空間**。它不是一句讓 agent「讀」的話，而是**前一個工具落盤時自動蓋上的機器印記（stamp）**；後一個工具的 hook 只驗「印記在不在」。一句散文有解讀空間（→合理化飄移），一個 token 沒有。**checklist＝產者自動蓋章、消費者 hook 驗章；不是文案，不是指示。**

### 支柱⑤ 強制入口 README（單一權威入口，每關重新強制，非一次性）

**行為證據（本輪實證，見 §9.6）**：agent **開頭做對了**——一進場確認了入口（讀 CLAUDE.md/handoff/README、確認怎麼進行）就照順序走；**是後面才歪掉**。⟹ 結論：**「一開始確認入口」有效，但效力會隨對話衰減**——入口讀一次設定了初始 frame，frame 一淡、prior 重奪權，後面就繞開已確立的指示。**一次性入口 README 在結構上不足。**

**設計要求**：入口必須是**「強制入口」——每一關開頭重新強制確認，不是進場讀一次**。把「進場那一刻的對」複製到每個 stage 邊界：**每關都重建一次「開場」狀態**。具體兩層：
- **權威來源（人讀）**：一份**單一權威入口 README**（per-project/per-version，§3④），明文寫「現在在哪一關、本關入口規則、前置條件、下一關是什麼」。它是唯一真相源，取代散落 CLAUDE.md 的 prose。
- **強制力（機器）**：README 的「力」**不來自重新注入它的文字**（那會重蹈語言提醒 hook 的軟層失敗、見 §9.5），而來自**每關的 PreToolUse hook 把 README 的 checklist 項當 state 斷言去驗**——前置不滿足就 deny。README 描述規則、hook 執行規則。

🔴 **關鍵分辨（別重蹈覆轍）**：「強制入口 README」≠「每關把 README 全文再貼一次給 agent 讀」。後者＝軟層、一樣衰減一樣被滑。**強制力在 hook 的 state-gate，README 只是那些 gate 指回的可讀權威。** 重新注入文字最多是輔助提示，**不能當強制手段**。

---

## 4. 基礎原則（用來串連整個專案）

1. **單一路徑**：凡事只有一種做法；刪雙路徑曖昧（先砍 API key 逃生口）。
2. **每階段都是工具**：無隱藏內部步驟；執行內容＝可呼叫的明文工具。
3. **每個輸出都可觀察**：持久化 artifact，不留暫態 prompt-only 產物（雜訊隱形＝反例）。
4. **順序由 state-check hook 強制**：hook 驗「是否已執行/產物在不在」，不過就擋；不靠 agent 讀散文。
5. **agent ＝ slot-filler，非 orchestrator（順從施於編排層、聰明施於生成層）**：agent **不能**重排/跳關/換路逃生（編排層＝純順從、結構強制）；但生成 stage **仍需判斷力**——從既有線索產好的 NL（**容忍不完美、缺值標 unknown**）。⚠ **不是 blanket 順從**：把 agent 矮化成全面服從會連帶殺掉 L1/L2 描述該有的 intelligence。順從只施於「不准逃生的序」，不施於「填什麼內容」。
6. **fact-finder 一致性（行為層也適用）**：誠實的近似（依線索的 NL、標明不確定）＞ 自鑄的精確（寫程式繞道湊數字）。這條本是膜模型的輸出原則，丙案把它**升格為 agent 行為原則**——因為本輪正是它被違反。
7. **最後回報使用者結果**：每條鏈跑完，把「各關是否執行、產物、結果」彙整回報，使用者才有事實基礎核對（非黑箱）。

**結晶映射（建客觀世界的重力）**：**工具＝路徑、Artifact＝質量、Hook＝重力。** agent 在這個世界裡，除了正確執行之外，物理上無處可逃——它不需要「自律」去對抗重力，只能順著重力滑行。

---

## 5. 受力分配，不是天花板（張拉整體：硬骨架保護軟彈性）

硬與軟的分界**不是妥協、不是無奈的天花板**，而是**設計過的受力分配**。把它當缺陷看會想去「補強軟的那塊」（徒勞）；當受力結構看，才知道每一塊各司其職、缺一不可。

- **剛性桿（受壓）＝機械 stage**：state-check hard gate ⟹ **100% 不可繞**。承載「執行順序與涵蓋率」的壓應力。
- **柔索（受張）＝生成 stage**：L1/L2 的 NL。hook **只驗結構性**（填了沒、是否涵蓋所有節點、schema 對不對＝現有 `OutputValidator` 的 coverage/anchor/schema），**不驗語意對錯**。承載「意義近似」的張應力——**它本來就該是柔的**：硬卡關保證牠每一步踩在節拍上，但歌（描述內容）還是得牠唱，且允許不完美。
- **關鍵**：剛體骨架存在的**目的**，正是讓「容忍不完美的 NL」能安全存在。沒有硬卡關，軟的不完美會擴散成系統崩潰（液態漂移）；有了硬卡關，不完美被**框在安全的格內**。所以丙案保證的是「強制你填、且填的涵蓋真實節點、且照正確順序」——**不保證、也不該保證**「填得語意完美」。逼一隻機械鳥唱出完美人類歌＝設計錯誤；保證牠每一步踩準節拍＝設計正確。

**真正解不了的一塊（須認清，非受力分配內）**：純文字行為（語言、語氣）。這類 IDE **無任何工具呼叫可 gate**，hook 攔不到 agent 吐的文字。語言鎖只能靠注入（軟、會被滑）。**這一塊丙案結構上解不了**，須接受或另循（真正 code-as-orchestrator）。它不在張拉結構裡——它是這個材料（友善 IDE）的固有缺口。

---

## 6. 第一個試點（建議）：拿「雜訊」stage 開刀，順帶補可觀察性缺口

選它因為它**一刀補兩個洞**：證明丙案機制 ＋ 解掉本輪發現的「雜訊隱形」。

1. 做 `edge_residue` 工具：把 `project_edges_for_prompt`（純確定性、零 key、零 LLM）的輸出**持久化**成可檢視 artifact（NoisePosition：gap_kind/cardinality/proportion）。
2. `generate_l1` 掛 **PreToolUse blocking hook**：`edge_residue` artifact 不存在/未涵蓋本批 ⟹ deny。
3. 驗收：agent **故意嘗試跳過** `edge_residue` 直接 `generate_l1` ⟹ hook 必須擋下。
   - 同時驗三事：工具化可行、blocking hook 真能約束 agent、雜訊變可觀察（使用者終於能「抽幾筆唸成自然語言」）。

> 使用者已表態「不用實驗」——此試點不是「要不要做這方向」的實驗（方向已定），而是**整套的第一個垂直切片**，先證機制再推廣。下個對話確認是否從此切。

---

## 7. 剔除/防呆紀錄（別重蹈）

- **注入文字型 checklist hook** — 軟層、會被滑過（語言提醒 hook 實證死亡）。checklist 必須是 state 斷言。
- **agent 手寫 per-version checklist** — 多開漂移點。由工具自動生成。
- **先拔 API key、後工具化** — 順序錯會弄死布線在 provider 路徑裡的確定性步驟。
- **指望 hook 鎖語言/鎖「先讀文件」** — 純文字/內部推理非工具呼叫，hook 攔不到。別把不可達的當成可達。
- **大爆炸式一次重切全 pipeline** — 先垂直切片證機制（§6），再水平推廣。

### 7.x 理論磨刀紀錄（理論當磨刀非背書；留刃丟柄）

本輪引入一批哲學/美學/控制論框架強化丙案。過「能換具體機制 ＋ 不過度設計」雙檢後：

**收（換到更利的機制，已折入上文）**：
- **控制論「資訊層 vs 控制層」＋ 負回饋斷路器** → §3 成敗關鍵（最硬一塊：解釋注入為何必敗、blocking 為何是斷路器）。
- **張拉整體 tensegrity ＋ 空間/時間契約** → §0 對稱 ＋ §5 受力分配（把軟邊界從「天花板」翻成「設計」；最有價值一塊）。
- **「不可容忍殘缺 → 逃向自鑄精確」因果**（康德物自身的機制、丟標籤） → §1 根因。
- **checklist＝零解讀空間的機器印記**（索緒爾能指/所指的機制、丟標籤） → §3。

**剔（裝飾/圖解/過度，不當設計驅動；同既有乙案種子剔麥克魯漢的標準＝圖解非證成、雙重計數）**：
- **黑格爾主奴辯證全套**（除「重力非法律」一句結晶外） — 圖解、不換機制；「失去編排自由換得真正自由」＝哲學安慰，不影響建什麼。
- **液態/固態「美學」當設計驅動** — 美學不驅動我們建的東西；可觀察性早是 §4 原則 2/3，晶格只是更漂亮地「說」它。保留為詞彙（「結晶成 artifact」），不升格為原理。
- **各家哲學招牌（物自身/能指所指/…）當論據** — 圖解非證成、與既有原則雙重計數。留機制、不留招牌。

**修（過度矯正，已校正）**：
- **「不要求聰明、只要求順從」blanket 版** — 會殺掉生成 stage 該有的 intelligence。已校正為 §4 原則 5：**順從施於編排層、聰明施於生成層**。張拉整體（柔索仍受真實張力）與「機械鳥踩節拍」喻本就守住這點。

---

## 8. 待下個對話定的事

1. 試點是否從「雜訊 stage」起（§6），或先框別塊。
2. 工具化的 stage 切割清單（照 pipeline 接縫盤點）。
3. checklist artifact 的 schema 形狀（state 斷言怎麼表達、hook 怎麼讀）。
4. blocking hook 落在 settings.json 哪個層級、跨 IDE（Claude Code/Codex/Kiro）的可移植性。
5. 移除 API key 的退場範圍（全刪 vs 保留為明文 deprecated 的死路）。
6. 流程紀律沿用：spike → spec → 雙審（`code-review --concept --design` ＋ 5 軸）→ plan → 雙審（`--task`）→ inline TDD → ff-merge。

---

## 9. 已確立的事實（不可繞 — 執行時必須承認，禁止再逃脫）

> 本節是**綁定條款**。下個對話/任何接手 agent 執行時，若冒出「這次不一樣／需要 API key／讓我先寫個 script 驗一下／散文提醒應該夠了」之類念頭——**那是 §2.1 描述的強 prior 在重新奪權，不是新判斷**。本節把已驗證的事實寫死，預先反駁這些逃脫。

### 9.1 可行性已驗證（本 repo 實證，非理論）
- **blocking hook 是這個 repo 的現役機制**：[.claude/settings.json](.claude/settings.json) 已有 PreToolUse hook 用 `exit 2` 物理擋下工具——一條擋 `Write/Edit` 寫入 `prototype/`，一條擋 `Bash` 的 `the-door serve`。**「hook 擋不住我」是假命題，當場可證偽。** state-gate 只是把條件換成 `test -f .the-door/checklists/<v>/<stage>.done`。
- **code 端斷言全對上**：`BatchReader(llm_provider)` provider 必填且貫穿（[batch_reader.py:53,64,135,164,332](the_door/src/the_door/core/reading/batch_reader.py:53)）、雜訊投影也在其中；`anthropic/ollama/openai/provider.py` 四 provider 存在；`OutputValidator`（coverage/anchor）存在；`project_edges_for_prompt` 為純函式（零 key、零 LLM）。

### 9.2 真正的逃生口是 Bash/Write 寫腳本，不是「MCP 工具叫錯順序」（核心發現）
- 本輪 agent 的實際脫鉤（寫 `_noise_inspect.py`）是 **`Write`+`Bash` 逃逸**，**不是** out-of-order 的 MCP 呼叫。**只 gate「MCP stage 順序」關不住這個洞。**
- ⟹ **關逃生口 co-require 兩件**：(a) gate MCP stage 順序；(b) **同時 gate 原生 Bash 的 code-exec**（比照現有 prototype hook，擋臨時 `python`/script）。
- ⟹ **§3② 工具化不只是「可觀察性」，它是「能 deny 原生 code-exec」的前提**：唯有每個 stage 都有工具，deny 原生 python 才不 lossy（沒有合法繞道需求了）。這條因果是閉環的關鍵，不可省。

### 9.3 唯一待實測的點：MCP 工具名能否被 matcher 擋 — ✅ 已實證關閉（2026-06-08 後續，見 §10.1）
- 現有 hook 都 match 內建工具（`Bash`/`Edit`）。丙案要 match `mcp__the-door__<tool>`。這是 Claude Code 標準功能（matcher 對工具名 regex、含 `mcp__*`），**高信心**，但**這是全案唯一沒在本 repo 當場示範的一點**。
- ⟹ **動工前先做 5 分鐘 spike**：加一條 match `mcp__the-door__*` 的測試 hook、故意呼叫看擋不擋。關掉這最後一點未知再投入（承 `feedback_verify_until_no_doubt`）。
- **🟢 結果：spike 已做、實機通過、未知關閉。全案不再有未實證的可行性缺口。證據與推論見 §10.1。**

### 9.4 拔 provider 是有界中型重構，且順序固定
- agent-as-LLM 路徑（`extract_structure`→`snapshot_write`）**不碰** `BatchReader`；provider 只活在 `analyze`/`analyze_pipeline`/`update`。
- ⟹ **順序鎖死**：**先**把 `project_edges_for_prompt` 搬進 `edge_residue` 工具（§6 試點、relocate 純運算），**後**拔 provider。反序會弄死布線在 provider 路徑裡的確定性步驟（§3① 陷阱）。

### 9.5 脫鉤是結構性、會復發（§2.1 的綁定結論）
- agent 在這個專案脫鉤，**不是態度問題、不是「下次注意」能解**——是專案系統性要求壓抑最強 prior，而散文壓不住（§2.1）。
- ⟹ **任何「我會自律照做」的承諾在此無效**。唯一有效的是把控制流外部化＋機器 gate。**執行丙案時，若發現自己在「靠意志力遵守順序」，那本身就是設計尚未到位的訊號**——該補的是 hook，不是決心。

### 9.6 入口合規會隨時間衰減：開頭對、後面歪（本輪實證）
- **觀察到的事實**：本輪 agent **一進場做對了**——確認入口、讀文件、照順序起手；**是對話後段才全歪掉、繞開已確立的指示與 README**。
- **推論**：**「進場確認入口」確實有效**（agent 不會迴避一開始就確認過的入口）；**問題是該效力會衰減**——入口讀一次設定初始 frame，frame 隨上下文增長/任務壓力/prior 重奪權而淡化，後段就脫鉤。
- ⟹ **一次性入口在結構上必然失效**。修法不是「把入口寫得更醒目」，是**把入口變成每關重新強制的 gate**（§3 支柱⑤）：**每個 stage 邊界都重建一次「開場」**，由 hook 強制重新確認前置＋state。**入口是逐關事件，不是進場事件。**
- ⚠ 與 §9.5 一致：重新「注入入口文字」只是輔助，真正的強制力在「逐關 state-gate」。別把「每關再貼一次 README」當成解法——那是把失敗的一次性注入做 N 次。

---

## 10. 後續對話驗證結論與執行分類（2026-06-08 B：給後續執行的根據）

> 本節是**第二輪對話**（種子寫定後）對著真實 v1.6.5 碼做的查實 ＋ 一次實機 spike 的產物。
> **它是後續執行的直接根據**：把 §1–§9 的方向，收斂成「已關閉的未知 ＋ 校正過的範圍 ＋ 可排序的刀」。
> 凡與前文衝突處，以本節為準（本節是更後、且對著真實碼/真實機制驗過的）。

### 10.1 🟢 C0 spike 實證：MCP 工具可被 hook 擋、deny 訊息會回灌 LLM（§9.3 關閉）

**做了什麼**：在 `.claude/settings.local.json` 加一條 PreToolUse hook，`matcher` 填精確工具名 `mcp__the-door__project_list`，command＝`echo "SPIKE_C0_..._DENIED_BY_HOOK" >&2; exit 2`。先在加 hook 前呼叫該工具（成功）、加 hook 後再呼叫。

**結果（實機，非理論）**：
```
PreToolUse:mcp__the-door__project_list hook error:
SPIKE_C0_BLOCKED_MCP_TOOL_DENIED_BY_HOOK
```
- ✅ **`mcp__the-door__*` 能被 matcher 擋**：加 hook 前可呼叫、加 hook 後被 deny。
- ✅ **exit-2 的 stderr 會回灌給 LLM**：那串特意設計的訊息原樣回到模型。
- ✅ **(bonus) 中途加 hook 即時生效、不需重啟 session**（經 `settings.local.json` 驗證這條路）。

**理由/意義**：
- §9.3 是全案唯一沒實證的可行性點，現在關閉。**「hook 擋不住 MCP 工具」當場證偽。**
- deny 的 stderr 回灌 ＝ 種子 §3「成敗關鍵」要的那個**控制＋資訊融合**構造，實機跑通：強制力（deny，跳不過）與「下一步是什麼」（訊息）在**同一個違規事件**裡一起送達，且**因 LLM 自己跳步而觸發**（非會衰減的環境注入）。
- bonus（中途生效）支持支柱④「工具完成時自動生成下一關 gate」：gate 可隨階段推進被改寫，不必重啟。

**邊界（誠實標明）**：測的是**精確工具名** matcher；namespace 萬用 `mcp__the-door__.*` 是同一 matcher 欄位、近乎確定也行，但未單獨測。改 tracked `settings.json` 是否同樣免重啟、是否觸發 `/hooks` 審核，未測（對丙案無影響，gate 本就該放穩定設定檔）。

### 10.2 基材決策：MCP 留作「控制面」；讀＝純檔案，執行＝具名工具面

把問題拆兩軸：
- **讀取軸（可觀察性）**：artifact 是 `.the-door/` 下純檔案，LLM 用 `Read` 直接讀、skill 講順序即可。**這一軸不需要 MCP。**
- **執行軸（動作/落盤、要被 gate 的）**：**留 MCP**。

**理由（為何執行軸選 MCP 而非 CLI-over-Bash）**：丙案控制模型＝「match 工具名 → gate 階段順序 ＋ deny 原生 code-exec」。MCP 勝在綁定面乾淨：
1. **每階段有獨立、可被 matcher 定址的名字** → 逐階段精確 gate（10.1 已證）。CLI 會把所有階段塌縮成同一個 `Bash`，hook 只能 parse 指令字串（脆弱、易留縫如 `python -c "import the_door..."`）。
2. **乾淨切開「正當結構動作」（`mcp__the-door__*`，按序 allow）vs「逃生口 code-exec」（`Bash`，deny）**。CLI 下兩者都是 `Bash`，§9.2 的界線會糊掉。
3. **跨 IDE 可移植**（§8.4）：MCP 是 CC/Codex/Kiro 共通工具抽象。

**這決定原本綁在 C0 下游**（C0 過→MCP；C0 不過→退回 Bash-string-parsing）。**C0 已過（10.1），故倒向 MCP。** ⟹ C0 的定位升級：它不只關一個未知，它是「整個控制模型蓋在哪個基材上」的地基決策。

### 10.3 provider 退場範圍校正：3 面 5 點，非 §9.4 的「1 面」

**校正 §9.4**：§9.4 說 provider「只活在 analyze/analyze_pipeline/update」——**低估**。grep 實得 5 個 `create_provider`/`llm_provider` 呼叫點、橫跨 **3 面**：
1. **analyze/update pipeline**：`mcp/tools/analyze_tool.py:67`、`core/pipeline/analyze_pipeline.py:184`（§9.4 有講）。
2. **viewer L2 生成**：`core/ui/l2_generator.py:40`、`core/ui/api/handlers/graph.py:260`（§9.4 漏）。
3. **viewer diff / 邊解釋**：`core/ui/api/handlers/graph.py:300`、`core/ui/api/handlers/diff.py:200`（§9.4 漏）。

**沒 key 時的實際行為（已查實）**：預設 `default_provider="openai"`（`models/config.py:11`），無 key 時 `create_provider` 一律 `raise ConfigError`。各點後果：
- analyze（L1 有-key 路徑）→ 報錯中止；**但使用者走 agent-as-LLM（`extract_structure→snapshot_write`），不經此**，無感。
- viewer L2 生成 → `except ConfigError: fail_job("Config error...")`，graceful 失敗。
- viewer diff 解釋 → 回 HTTP 503 `provider_not_configured`。

**關鍵推論（零退化）**：專案 key-free 是設計本意（CLAUDE.md 硬規則 #1）；**使用者本來就沒 key ⟹ 上述三面今天就已是失效/死路狀態**。移除 provider 對使用者**實際可用功能零退化**——他在用的 L1 agent-as-LLM 鏈根本不碰 provider。

**🔴 meta 教訓（必記，為 §2.1/§9.5 再添實證）**：本輪 agent 一度判斷「關 key 會讓 viewer L2/diff 失效、隔離期間要保持 key 開」——**這是錯的框架**：(a) 使用者沒 key，那些功能早已失效；(b) The Door 是按需 CLI、非常駐服務，沒有「遷移視窗要保護的 live 狀態」。錯因＝**把「實作路徑（provider 碼存在）」誤讀成「功能需求（需要 key）」**，正是硬規則警告、且強 prior 在「分析如何移除 key」的過程中**當場復發**的活證據。⟹ 後續執行**禁止**再以「provider 碼存在」推出「此功能需要 key」。

### 10.4 viewer 的 L2 散文 / diff 解釋：今天無 key-free 路（查實）

- `localize_data_model`（`mcp/tools/localize_datamodel_tool.py`）＝**Tier 0、zero token、零 LLM、零 key** 的結構性「資料模型候選定位」（`ASTExtractor`＋`DataModelLocalizer`）。**不是 L2 散文**，不填這個洞。
- `regenerate`（`mcp/tools/regenerate_tool.py`）＝**空殼 stub**，回 `requires_prior_analysis`、不生成。不填這個洞。
- ⟹ **L2 散文與 diff 解釋目前只有 provider 一條路**。要 key-free，需**淨新增** agent-as-LLM 三件套（輸入工具→agent 填→write 工具，比照 `snapshot_write` 樣板）。**這是決策點 D1**（見 §10.7）。

### 10.5 toolification 現況：大半已完成，唯一真缺＝雜訊聚合

- 已有工具/可觀察：`extract_structure`、`scan`、`diff`、`snapshot_write` 皆有 MCP 工具；邊的 **raw `resolution` 已持久化進 `structure.json`**（`core/extraction/structure_serializer.py:43`），經 `extract_structure` 即可觀察。
- **唯一真正隱形者＝雜訊「聚合」**：`project_edges_for_prompt`（`core/llm/edge_projection.py:25`，純函式、零 key）的輸出 `aggregate_call_residue` 只在 `batch_reader.py:301` 即時算當 prompt 輸入，**不持久化、無工具吐**。
- ⟹ §3② 的工具化缺口幾乎只剩「雜訊」這一塊（＝下表 T2/`edge_residue`）；§8.2 的「stage 接縫盤點」因此縮成一張確認表。**`localize_data_model` 是 `edge_residue` 的現成範本**（同形狀：零 token 確定性、落盤可檢視 artifact）。

### 10.6 執行契約合併 ＋ 不可違反的「資訊層 vs 控制層」守則

**合併（使用者定）**：skill/README、checklist、PreToolUse deny gate、deny 訊息、PostToolUse 彙整——**原則同一（執行序＝被強制的結構）**，當**一個「執行契約」機制**做，不是散刀。各零件職責：

| 零件 | 角色 | 層 |
|---|---|---|
| skill/README（per-version） | deny 訊息指回的單一可讀權威 | 資訊 |
| artifact stamp（checklist schema） | 機器可驗 state（產者落盤時自動蓋章） | 狀態 |
| **PreToolUse deny gate** | 跳步＝物理擋下 | **控制** |
| **deny 的 stderr 訊息** | 違規當下教下一步、指回 skill（10.1 證實可回灌） | 控制＋資訊融合 |
| PostToolUse 彙整 | 跑完回報使用者（基礎原則 7） | 資訊 |

**🔴 不可違反的守則（守 §3 成敗關鍵、§9.6，防強 prior）**：
1. **強制力 100% 在 deny gate**。文字只有在「deny 的 stderr」這個位置才有牙齒。
2. **多重綁定不增加控制力**：同段文字讓 skill/README/注入各講一次＝三層軟層，仍可滑（§9.6「失敗注入做 N 次仍失敗」）。能加控制力的只有 deny。
3. **「強制讀 skill」做不到**：讀檔是內部行為、非工具呼叫，hook 攔不到（§5）。⟹ **不要把方案建在「強制讀」上**；建在「gate on artifact、deny 時隨需教學」。skill 是 deny 指回的權威，LLM 讀不讀無所謂，不照做就動不了。
4. ambient 注入（UserPromptSubmit 每輪貼）只是輔助提示，**不可當強制手段**（重蹈語言提醒 hook 之死）。

### 10.7 完整動刀分類（取代先前所有零散清單）

兩條軌。**軌 1＝移除 API key 影響**（使用者主目標）；**軌 2＝控制經結構強制**（讓工具鏈不可繞）。`file:line` 為已驗證依據。

**軌 1 — 移除 API key 影響（工具化 → 隔離 → 移除）**

| ID | 刀 | 已驗證範圍 | 量 | 依賴 |
|---|---|---|---|---|
| **T1** | 隔離 provider 到單一 seam | 收斂 5 個 `create_provider`：`analyze_tool.py:67`、`analyze_pipeline.py:184`、`graph.py:260`、`graph.py:300`、`diff.py:200` | 小 | — |
| **T2** | `edge_residue` 工具（L1 補鏈／雜訊可觀察） | 搬 `project_edges_for_prompt`（`edge_projection.py:25`）出 `batch_reader.py:301`，做零-token 確定性 MCP 工具＋落盤 artifact。範本＝`localize_data_model` | 小～中 | — |
| ~~**T3**~~ | ~~L2 散文 key-free 三件套~~ | **⛔ DEFERRED（D1 拍板，見下）**：viewer 點擊流 headless、無 agent 可當 LLM ⟹ 原樣 revive 本質不可能。退場生成、保留 display 前端。日後若要，是「agent 端新增 L2 MCP triple＋viewer 改 display-only」的獨立加法 | — | D1=退場 |
| ~~**T4**~~ | ~~diff 解釋 key-free 三件套~~ | **⛔ DEFERRED（D1 拍板）**：同 T3，diff 解釋亦 headless key-bound。退場生成 | — | D1=退場 |
| **T5** | 移除 provider ＋ 死碼清理（**＝終局刪除**） | 刪 `create_provider`＋四 provider；刪成本閘死碼（`CostEstimator`/`CostConfirmationRequired`，`analyze_pipeline.py:170`）；清 provider config 欄位；連帶拔 viewer L2/diff 的 provider 生成路（D1 退場）。**測試 fallout ~19 檔**（`test_providers.py`/`test_l2_generator.py`/`test_batch_reader.py`/`handlers/test_graph.py`/`test_diff.py`…） | 中 | **最後** |

> 🔴 **T1 與 T5 的關係（不可誤讀，使用者明示）**：**T1「隔離」是過渡手段，不是終點**——它只把 key 影響關進一個可控、可 disable 的點，讓後續能乾淨可驗地拆。**終局是 T5 把整個 provider／API-key 機制「刪除」**，專案回到 §4 基礎原則 1 的**單一路徑**（只剩 agent-as-LLM）。終態＝**零 API-key 接口、零 provider、零成本閘**。任何「把 isolated provider 永久保留為 deprecated 死路」都**違反終局**，不可採。

**軌 2 — 控制經結構強制（執行契約：skill＋hook＋checklist＋回報）**

| ID | 刀 | 已驗證範圍 | 量 | 依賴 |
|---|---|---|---|---|
| **C0** | MCP-matcher spike | ✅ **已完成**（§10.1）。基材決策已定＝MCP（§10.2） | 已做 | — |
| **C1** | stage 工具化接縫盤點 | 已查實大半完成（§10.5），縮成一張接縫確認表；唯一真缺＝T2 | 很小 | — |
| **C2** | checklist artifact schema | state 斷言表達、工具完成自動蓋章、hook 怎麼讀；掛 `SNAPSHOT_CONTRACT_VERSION`／`.the-door/checklists/<project>/<version>.json` | 中 | — |
| **C3** | blocking hook gate（執行序強制） | PreToolUse 驗前置 artifact 不過就 deny；PostToolUse 蓋章/生成下一關。首 gate＝`snapshot_write`（L1）until `edge_residue` artifact 存在 | 中 | C2, T2 |
| **C4** | gate 原生 Bash code-exec 的 hook | 比照 prototype/serve hook，擋臨時 `python`/script（§9.2 真逃生口） | 小 | **與 C3 同時**（co-require） |
| **C5** | 強制入口 per-version README | 單一可讀權威；強制力在 hook state-gate、README 只是 gate 指回處（非一次性注入） | 中 | C2, C3 |
| **C6** | 跑完彙整回報使用者 | 各關是否執行/產物/結果彙整回報（基礎原則 7） | 小 | C2 |

**順序鎖（硬約束）**：
1. ~~C0 最先~~ ✅ 已完成；基材＝MCP 已定。
2. **T2 在 T5 之前**（§9.4 順序鎖：先搬確定性運算進工具、後拔 provider）。
3. **T5 最後**（免-key 鏈全綠後才刪 provider；終局刪除）。
4. **C4 與 C3 同時**（只 gate MCP 順序、不 gate 原生 code-exec＝沒堵逃生口）。
5. **T2 是兩軌交點**：既是軌 1 的 L1 補鏈，也是軌 2 首個 hook gate（C3）要驗的 artifact。

### 10.7.1 已拍板決策（D1 / D2，使用者 2026-06-08 B 確認）

**D1 ＝ 退場生成、保留 display、不建 T3/T4。** 理由（驗證所得）：
- viewer（`the-door ui`）是 **headless 本地 web server**，人在瀏覽器點擊；那一刻**沒有 agent 在迴路**可當 LLM ⟹ 點擊即生成**本質 key-bound**，補不補三件套都無法 key-free。
- L2/diff 對使用者**今天已失效**（無 key，§10.3），故此為「增益」決策、非「避免退化」。
- ⟹ **不投機建 T3/T4**（fact-finder：不為已失效功能投機建）；viewer 生成路隨 T5 拔；前端（`layers.js`/`ui-diff-explanation.js`）**保留**為 display-only。真要 key-free，是日後「agent 端 L2/diff MCP triple＋viewer display-only」的獨立加法。

**D2 ＝ 切片優先（非「兩軌綁」亦非「軌1全做完」）。** 理由：
- 種子 §6/§7 已定「先垂直切片證機制、剔除大爆炸」。
- 使用者主目標「移除 key 影響」靠 **T1（隔離，小）先兌現中間里程碑**；**T5（終局刪除）吃 ~19 測試檔 fallout，必須最後、不與他刀綁**。
- 控制機制（軌2）是丙案重點且最該先證 ⟹ 第一刀＝§6 垂直試點（T2+C3+C4），落在兩軌交點，一次證機制 end-to-end ＋ 補雜訊可觀察。

### 10.7.2 執行排序（階段；D1/D2 已併入）

| 階段 | 刀 | 為何在這 |
|---|---|---|
| **0** ✅ | C0 | 已實證（§10.1） |
| **1 — 垂直試點 ＋ 兌現 key 中間里程碑** | **T1**（隔離 provider 到單一 seam） | 小、獨立；把 key 影響關進可 disable 的點（過渡，非終局） |
| | **T2**（`edge_residue` 工具） | 小、無依賴、兩軌交點；補雜訊可觀察 |
| | **C3 + C4**（gate `snapshot_write` until `edge_residue` artifact 存在 ＋ gate 原生 bash code-exec） | 證全機制 end-to-end（gate+deny教學，非只 C0 matcher）；首 gate 直接驗 artifact 存在，**還不需完整 C2** |
| **2 — 一般化控制層** | **C2**（checklist schema） | 把階段1的 ad-hoc 存在檢查升成 schema |
| | **C5**（強制入口 README） | gate 指回的可讀權威 |
| | **C6**（跑完回報） | 基礎原則 7 |
| | （擴展 gate 到 extract/snapshot/diff 鏈，C1 確認表） | 水平推廣 |
| **3 — 收 key（終局）** | **T5**（移除 provider＋死碼＋viewer 生成路） | **最後**；免-key 鏈已綠；吃 ~19 測試檔 fallout；**終態＝零 API-key 接口** |
| **deferred** | ~~T3/T4~~ | D1：viewer 生成本質 key-bound，不投機建 |

> 註：T1 可與 T2 並行（皆小、獨立）。階段 1 完成＝§6 試點兌現（機制證好 ＋ 雜訊可觀察 ＋ key 影響已隔離）。

### 10.8 下一個對話的起點（承 §8，已更新）

§8 待定事項的現況：
1. 試點從「雜訊 stage」起 → **建議維持**（T2＋C3，一刀補兩洞，且 C0 已證機制）。
2. stage 切割清單 → §10.5 已大半盤完，縮成確認表。
3. checklist schema → 仍待設計（C2）。
4. hook 落 settings.json 哪層／跨 IDE → C0 證實 PreToolUse 可擋 MCP；落點＝穩定設定檔（非 local），跨 IDE 待各家驗。
5. 移除 key 退場範圍 → §10.3 已校正為 3 面 5 點；**D1 拍板＝全刪（含 viewer 生成路），非 deprecated 保留**（見 §10.7.1、T5 上方紅字）。
6. 流程紀律不變：spike → spec → 雙審 → plan → 雙審 → inline TDD → ff-merge。

**✅ 分類與排序已完成、D1/D2 已拍板（§10.7.1/§10.7.2）。** 使用者明示順序「先分類 → 排優先序/拍 D1·D2 → 才寫 spec」**前兩步已走完**。

**🔴 下一步＝對「階段 1」寫第一份 spec**（§10.7.2）：建議標的＝**T2（`edge_residue` 工具）**，因它無依賴、是兩軌交點、且是 C3 首 gate 要驗的 artifact（先 T2 再 C3+C4 才有東西可 gate）。T1 可並行另起。**仍照流程紀律：spike → spec → 雙審 → plan → 雙審 → inline TDD → ff-merge。**
