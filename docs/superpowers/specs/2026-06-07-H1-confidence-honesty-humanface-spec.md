# H1 spec：人類面 confidence 缺值誠實化（未評估 ≠ 謊報等級）

> **日期**：2026-06-07　**狀態**：spec（pre-plan，已對真實碼 spike）　**性質**：人類面整膜首刀。把 S4 已在 agent 面建立的「confidence `str|None`、None＝未評估」誠實性，補滲透到**人類面**（viewer graph + 後端 graph view-model）。
> **一句話**：S4 讓後端 confidence 變 `str|None`（None＝未評估）。但 viewer 的 graph 路徑把 None 原樣送到 JS、JS 再 `?? 'medium'`／`|| 'high'` **謊報**成真實等級；且 JS 對既有誠實 token `"unknown"`（`view_model.py:164` 早已採用）**沒有渲染**。本刀：後端 graph 路徑對齊 `or "unknown"`、JS 顯式渲染「未評估」中性態、停止把缺值脅迫成等級。

---

## 0. 理論錨點

| 原則 | 對本刀約束 |
|---|---|
| **fact-finder、不自鑄**（§8.2A／S4 通則） | 未評估的 confidence 不可被脅迫成 high/medium/low；缺值＝`"unknown"`（誠實 token），人類面如實顯示「未評估」。 |
| **單一誠實 token** | `"unknown"` 已是既有約定（`view_model.py:164` `feature.get("confidence") or "unknown"`）。本刀**沿用**、不另發明 token；只把 graph 路徑與 JS 對齊到它。 |
| **正做不虛做**（Economy） | 已 spike 證 graph 路徑**確實**送 null（`graph_view_model.py:67/112`、`graph.py:66` 傳 `f.confidence` 原值、S4 後 None-capable）⟹ 真缺陷、非防禦性死碼。 |
| **膜住呈現邊界**（§8.12） | 不碰 persisted snapshot（仍存 bare `confidence`，含 None）；只動 view-model 投影層與 viewer 呈現。 |

---

## 1. 範圍（in / out）

### 做（in）
1. **後端 graph view-model 對齊誠實 token**：`f.confidence` → `f.confidence or "unknown"`，與 `view_model.py:164` 一致：
   - `graph_view_model.py:67`（`build_l1_graph_view_model` node）
   - `graph_view_model.py:112`（`build_l1_graph_view_model_from_snapshot` node）
   - `api/handlers/graph.py:66`（GET 端點 node）
2. **前端 JS 顯式渲染 `"unknown"`＝「未評估」中性態，並停止把缺值脅迫成等級**：
   - `graph.js`：`CONF_LABEL`（:243）加 `unknown:'未評估'`；`confRank`（:24）給 unknown 自有最低資訊序；`lowestConf`（:32）缺值改 `'unknown'`（非 `'medium'`）；node/edge 樣式（:272/:289）unknown → 中性（不套 high 預設、不畫 false-precision dash）。
   - `ui-list.js`：`CONF_PRIORITY`（:4）加 `unknown`；`'low'` anomaly 桶（:38 `confidence === 'low'`）**不**納入 unknown（未評估≠低信心異常）。
   - `ui-detail.js`：若有 confidence 標籤顯示，加 unknown 標籤（:9 `=== 'low'` 維持原義、unknown 不誤入）。

### 不做（out）
- **persisted snapshot / `snapshot.schema.json` confidence**：仍存 bare（含 None）；schema 不動。
- **ui-diff-explanation.js:37 `explanation.confidence || "low"`**：那是 **diff 敘述 LLM 自身**的 confidence（`api/handlers/diff.py:236` 後端缺值即保守填 `"low"`），語義是「生成敘述的把握度」、與「feature 未評估」**正交**，且後端已有刻意預設 ⟹ OUT（不同軸、不同 owner）。
- **L2 module/anomaly confidence（`graph_view_model.py:159/193`，`build_l2_graph_view_model`）**：spike 結論＝這是 **L2 圖**（L2Module/L2Anomaly，源自 L2 generation），與本刀的 **L1 feature confidence 謊報 bug 是不同 surface**（不同 renderer 路徑、不同語義來源）。即便 `BlockSummary.confidence`（snapshot L1.5）為 None-capable，L2 圖的誠實化＝獨立未來刀（需各自驗 None-capability＋謊報渲染）。**H1 嚴格限 L1 feature confidence 三點。**
- **change_type 排序不一致（H2）／risk_flags lexicon（H3）**：後續刀。
- **8 個既有 red 測**（`graph.test.js` cytoscape-mock ×5、`ui-detail.test.js` user-notes ×3）：pre-existing、與本刀正交、不修不破（紅數維持恰 8）。

---

## 2. Spike 事實（2026-06-07，file:line 已驗）

| 層 | 檔案:line | 事實 |
|---|---|---|
| 誠實 token 先例 | `core/ui/view_model.py:164` | `"confidence": feature.get("confidence") or "unknown"`（L1 list 路徑**已**誠實）。 |
| graph 不一致 | `core/ui/graph_view_model.py:67,112` | node `"confidence": f.confidence` / `summary["confidence"]` 原樣傳（S4 後 None-capable）→ JSON null 到 JS。 |
| graph 端點 | `core/ui/api/handlers/graph.py:66` | `"confidence": fs.confidence` 原樣（None-capable）。 |
| JS 謊報 | `viewer/js/graph.js:32,272,289` | `?? 'medium'`／`|| 'high'`：缺值脅迫成真實等級。 |
| JS 無 unknown 渲染 | `viewer/js/graph.js:243`／`ui-list.js:4` | `CONF_LABEL`／`CONF_PRIORITY` 僅 high/medium/low；`"unknown"` → undefined（空白/排序漏）。 |
| 資料來源 | `models/snapshot.py` `FeatureSummary.confidence: str\|None`（S4） | None＝未評估、真實可達 graph。 |
| OUT 確認 | `viewer/js/ui-diff-explanation.js:37`＋`api/handlers/diff.py:236` | diff 敘述自身 confidence、後端刻意預設 low＝不同軸。 |
| viewer-only 佐證 | grep `graph_view_model` 消費者 | **僅** `api/handlers/graph.py` import（無 MCP/agent/persisted 消費者）⟹ `or "unknown"` 不洩進 agent 面（S4 留 None）。§8.12 邊界成立。 |

**結論**：後端 graph 路徑與 list 路徑對 None 不一致（一個 `or "unknown"`、一個原樣）；JS 兩面皆未誠實處理 unknown（謊報 + 不渲染）。本刀＝後端三點對齊既有 `"unknown"` 先例 + JS 顯式「未評估」中性渲染。零 schema/persisted。

---

## 3. 設計（落點；exact code 留 plan）

### 3.1 後端（3 點，對齊 `view_model.py:164` 先例）
`f.confidence` / `summary["confidence"]` / `fs.confidence` → `... or "unknown"`（保持其餘欄不動）。

### 3.2 前端 graph.js（具體可觀測 token）
- `CONF_LABEL`（:243）加 `unknown: '未評估'`。
- `confRank`（:24）：`{ high:3, medium:2, low:1, unknown:0 }`（unknown＝最低資訊、排序殿後但**不**等同 low）。
- `lowestConf` 入參缺值（:32）：`?? 'unknown'`（非 `'medium'`）。
- **node 樣式**（:289 `node.confidence || 'high'`）→ `node.confidence || 'unknown'`：card 類別變 `conf-unknown`（**非** `conf-high`）。**可觀測 token＝class `conf-unknown` present 且 `conf-high/medium/low` absent。**（CSS 無 `conf-unknown` 規則即退基礎 `gv-node` 中性樣式＝可接受；plan 可選加一條 muted 規則，測試只斷言 class 名。）
- **edge dash**（:272 `edge.lowestConfidence || 'high'`）→ `|| 'unknown'`：既有 high＝實線（無 dasharray）、medium=`5 4`、low=`2 4`；**unknown 須與 high 可區分**＝給 unknown 自有 dasharray（如點線 `1 3`）。**可觀測 token＝unknown 邊有 dasharray（≠ high 的無 dasharray）。**

### 3.3 前端 ui-list.js
- `CONF_PRIORITY`（:4）加 `unknown`（排序位置 plan 定，與 confRank 一致方向）。
- anomaly 桶（:38 `f.confidence === 'low'`）維持只認 `'low'`＝unknown 不誤判為低信心異常（誠實：未評估≠低）。

---

## 4. 不變量清單

| # | 不變量 | 強制處 | 理論 |
|---|---|---|---|
| H1-1 | 後端 graph node：`confidence is None` → 輸出 `"unknown"`（三點皆然、與 `view_model.py:164` 一致） | graph_view_model/graph.py ＋ python 測 | 單一誠實 token |
| H1-2 | JS 對 `"unknown"` → `CONF_LABEL['unknown'] === '未評估'`（不 fall through 成 undefined/空白） | graph.js/ui-list.js ＋ vitest | fact-finder |
| H1-3 | unknown node/edge **不**取得 `confidence-badge-high/medium/low`（或對應樣式類）＝具體可觀測訊號；其排序 key 為自有 unknown 序、非 low | graph.js ＋ vitest | 不自鑄 |
| H1-4 | unknown **不**進 low-anomaly 桶（未評估≠低信心） | ui-list.js ＋ vitest | 誠實分類 |
| H1-5 | persisted snapshot/schema/diff-explanation confidence **未動** | grep gate | §8.12／OUT 邊界 |
| H1-6 | 既有 red 測維持恰 8（不修不破）；其餘前後端測零回歸 | full suite ＋ vitest | 隔離 |

---

## 5. 測試策略

- **後端**（python，`tests/unit/core/ui/`）：`build_l1_graph_view_model` / `_from_snapshot` / graph handler 對 `confidence=None` 的 feature → node `confidence == "unknown"`（characterization：先釘現狀 raw-None→flip 到 "unknown"）。
- **前端**（vitest，`graph.test.js`/`ui-list.test.js` 擴充，避開既有 8 red 的 describe）：
  - `CONF_LABEL['unknown'] === '未評估'`；confidence=null/'unknown' 的 node 不取得 high/medium/low 標籤或樣式類。
  - `lowestConf` 對缺值回 'unknown' 非 'medium'。
  - `CONF_PRIORITY` 含 unknown；anomaly filter 不納 unknown。
- **gate**：python 全測零回歸；vitest 紅數維持恰 8（新測全綠）；grep 確認 schema/persisted/ui-diff-explanation 未動。

---

## 6. 7 點審查（第 4 點 grep 已驗）

1. **單一職責**：三點後端對齊誠實 token；JS 加 unknown 渲染分支。✓
2. **介面最小**：無新欄、無新 token（沿用 "unknown"）；純加 unknown 處理分支。✓
3. **可測**：後端純值 flip、前端純標籤/排序斷言；H1-1..6 皆可斷言。✓
4. **API grep 驗真**（§2）：view_model:164✓／graph_view_model:67,112✓／graph.py:66✓／JS graph.js:24,32,243,272,289✓／ui-list.js:4,38✓／diff-explanation OUT✓。無虛構。
5. **錯誤路徑**：unknown 為顯式分支、不再 silent 脅迫；module confidence None-capability＝plan spike 先確認（不虛建）。
6. **向後相容**：已評估 feature（high/medium/low）逐位元不變；只有 None→"unknown" 路徑改變（誠實化、characterization 見證）。persisted/schema 零動。
7. **文件**：結構化、file:line、零佔位符；plan 引本 spec §3.x。

---

## 7. 連貫律回驗

- **承 S4**：agent 面 confidence 缺值誠實化的人類面補完（同一誠實性、跨呈現邊界）。
- **與 H2/H3 正交**：H1＝confidence 軸誠實化；H2＝change_type 排序單一來源；H3＝risk_flags/lexicon。三刀同屬人類面整膜、各自獨立可 merge。
- **lexicon 鋪路**：H1 把 confidence 的 unknown 顯式化，未來 B-lexicon（H3 範疇）若單一來源化 confidence 詞彙，unknown 已是一等公民。
