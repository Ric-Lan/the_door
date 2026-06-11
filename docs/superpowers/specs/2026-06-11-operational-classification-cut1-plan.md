# Plan — Cut 1: operational classification + unmapped_nodes summarization

> 實作計畫，對應 design `2026-06-11-operational-classification-cut1-design.md`（已雙審修訂）。
> TDD、純加法、零 snapshot 契約 bump。依使用者指示：**plan 雙審後停、問使用者**，不自行進 TDD。

## 0. Plan 先閉合的兩決策（task 審要求）

- **模組落點**：`core/classification/operational_classifier.py`（**新 package**）。
  理由：①刀 1 是 path-based、**zero-graph**，放 `core/topology/`（圖語意）會誤導；
  ②刀 2 的可達性連貫性分類器也是「分類 node」，會加入同 package（reachability/Git-time/行為紅旗），
  `core/classification/` 給整條分類 campaign 一個家。不是過度結構——刀 2 已具名實在。
- **category 常數**：plain string（design 已定不套 membrane）。
  ```python
  CAT_OPERATIONAL = "operational"
  CAT_TEST = "test"; CAT_FIXTURE = "fixture"; CAT_SCRIPT = "script"; CAT_PROTOTYPE = "prototype"
  NON_OPERATIONAL = frozenset({CAT_TEST, CAT_FIXTURE, CAT_SCRIPT, CAT_PROTOTYPE})
  ```

## ⚠ 範圍鎖（雙審校正，動工前必讀）

Cut 1 **只改 MCP 投影**＝`analyze_changes_tool.py:166-169` 把 `diff.unmapped_nodes.{added,
removed,modified}`（`NodeDelta` tuple）序列化成 dict 的那一段。**`IncrementalDiff.unmapped_nodes`
本身（`NodeDelta`，pipeline 層資料）不變。** ⟹ 已查證：`tests/scenario/test_v105_incremental_flow.py:72`
與 `tests/unit/core/pipeline/test_incremental_pipeline.py:160` 斷言的是 `result.diff.unmapped_nodes`
（NodeDelta 屬性 `.added` 等）→ **不受 Cut 1 影響、不需改**。只有讀 MCP 回應 dict 的測試（
`test_analyze_changes_tool.py`、contract）需更新。

## Task 1 — 分類器純函式（red→green）

新檔 `the_door/src/the_door/core/classification/operational_classifier.py` + `__init__.py`：
```python
def classify_node(node_id: str) -> str
def is_operational(node_id: str) -> bool   # == classify_node(node_id) == CAT_OPERATIONAL
```
- 正規化：取 `node_id.split("::",1)[0]`、`replace("\\","/")`、`.lower()`。
- 樣式（**first-match wins，依此明確順序**；重疊路徑如 `tests/fixtures/` 命中第一條 `/tests/`→test，
  可接受——test 與 fixture 同為非操作、`total` 不受影響、只是歸 test 桶）：
  - filename `conftest.py` / `test_*.py` / `*_test.py` → test
  - path 含 `/tests/` 或開頭 `tests/` → test
  - path 含 `/fixtures/` → fixture
  - path 含 `/scripts/` 或開頭 `scripts/` → script
  - path 含 `/prototype` → prototype
  - 其餘（含 `src/`、`viewer/`、無法判定）→ operational（**預設安全**）

**Task 1 測**（`tests/unit/core/classification/test_operational_classifier.py`）：
- 每個非操作類各 ≥1 正例（真實 node_id 形狀，如 `the_door/tests/unit/cli/test_x.py::test_foo`→test、
  `.../conftest.py::x`→test、`scripts/dogfood_x.py::run`→script、`docs/.../prototype/flow.js::buildWalk`→prototype、
  `the_door/tests/fixtures/...`→fixture）。
- operational 正例：`the_door/src/the_door/core/...::m`、`docs/frontend-local-version-viewer/viewer/app.js::f`。
- **預設 operational**：無法判定的怪路徑 → operational（釘「永不偽陽性」）。
- `is_operational` 與 `classify_node` 一致性。

## Task 2 — analyze_changes 摘要 unmapped_nodes（red→green）

改 `the_door/src/the_door/mcp/tools/analyze_changes_tool.py` 的 `unmapped_nodes` 投影。
抽一個小 helper（同檔或分類器模組）`summarize_unmapped(node_ids: list[str]) -> dict`：
```python
{"operational": [<id>...], "non_operational": {"by_category": {<cat>: <count>}, "total": <int>}}
```
對 `diff.unmapped_nodes.{added,removed,modified}` 三者各套用，取代現行的裸 `list(...)`。

**Task 2 測**（`tests/unit/mcp/test_analyze_changes_tool.py` 追加，**合成 fixture、非 220K live**）：
- **fixture 用真實型別**（雙審校正）：`unmapped_nodes` 是 `NodeDelta(added,removed,modified)` 的
  tuple，**非 dict**。用既有 `test_feature_attribution.py` 的 `_sample_structure_with_nodes` +
  `compute_affected_features` 造一個真 `IncrementalDiff`，使其 `unmapped_nodes.removed` 含
  N 個 test-path + M 個 src-path node_id（測試節點 owned by no feature → 自然落 unmapped）。
  再餵給 analyze_changes 投影路徑（或抽出的 `summarize_unmapped` helper 直接測）。
- 斷言：`removed.non_operational.by_category["test"] == N`、`removed.non_operational.total == N`、
  `removed.operational` 恰含那 M 個 src id、**`json.dumps(removed)` 不含任一裸 test id**。
- added/modified 同規則各驗一次（modified 也走分類，design §3.2）。
- 既有 `test_analyze_changes_returns_incremental_diff`：把對 `unmapped_nodes["added"]` 為 list 的舊斷言
  改為新 shape（dict with operational/non_operational）。

## Task 3 — 更新 shape contract（red→green）

`the_door/tests/contract/test_incremental_diff_shape_contract.py`：
- `unmapped_nodes` 仍為 top-level key（不變）。
- 新增：`unmapped_nodes.{added,removed,modified}` 各為 dict，含 `operational`(list) +
  `non_operational`(dict: `by_category`,`total`)。釘新 shape，防未來退回裸 list。

## Task 4 — 手動 sanity（非 committed 測，依賴外部 v170）

- 跑 `analyze_changes(v170, baseline=v1.6.5)`（拋棄式 pytest，跑完刪），確認：
  payload 總量大降、`removed.non_operational.by_category.test` ≈ 1539（量級）、operational 仍含 viewer。
- **餘量歸因**：確認剩餘大宗 = `affected_features.delta`（操作性、actionable），閉合「#2 噪音淹沒已解除」。
- 不 commit（外部路徑不可攜）。

## 驗收

- 全套 `PYTHONUTF8=1 python -m pytest` 綠、零回歸（baseline 1435）。
- design §7 主要 oracle（結構斷言）全綠；次要 sanity 佐證。
- 純加法：無 `SNAPSHOT_CONTRACT_VERSION` bump、viewer 零改動、無新 hook。

## 不做（重申 design §4 Out）
可達性/圖連貫性、死碼/惡意、decorator 訊號、改 extraction 範圍、affected_features.delta、membrane、持久化 category。
