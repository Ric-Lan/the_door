# 設計 spec：整合健檢 viewer 置入

> 狀態：核可（2026-06-21）。承接 [`2026-06-19-integration-gap-verification-design.md`](2026-06-19-integration-gap-verification-design.md) §9 的 `integration_check` 工具，把判定攤進 viewer。前置：工具與加法持久化已併入 main（`0e9a68b`）。

## 1. 目標
讓非技術讀者在 viewer 裡看到「功能宣稱的依賴有沒有真的接上」——以 **C 方案**（功能卡徽章 + 獨立健檢面板）呈現，且**兩介面由單一資料源驅動、連動**（不各自計算、不各自寫）。

## 2. 核心原則（使用者明示）
**單一真相**：判定只算一次、存一處；徽章與面板都讀同一份；資料不在前端各自重算。

**與 headless viewer 約束相容**：`GET /api/integration` 是**純結構計算、零 agent/LLM**（只讀 snapshot typed relations + structure 圖、跑 BFS）。這不違反「viewer 不在 click 時 host agent-as-LLM」的退場決定（T5-V）——那退的是 L2/diff 的 LLM **生成** POST 端點；本端點與 `get_l1` 同類、display-time 純讀算。

## 3. 架構

### 3.1 後端：判定邏輯抽到 core（共用）
- 現況：`classify_relation` / `_path_within_hops` / `_load_structure` 住在 `the_door/src/the_door/mcp/tools/integration_check_tool.py`。
- 改動：抽到 **`the_door/src/the_door/core/integration/checker.py`**（純函式、無 IO 例外 `_load_structure` 的檔案讀取）。
  - `mcp/tools/integration_check_tool.py` 改為 import core 並保留薄 `execute`（行為與回傳不變、既有測試續綠）。
  - viewer 的 API handler 也 import 同一份 core。
  - 理由：避免 `core/ui` 反向依賴 `mcp/tools`（層級錯亂）；保證 MCP 與 viewer 判定永遠一致＝「不各自寫」的後端體現。

### 3.2 後端：單一 API 端點
- 新增 `GET /api/integration?version_id=<id>`（省略＝最新版），由新 handler（比照 `core/ui/api/handlers/graph.py` 的 `get_l1` 模式）：
  1. `SnapshotStore(project_root).get_snapshot(version_id)`（或 `get_latest()`）。
  2. 用 core checker 對該 snapshot 的 typed relations + `structure.full.json.gz` 算一次。
  3. 回傳單一 payload：
     - `relations[]`：per-relation 五態判定（backed/gap/undetermined/conceptual/not_assessed）+ 證據（路徑或理由）。
     - `features{ feature_id: verdict }`：**per-feature 聚合徽章**——`gap` 若該功能任一 outgoing static 依賴是 gap；否則 `undetermined` 若任一 undetermined；否則 `backed` 若至少一條 static 且全 backed；否則 `none`（無 static 依賴＝不顯示徽章）。
     - `rollup{ backed, gap, undetermined, conceptual, not_assessed }`：專案級計數。
- 端點註冊比照既有 handler 在 API router 掛載（plan 補確切位置）。

### 3.3 前端：單一 state slice，兩處渲染
- `js/api.js`：加 `fetchIntegration(versionId)` → `/api/integration?version_id=...`（比照既有 `fetchL1Graph`）。
- `js/state.js`：加 `integration: null` slice（單一真相）。
- 載入時機：與 L1 同步取（選版時一起 fetch、寫入 `state.integration`）。
- **徽章**：`js/ui-list.js`（清單項）與 `js/ui-detail.js`（詳情）讀 `state.integration.features[feature_id]` 渲染 ✅/❌/⚠（`none` 不顯示）。**join key ＝ `feature_id`**：viewer 的 feature 物件須帶 `feature_id` 與端點 `features{}` 的 key 對齊（plan 須先驗證 L1 view model 的 feature 確帶 `feature_id`；若清單目前只用 label，plan 補上 feature_id 的傳遞）。
- **面板**：新「整合健檢」section（新檔 `js/ui-integration.js`），讀 `state.integration.rollup` + `relations[]` 的 gap/undetermined 清單。

### 3.4 連動（共用 state slice ⇒ 天然一致）
- 面板點某條 gap → 呼叫既有選取機制（設 `state.selectedFeatureId` + 既有 render/scroll）選中並捲到該功能卡；卡上徽章同步高亮（同一份資料）。
- 反向（加分、非必要）：選功能 → 面板高亮其相關列。
- 因徽章與面板都讀 `state.integration`，判定永遠同步，不需互相通知資料、只需共用選取狀態。

## 4. 範圍
- **本步＝當前選取版本的整合健檢**。
- 跨版本 diff（「這版有沒有把上版 gap 修好」）：資料已持久化、為自然下一步，**不在本步**（YAGNI）。
- 動的前端＝唯一正式版 `docs/frontend-local-version-viewer/viewer/`（⛔ 不碰 `prototype/`）。

## 5. 錯誤 / 空狀態（誠實）
- 無 `structure.full.json.gz` 或 snapshot 無 typed relations → 端點回 `rollup` 全 0 + 空 `relations`；面板顯示「未評估（尚未標記 static 依賴或缺結構檔）」；徽章不出現。**不假裝 ❌**。
- 端點錯誤（snapshot 不存在）→ 比照既有 handler 的 error envelope。

## 6. 測試
- **後端**：
  - `core/integration/checker` 沿用既有單元測試（搬家後路徑調整）。
  - 新 API handler 測試：有 gap 的 snapshot → 回正確 `relations`/`features`/`rollup`；空狀態 → 未評估。
  - 回歸：既有 `integration_check_tool` 測試續綠（薄 execute 不變行為）。
- **前端**（vitest）：
  - `state.integration` 載入與形狀。
  - 徽章聚合：feature 有 gap → ❌；全 backed → ✅；有 undetermined 無 gap → ⚠；無 static → 無徽章。
  - 面板渲染 rollup + gap 清單。
  - 連動：面板點 gap → `state.selectedFeatureId` 更新、對應卡被選中。

## 7. 檔案結構（plan 鎖定確切行號）
- Create: `the_door/src/the_door/core/integration/checker.py`、`__init__.py`
- Modify: `the_door/src/the_door/mcp/tools/integration_check_tool.py`（改 import core、薄 execute）
- Create: `the_door/src/the_door/core/ui/api/handlers/integration.py`（新 handler）
- Modify: API router（掛 `/api/integration`）
- Modify: `docs/frontend-local-version-viewer/viewer/js/api.js`（`fetchIntegration`）、`js/state.js`（slice）、`js/ui-list.js` + `js/ui-detail.js`（徽章）
- Create: `docs/frontend-local-version-viewer/viewer/js/ui-integration.js`（面板）
- Tests: 後端 handler 測試、前端 vitest（`tests/ui-integration.test.js` 等）

## 8. 範圍邊界（本步不做）
- 跨版本 diff 的整合健檢比較。
- 面板→功能卡以外的進階互動（圖上高亮邊等）。
