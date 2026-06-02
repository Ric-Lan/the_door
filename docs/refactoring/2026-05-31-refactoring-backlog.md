# The Door 自我重構 — 動刀待辦清單

> **產生時機**：2026-05-31，以高保真 `structure.json`（`the-door extract` 產出）
> 為依據，套用已確認的重構決策準則得出。
> **第一刀完成**：`api_handlers.py` 拆分已實作並 merge（`core/ui/api/` package）。
>
> **2026-06-02 重驗**：以**新跑的 structure.json**（766 nodes / 2321 edges）＋ 跨 repo 活路徑
> grep 重新查證各刀依據。結論：
> - **T1（guidance 死碼）已證偽 → 關閉**（詳見下方 T1 段；「11 候選」是抽取器動態派發盲區的假陽性）。
> - **T2–T5 的 size 依據（行數/node 數）完全重現、可靠**；僅 T2「全系統 fan-in 最高」措辭已修正。
> - **教訓**：The Door 自家抽取器的 **fan-in=0 對「死碼」是不可靠信號**（規則表/click CLI/dataclass
>   dunder/property/MCP 註冊全會假陽性）。size 類依據可靠，dead-code 類依據不可靠。

## 決策準則（北極星）

1. 可讀性／可維護性優先於「乾淨度」。
2. 結構先行，行為不變（純重構，測試零回歸、覆蓋不降）。
3. 證據驅動，不憑感覺。
4. 能簡潔就簡潔——簡單直接優先於多層抽象，抽象要償還成本。

**拆分與簡潔不衝突、各司其職**：
- **拆分** → 讓功能獨立 → 維護更簡單、獨立、明確（維護性軸）。
- **簡潔不重複** → 不繞路、不重工 → 提升運作效率（效率軸）。
- 正確的動刀讓「功能更獨立」且「程式更直白」**同時成立**；若拆完更繞，是拆法錯，不是原則衝突。

## 護欄（越線即否決，記另議）

- 不改抽取層 / ASTNode / L1–L3 / snapshot schema。
- 新增能力旁路、仿 `core/vulnerability/` 範式。
- 不寫框架/廠商特定解析器。
- 測試 100% 覆蓋、零回歸。

---

## 待辦刀（依優先序）

### ❌ T1 · guidance dead-code 移除 — **2026-06-02 證偽、關閉**
- **原依據（已推翻）**：L2 偵測到該功能 fan-in=0 候選最多（11 個，宣稱最大死碼群）。
- **基礎確認結果（證據驅動）**：
  - **活路徑稽核**：`core/guidance/` 被 **8 個 CLI**（status/diff/post_run_hook/wizard/update/
    extract/main/next_action_renderer）＋ **5 個 MCP tool**（system_status/snapshot_write/
    snapshot_patch/analyze_changes/_response_envelope）＋ **3 個 viewer API handler**
    （project/graph/diff）＋ pipeline ＋ 15 測試檔 消費。**是全 repo 最活的模組之一。**
  - **結構快照**：公開符號 fan-in 很高（NextAction in=26、StateInspector/NextActionSuggester
    in=16、Remediation in=15、make_error_envelope in=10）。
  - **那「11 候選」＝ `suggester.py` 的 11 個 `_rule_*` 函式**（in=0）。它們是 `_RULES` 規則表成員，
    經 `suggest()` 的 `factory(state, context)` **動態派發呼叫**——抽取器追不到「函式存進 list/tuple
    再經變數呼叫」的間接，故假報 fan-in=0。逐一查證 15 個零 fan-in 節點（11 rules + dataclass
    dunder + property）**全為活碼**。
- **結論**：**guidance 無任何死碼。** 若照原計畫刪，會刪掉整張規則表、弄壞被 8 CLI/5 MCP/3 viewer
  消費的引導引擎。此刀關閉，不執行。

### 🔪 T2 · `models.py` 套件化（高值 × 高險，需獨立 spec）
- **檔案**：`models.py`（1004 行 / 86 nodes，全 repo node 數第一）
- **依據**：承載多領域 dataclass（抽取 / 差異 / UI / 資料模型契約混一檔）= 多職責（準則 A）。
  （2026-06-02 重驗：1004 行 / 86 nodes ✓ 完全重現。）
- **風險**：高 fan-in 型別中樞（`StructureJSON` in=23、`ASTNode` in=19、`L1Output` in=16，
  2026-06-02 重驗）；**緊鄰護欄**（ASTNode / snapshot schema 不可改）。
  （註：非「全系統絕對最高」——最高是 `project.py::get` 等同名方法聚合節點；原措辭已修正。）
- **安全動法**：只**搬位置 + 維持扁平 re-export**（import 路徑不變、欄位完全不動）=
  純重組非改 schema。**不做深層巢狀 package**（違反簡潔原則）。
- **流程**：**需獨立 brainstorming → spec**，不與其他刀混批；完整測試護網。

### 🔪 T3 · `report_renderer.py` 長函式拉直（中等，緩做）
- **檔案**：`core/pipeline/report_renderer.py`（901 行 / 19 nodes ≈ 47 行/node）
- **依據**：行/node 比極高 = 函式過長；但**職責單一**（渲染）。
- **動法**：先問「流程是否繞遠路、能否拉直」，再考慮抽 helper。**不為拆而拆**
  （準則 A 警告：大但單一職責不該切檔）。簡潔優先於切割。

### 🔪 T4 · `pipeline_orchestrator.py` 長函式拉直（中等，緩做）
- **檔案**：`core/pipeline/pipeline_orchestrator.py`（724 行 / 17 nodes ≈ 43 行/node）
- 同 T3：長函式、單一職責（協調）。拉直流程優先，避免加層。

### 🔪 T5 · store 內部整理（中低，無急迫）
- **檔案**：`core/diff/snapshot_store.py`（522 行）、`core/scope/doubt_store.py`（534 行）
- **動法**：內部整理；`snapshot_store` 注意不碰 snapshot schema（護欄）。

---

## 🚫 明確不動（護欄內，雖大 off-limits）

- `core/extraction/edge_builder.py`（883 行）— 抽取層。
- `core/extraction/node_builder.py`（754 行）— 抽取層。
- 兩者體積大但在護欄內，**本輪重構範圍外**。若日後判斷必要，需先解護欄約束、另議。

---

## 進度

- [x] **api_handlers.py 拆分（第一刀）— 已實作 + merge（`core/ui/api/` package）**
- [❌] ~~T1 guidance dead-code~~ — **2026-06-02 證偽、關閉**（guidance 是活碼，無死碼可刪）
- [ ] T2 models.py 套件化（需獨立 spec；size 依據 2026-06-02 已重驗）
- [ ] T3 report_renderer 長函式（901 行 ✓ 已重驗）
- [x] T4 pipeline_orchestrator 長函式 — 已實作（run() 拉直：8 提早離場收斂為單一 _partial 閉包）
- [ ] T5 store 內部整理（snapshot_store 522 / doubt_store 534 ✓ 已重驗）
