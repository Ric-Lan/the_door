# Flow View：viewer 圖形視圖替換為拓撲分層有向布局

**日期**：2026-07-05
**狀態**：spec（待雙審）
**範圍**：純前端呈現層（`docs/frontend-local-version-viewer/viewer/`）。零後端、零 API、零契約、零 gate 改動。

---

## 1. 動機與問題

viewer 目前的圖形視圖（`js/graph.js` `renderGridGraph`）是**無向平鋪網格**：

- 卡片位置＝DOM 排列序，零語意。
- 邊的方向資料一路都在（snapshot `from_feature→to_feature` → API `source`/`target`），
  但前端畫成**無箭頭直線**，方向被呈現層丟棄。
- 使用者無法從圖上讀出「資訊流順序」——例如 client → API → 服務 → DB 的端到端閱讀感。

**替換而非並存**：網格位置不承載資訊，換成分層布局是純資訊增益；且 L1/L2/L3 三層
與 diff 模式共用單一 `initGraph` → `renderGridGraph` 漏斗，改一處全域生效。

## 2. Spike 結論（真資料，2026-07-05）

### L1 feature 圖分層（三個 test-target 最新快照）

| 專案 | features | edges | 層數 | 每層寬 | 真環邊 | 斷連分量 |
|---|---|---|---|---|---|---|
| v170 | 21 | 24 | 5 | [10,2,3,2,4] | 0 | 4（含 3 個完全孤立 feature） |
| integration-demo | 5 | 5 | 3 | [1,3,1] | 0 | 1 |
| radicli | 8 | 8 | 5 | [4,1,1,1,1] | 0 | 1 |

integration-demo 直接分出 `feat-order → auth/report/user → feat-db` 的教科書三層形——
正是目標閱讀感。

### L3 node 級子圖分層（v170 前五大 feature，DFS back-edge 版）

| feature | 節點 | 邊 | back-edge | 層數 | 最寬欄 |
|---|---|---|---|---|---|
| feat-ui-http-api | 42 | 41 | 0 | 4 | 24 |
| feat-code-extraction | 37 | 32 | 0 | 5 | 23 |
| feat-viewer-workbench | 31 | 34 | 1 | 9 | 17 |
| feat-versioning-diff | 30 | 14 | 0 | 4 | 20 |
| feat-cli | 30 | 53 | 2 | 5 | 18 |

### spike 推翻的兩個扶手椅判斷（記錄以防回退）

1. **naive Kahn 破環高估 10 倍**：viewer-workbench 用「選中節點斷其全部殘餘依賴邊」
   算出 11 條環邊；DFS back-edge 實測**只有 1 條**真環邊。⟹ 打環必須用 DFS back-edge。
2. **「寬欄純垂直排」不可行**：L3 最寬欄 24 卡 × 每卡約 102px 縱距 ≈ 2400px，比現行
   網格整張圖還高。⟹ 必須欄內折行。

## 3. 設計決策（已定案）

### D1 分層演算法：DFS back-edge + 記憶化 longest-path（純函式）

- 輸入 `{nodes, edges}`（edge ＝ `source depends_on target`），輸出
  `{ columnOf: Map<node_id, int>, backEdges: Set<edge>, isolated: node_id[] }`。
- **決定性 DFS**（根節點與鄰接串列皆按 `node_id` 字典序）標 back-edge（指向 GRAY
  節點的邊）；self-loop 邊直接忽略。
- 去 back-edge 後圖必為 DAG → 記憶化 longest-path：`depth(n) = 1 + max(depth(其依賴))`
  （無依賴者 depth=0）。
- **顯示欄索引須反轉**（第二審補明，防照公式直排左右顛倒）：
  `顯示欄 = maxDepth − depth(n)`——entry（depth 最大）落最左欄、
  被依賴最深者（depth=0，底層 models/DB 類）落最右欄。
  閱讀方向＝左（入口）→ 右（底層），與「client → API → DB」直覺一致。
- 同欄內卡片按 `node_id` 字典序——同輸入永遠同圖。

### D2 寬欄：band 內折行，上限 8 卡/子欄

- 同深度＝同一視覺 band（垂直欄帶、有視覺分隔）。band 內超過 8 卡折成子欄
  （CSS flex `column wrap` 或等價 grid）。
- band 高上限 ≈ 8 × 102px ≈ 816px（約一視窗高）；v170 L3 最寬 feature 折行後
  總寬 ≈ 7 子欄 × 180px ≈ 1260px，畫布橫向滾動，可接受。
- L1 場景（最寬 10 卡→2 子欄）由同一規則自然涵蓋，不設特例。

### D3 孤島：「未宣告關聯」獨立列

- **無任何邊**的節點（v170 L1 有 3 個：`feat-datamodel-localization`、
  `feat-domain-models`、`feat-execution-gate`；L3 更多）集中放畫布最下方獨立一列，
  帶標題「未宣告關聯」。誠實呈現「沒有資訊流資料」，不隨機塞欄假裝有位置語意。
- **有邊的斷連小分量**照常參與分欄（它們自己有流向），不特殊處理。

### D4 L3 一併替換、不做 fallback

- 單一漏斗替換，L1/L2/L3 自動全換。五大 L3 子圖實測全部可用（層數 4–9、
  back-edge ≤ 2、寬欄由 D2 解）。「退回網格」的 fallback 選項**取消**——
  沒有坐實的需求不加碼。

### D5 邊的視覺編碼：方向 + integration 狀態；信心退出邊

一條邊只承載兩種資訊（使用者拍板，2026-07-05）：

- **方向**：SVG `<marker>` 箭頭，指向被依賴者（即指向右方）。
- **integration 狀態**（僅 L1；L2/L3 無此概念、一律灰）：
  - `gap` ＝ 紅（宣稱 static 但結構沒接上——資訊流圖上的「斷點」）
  - `backed` ＝ 綠
  - 其餘（`undetermined`/`conceptual`/`not_assessed`/無資料）＝ 灰。
    與整合面板同一誠實原則：不把未評估洗成全綠。
- **虛線只剩一個語意：循環回邊**（back-edge）。既有「信心虛線」編碼自邊上退場
  （信心已在卡片上有 `conf-*` 邊框樣式＋文字標籤，邊上重複是雙重計數）。
- 卡片渲染完全不動：diff 標籤（`change_type`）、信心樣式、點擊進 detail 全保留。

**資料對齊（已驗證）**：`integration.relations[]` 形狀＝
`{from_feature, to_feature, verdict}`，與邊 `(source, target)` 同鍵直接 join。

**資料生命週期（第一審 critical 修正，2026-07-05）**：現行碼的載入順序**不可依賴**——
API 路徑 `app.js:174-176` 是 `loadL1Graph`（畫圖）先、`fetchIntegration` 後（首繪拿不到）；
且另 5 個 `loadL1Graph` 呼叫點（mode 切換、版本切換、breadcrumb 返回）完全不重抓
integration → 切版本後邊色會是**上一版的過期 verdict**（比灰更糟，違反誠實原則）。
定案：**integration fetch 收進 `loadL1Graph`**（它已是 L1 state+graph 的單一權威），
用同一 `versionId` 抓、附掛進 viewModel（`viewModel.integration`）後才 `initGraph`；
`app.js:176` 原處的 fetch 移除（整合面板改讀同一份 `state.integration`，由
loadL1Graph 寫入）。fetch 失敗 → `null` fail-soft → 邊全灰、不阻斷。
此設計同時解三件事：首繪時序、版本切換過期資料、graph.js 模組耦合
（graph.js 保持純參數、不 import state、`initGraph` 介面不變）。

### D6 Legend 更新

`renderLegend` 增加：箭頭方向語意（左＝入口、右＝底層）、紅邊＝整合落差（沒接上）、
綠邊＝有結構支撐、虛線邊＝循環。既有 diff 四色圖例保留。

## 4. 元件切分

| 單元 | 職責 | 依賴 |
|---|---|---|
| `js/flow-layout.js`（新） | 純函式：`detectBackEdges(nodes, edges)`、`assignColumns(nodes, edges, backEdges)`、`splitIsolated(nodes, edges)`。零 DOM、可獨立單元測 | 無 |
| `js/graph.js` `renderFlowGraph`（取代 `renderGridGraph`） | 讀 layout 結果 → 建 band/子欄 DOM → 卡片渲染（沿用現有卡片碼）→ 呼叫邊繪製 | flow-layout.js |
| `js/graph.js` `_drawFlowEdges`（改自 `_drawGridEdges`） | DOM rect 現算座標（機制沿用）；**錨點改為源卡右緣中點 → 目標卡左緣中點**（back-edge 反向：源卡左緣 → 目標卡右緣；中心對中心會穿過中間欄卡片，棄用）＋ `<marker>` 箭頭 ＋ 邊色（查 `viewModel.integration`）＋ back-edge 虛線 | viewModel.integration（可為 null） |
| `js/graph.js` `renderLegend` | 圖例增項（D6） | 無 |
| `js/layers.js` `loadL1Graph`（小改） | fetch integration（同 versionId、fail-soft）→ 附掛 `viewModel.integration` → 才 `initGraph`；同時寫 `state.integration` 供整合面板讀 | api.js `fetchIntegration` |
| `js/app.js`（小改） | 移除 :176 的 `fetchIntegration`（權威移至 loadL1Graph） | 無 |
| `styles.css` | `gv-grid` → band/子欄樣式；`gv-edges` 保留；孤島列樣式 | 無 |

`initGraph` 介面不變（`containerId, viewModel, onNodeClick`），呼叫端
（`layers.js` 5 處、`app.js` 1 處）零改動。integration 隨 **`viewModel.integration`**
傳入（由 `loadL1Graph` 附掛，見 D5 資料生命週期；graph.js 不 import state、保持純參數）。
`_drawFlowEdges` **無條件按 `(source, target)` join**——L2/L3 的 viewModel 沒有
`integration` 欄位、node_id 也天然比不中 feature_id 鍵 → 邊自動保持灰，零層級分支。

## 5. 錯誤處理與邊界

- **空 viewModel**：沿用既有 empty-state 路徑（`initGraph` 現有分支，不動）。
- **單節點/全孤島**：全部落入「未宣告關聯」列，主畫布空——合法輸出，不報錯。
- **self-loop 邊**：布局忽略、也不畫（現行網格同樣畫不出自環；誠實起見 legend 不宣稱涵蓋）。
- **dangling edge**：上游 `graph_view_model.py` 已過濾（omit + warning），前端不重複防。
- **integration 資料缺席**：`viewModel.integration == null`（fetch 失敗或 L2/L3）→ 全邊灰。
- **決定性**：同一 viewModel 輸入，布局輸出位元級一致（測試斷言）。

## 6. 測試

- **單元（新 `tests/flow-layout.test.js`）**：back-edge 偵測（含環/無環/self-loop）、
  分欄正確性（鏈/菱形/多分量）、孤島分離、決定性（同輸入跑兩次深比對）、
  8 卡折欄門檻。
- **渲染（改 `tests/graph.test.js`，既有 11 處引用跟改）**：band DOM 結構、卡片保留
  diff 標籤/信心 class/點擊 handler、箭頭 marker 存在、gap 邊紅色 class、
  integration null 時全灰、孤島列標題。
- **渲染（補，第一審 F1 衍生）**：`loadL1Graph` 附掛 integration 的行為——
  fetch 失敗 fail-soft、版本切換後 integration 隨新 versionId 重抓（過期資料防護）。
- **e2e（手動驗收）**：`the-door ui` 開 v170 與 integration-demo——
  integration-demo 應呈現 order → auth/user/report → db 三欄；v170 L1 五欄、
  3 孤島在下方列；drill 到 feat-ui-http-api 的 L3 檢查折欄與可讀性；
  **切換版本後邊色跟著新版本**（F1 回歸驗證）。
- **plan 階段補驗**（第一審 Gap）：ui-blocks.js blocks-mode 與 `graph-container`
  是否互動（若會動 graph 區，band 樣式可能撞）——動工前一條 grep 收掉。

## 7. 誠實限制（寫給使用者的話也照此）

- 分欄＝**依賴深度序**，不是架構角色標籤——圖不知道誰是「DB」誰是「佇列」。
  角色標籤是語意判斷，結構算不出；本刀不做（避免 phantom 資訊）。
- 圖的品質上游依賴 relations 的判斷品質（agent-as-LLM 產出、CLAUDE.md 判準注入）；
  布局是決定性呈現，上游標錯它照畫——紅邊（gap）正是讓上游錯誤現形的機制。
- 邊不做交叉最小化；feature 圖規模天生有界（數十量級），實測可讀。

## 8. 出範圍（明確不做）

- 架構角色標籤（client/API/DB 之類的語意分類）。
- dagre/ELK 等布局庫引入。
- 後端算層級 / API 改動。
- diff 模式特殊布局（卡片標籤機制自動存活，無需特殊處理）。
- mindmap / blocks / list 視圖（獨立不受影響）。
