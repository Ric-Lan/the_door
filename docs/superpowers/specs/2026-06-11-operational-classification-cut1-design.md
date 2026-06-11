# Design — Cut 1: operational classification + unmapped_nodes summarization — 2026-06-11

> 解 handoff_2026_06_11 §4 **#2**（analyze_changes 輸出 22 萬字）。承本 session 的
> spike（path/naming 分類 vs 可達性的頭對頭實測）。**刀 1 走 path/naming；可達性
> 連貫性歸刀 2（背 Lens-4 鄰近度 + per-runtime entry + Git 時間軸 + 行為紅旗）。**
> 流程：spike→spec→雙審→plan→雙審→（本刀依使用者指示，plan 雙審後停、問使用者）。

## 1. Problem（spike 實測，非臆測）

`analyze_changes(v170, baseline=v1.6.5)` 回 **220,823 字**。分解：
- `unmapped_nodes` = **169,527 字（76.8%）**，其中 `removed` 1607 個 node = 150,307 字。
- 那 1607 個 removed 裡 **~1539（96%）是測試節點**（`tests/unit`×1371、integration、fixtures、
  contract、scenario、property）+ prototype——**從不對應任何 L1 feature**（功能由 src 節點定義），
  故全進 `unmapped_nodes` 被裸傾倒。
- agent 在增量鏈該消費的是 `affected_features`（要重產的 feature）；`unmapped_nodes` 是診斷性附帶，
  卻以「裸列每個 node_id（~90 字長路徑）」形式塞爆同一回應。

**根因（spike 裁定）**：缺少「偵測非專案實際運用內容」的機制。測試/fixture/script/prototype 不是
產品運行的一部分，但被當一等結構內容裸傾倒。

## 2. 為何 path/naming 而非可達性（spike 頭對頭）

對 v170（1431 nodes / 3373 edges，圖健康：最大連通分量 1099）：
- **可達性（從 38 進入點）**：閉包 436、orphan 972。但**誤判 191 個真操作節點為 orphan**
  ——121 個 src（占 src 23%，其中 87 個因動態派發漏邊）+ 70 個 viewer（JS、瀏覽器 runtime，
  Python entry 抓不到）。對 #2 是**又重又有損的錯工具**。
- **path/naming（零圖）**：`non-operational = 803/1408（57%）`（773 test + 30 prototype），
  **100% 涵蓋 #2 的膨脹源、零假陽性、確定性**。

⟹ #2 的最佳解是 path/naming。可達性連貫性對「死碼/惡意」願景才適用，且需 3 個前提（刀 2）。

## 3. Decision

兩件事，純加法、零 snapshot 契約 bump：

### 3.1 純分類器（zero-graph、deterministic）

新模組 `core/classification/operational_classifier.py`（或 `core/topology/` 下；模組落點交 plan
定），純函式：

```python
def classify_node(node_id: str) -> str
```
回傳 category（單一字串）：`operational`（預設）/ `test` / `fixture` / `script` / `prototype`。

**刀 1 只用 path/filename 訊號（zero-graph、僅靠 node_id 字串）**：
- **path**：`/tests/` 或 `tests/` 開頭 → test；`/fixtures/` → fixture；`/scripts/` 或 `scripts/`
  開頭 → script；`/prototype` → prototype（對齊本專案「prototype/ 已廢棄、viewer/ 才是正式版」）。
- **filename**：`test_*.py` / `*_test.py` / `conftest.py` → test。

> **decorator 訊號刻意退出刀 1（雙審 feasibility 裁定）**：分類器的唯一消費點是
> `unmapped_nodes` 投影，那裡只有**裸 `node_id` 字串**（且 `removed` 來自 baseline 結構），
> **拿不到 `ASTNode.decorators`**。spike 已證 path/filename 單獨涵蓋 803/803 的膨脹源 →
> decorator 是無消費者的加固，違 Economy。**留刀 2**（屆時若分類器要吃 ASTNode 再加）。

**安全方向＝預設 operational**：只有**確信**符合非操作樣式才歸非操作；任何不確定 → operational
（保持可見）。⟹ 只有偽陰性（怪位置的測試仍被列舉），**永不偽陽性**（永不隱藏真操作節點）。
符合 fact-finder：不確定就別藏。

`viewer/` 不符任何非操作樣式 → operational（它是正式前端）。`prototype/` → 非操作。

### 3.2 analyze_changes 摘要 unmapped_nodes

把 `unmapped_nodes` 的值重塑：**三個子清單（added/removed/modified）全用同一規則**——
用分類器拆兩堆——
- **operational**：照舊**列舉 node_id**（agent 可能要看）。
- **non_operational**：**只摘要**——`{by_category: {test: N, prototype: M, ...}, total: K}`，**不列 id**。

新 shape：
```json
"unmapped_nodes": {
  "added":    {"operational": ["...id..."], "non_operational": {"by_category": {...}, "total": N}},
  "removed":  {"operational": ["...id..."], "non_operational": {"by_category": {"test": 1539, ...}, "total": 1542}},
  "modified": {"operational": ["...id..."], "non_operational": {"by_category": {}, "total": 0}}
}
```
v170 效果預估：`removed` 從 150K → ~41 viewer/其他 id（~4K）+ 一行摘要。**剩餘的 ~40–50K 主要是
`affected_features.delta`（41K），那是操作性、contract-locked、actionable 內容——本刀不動、也不該動。**

> **成功條件（誠實，雙審校正）**：「總量大降」**有條件**——只在「測試/腳手架主導的 churn ＋ 慣例測試
> 佈局」下成立（如 The Door 自身、v170）。若某版本是**操作性 feature 大改**，`affected_features.delta`
> 會主導且仍可能大——**那是預期且可接受**（它是 agent 真要消費的部分，不是噪音）。慣例佈局之外（測試
> 不在 tests/、無 test_ 前綴）→ 分類器退化為「不摘要」（仍正確、只是不縮），**安全失敗**。

## 4. Scope

In:
- 新 `core/classification/operational_classifier.py`（純函式 + category 常數集）。
- `mcp/tools/analyze_changes_tool.py`：`unmapped_nodes` 投影改用分類器摘要。
- 測試：分類器單元（path/filename/decorator/預設 operational）、analyze_changes shape 整合、
  更新 `tests/contract/test_incremental_diff_shape_contract.py`（unmapped_nodes 新內部 shape）。

Out（明確不做、留刀 2 或別處）：
- **可達性/圖連貫性**（刀 2，背 Lens-4 + per-runtime + Git 時間軸 + 行為紅旗）。
- **死碼/惡意偵測**（刀 2）。
- 改 extraction 範圍（**不停止抽測試**——資料保留供刀 2 安全層用；只在回應層摘要）。
- `affected_features.delta`（contract-locked、操作性、本刀不碰）。
- membrane 投影（category 是結構事實非 doubt/confidence signal；是否套膜交雙審，預設不套以保最小）。
- snapshot 持久化 category（未來可選；本刀只在 analyze_changes 回應即時分類）。

## 5. Backward-compat（已查證）

- `unmapped_nodes` 消費者＝**agent + contract 測**；**viewer 不讀**（grep 確認 0 處）；
  **不持久化**（analyze_changes 唯讀回應、非 snapshot）。
- contract 測只斷言 `unmapped_nodes` **key 存在** + `affected_features[].delta` 有 added/removed/modified；
  **未鎖 unmapped_nodes 內部 shape** → 只需更新該測反映新 shape。
- 無 `SNAPSHOT_CONTRACT_VERSION` bump（非持久化欄位）。

## 6. Risks / 邊界（誠實）

- **�path 啟發式的偽陰性**：非標準位置的測試（不在 tests/、無 test_ 前綴、無 pytest decorator）
  會被當 operational 列舉。可接受——只是少摘要一點，永不藏真節點。decorator 訊號可加固（雙審定）。
- **viewer 大版本變動**：viewer 是 operational，若 viewer 自身大改，其 unmapped 仍列舉（正確——它是產品）。
- 這是**摘要不是刪除**：非操作 node 的存在與計數仍回報，只是不裸列 id；要逐一可去 structure.json。

## 7. Verification

**主要 oracle＝結構性斷言（確定性、不依賴會漂移的 live 數字）：**
- 分類器單元：`tests/unit/...` 路徑 → test；`conftest.py` → test；`scripts/` → script；
  `/prototype` → prototype；`src/` 與 `viewer/` → operational；不確定 → operational（預設）。
- **analyze_changes shape 整合（合成 fixture，非 220K live）**：構造一個小 `IncrementalDiff`，
  `unmapped_nodes.removed` 含 N 個 test-path node + M 個 src-path node →
  斷言輸出 `removed.non_operational.by_category.test == N`、`removed.operational` 恰含那 M 個 src id、
  **`removed` 內不含任何裸 test id**。三桶（added/removed/modified）各驗一次。
- contract 測更新後綠（反映 unmapped_nodes 新內部 shape）；全套 `python -m pytest` 零回歸。

**次要 sanity（非 gate，會漂移、僅佐證）：**
- 對 v170 重跑 analyze_changes：payload 總量明顯下降（測試 bulk 消失）；
  `unmapped_nodes.removed.non_operational.by_category.test` ≈ 1539（量級）；operational 清單仍含 viewer 等真節點。
- **餘量歸因步驟（閉合「到底修好沒」）**：確認修後剩餘大宗 = `affected_features.delta`（操作性、
  contract-locked、actionable），而非殘餘噪音 → 證明 #2 的「噪音淹沒」確實解除，剩下的是 agent 真要的內容。
