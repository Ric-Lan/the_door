# The Door 自我重構 — 動刀待辦清單

> **產生時機**：2026-05-31，以高保真 `structure.json`（`the-door extract` 產出）
> 為依據，套用已確認的重構決策準則得出。
> **正在進行**：`api_handlers.py` 拆分（第一刀，brainstorming 中）。本檔記錄**其餘**刀。

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

### 🔪 T1 · guidance dead-code 確認後移除（高值 × 低險）
- **檔案**：`core/guidance/`（suggester.py / state.py 等）
- **依據**：L2 偵測到該功能 fan-in=0 候選最多（11 個，全動刀清單最大死碼群）。
- **動法**：**先逐一確認**每個候選不是 CLI / MCP / 動態派發入口（抽取器看不到的外部呼叫），
  確認屬實才移除。
- **準則**：C（隱憂先標記後處理）。confidence=low，**確認是前置條件**，不可直接刪。
- **驗證**：移除後全套測試綠燈、覆蓋不降。

### 🔪 T2 · `models.py` 套件化（高值 × 高險，需獨立 spec）
- **檔案**：`models.py`（1004 行 / 86 nodes，全 repo node 數第一）
- **依據**：承載多領域 dataclass（抽取 / 差異 / UI / 資料模型契約混一檔）= 多職責（準則 A）。
- **風險**：全系統 fan-in 最高中樞；緊鄰護欄（ASTNode / snapshot schema 不可改）。
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

- [ ] T1 guidance dead-code
- [ ] T2 models.py 套件化（需獨立 spec）
- [ ] T3 report_renderer 長函式
- [ ] T4 pipeline_orchestrator 長函式
- [ ] T5 store 內部整理
- [進行中] **api_handlers.py 拆分（第一刀，另立 spec/brainstorm）**
