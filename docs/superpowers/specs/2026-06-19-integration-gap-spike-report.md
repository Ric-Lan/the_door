# 整合落差驗證 Spike — Go/No-Go 報告

> **日期：** 2026-06-20
> **對應 spec：** `docs/superpowers/specs/2026-06-19-integration-gap-verification-design.md`
> **對應計畫：** `docs/superpowers/plans/2026-06-19-integration-gap-spike.md`
> **測試檔：** `the_door/tests/spike/test_integration_gap_spike.py`
> **Fixture：** `the_door/tests/spike/fixtures/broken_integration/`

---

## 閘門結果總覽

| 閘門 | 可觀察條件 | 結果 | 說明 |
|---|---|---|---|
| **G2 偵測有效性（真陽性）** | 已知斷裂者被標 `gap`（❌） | ✅ **通過** | `UserService.save_user` → `Database` 正確被標 `gap`；無任何 edge 從 `user_service.py::*` 流向 `db.py::*` |
| **G3 假陽性控制（不喊狼）** | N≥3 良好依賴全標 `backed`；外部非程式碼節點標 `undetermined` | ✅ **通過** | OrderService/ReportService/AuthService → Database 全部標 `backed`；RedisCache（不在 graph）標 `undetermined` |
| **G4 非循環性** | 宣稱清單在「看 edges 之前」從描述語意寫定（Task 2 先於 Task 3） | ✅ **通過** | `claims.md` 在抽取前已 commit（`9795e1c`，早於測試 commit `37d2bba`）；宣稱 1 的斷裂是從 `save_user + docstring` 語意推出，非讀 edges 推出 |
| **設計輸入（RelationCheck 無法三態）** | `RelationCheck.check` 把 ❌ 與 ⚠ 都回報為 `errors`，無法區分 | ✅ **通過** | `result.errors` 有 2 條（feat-user→feat-db 及 feat-user→feat-redis）；兩者在 errors 內無法辨別「真斷裂」與「目標不在 graph」——需要存在性前置檢查 |

**所有閘門通過。Spike 結論：GO（條件滿足）。**

---

## 真實抽取資料（Task 4 evidence）

### 抽取到的 node_ids（共 15 個）

```
auth_service.py::AuthService
auth_service.py::__init__
auth_service.py::login
db.py::Database
db.py::connect
db.py::query
order_service.py::OrderService
order_service.py::__init__
order_service.py::create
report_service.py::ReportService
report_service.py::__init__
report_service.py::monthly
user_service.py::UserService
user_service.py::__init__
user_service.py::save_user
```

格式確認：`{filename.py}::{ClassName}` 或 `{filename.py}::{method_name}`（相對路徑段）。
`__init__`（constructor）與 class 本身各為獨立節點。

### 抽取到的 edges（共 12 條）

```
auth_service.py::__init__   → db.py::Database
auth_service.py::login      → db.py::connect
auth_service.py::login      → db.py::query
order_service.py::__init__  → db.py::Database
order_service.py::create    → db.py::connect
order_service.py::create    → db.py::query
report_service.py::__init__ → db.py::Database
report_service.py::monthly  → db.py::connect
report_service.py::monthly  → db.py::query
auth_service.py::AuthService   → db.py::Database  (import-level edge)
order_service.py::OrderService → db.py::Database  (import-level edge)
report_service.py::ReportService → db.py::Database (import-level edge)
```

**user_service.py::* 節點無任何 outgoing edge** → 三態分類器正確輸出 `gap`。

### 三態判定結果（_classify 函式，per claim）

| 宣稱 | from_nodes | claimed_to | 在 graph？ | 有 path？ | 判定 |
|---|---|---|---|---|---|
| UserService → Database | user_service.py::* | db.py::* | ✅ | ❌ | `gap` |
| OrderService → Database | order_service.py::* | db.py::* | ✅ | ✅ | `backed` |
| ReportService → Database | report_service.py::* | db.py::* | ✅ | ✅ | `backed` |
| AuthService → Database | auth_service.py::* | db.py::* | ✅ | ✅ | `backed` |
| UserService → RedisCache | user_service.py::* | redis_cache.py::* | ❌ | — | `undetermined` |

### BFS 傳遞可達性的備注

`RelationCheck._has_path` 使用 BFS 傳遞可達，而非要求直接邊。在本 spike fixture 中，UserService 完全無 outgoing edges，因此傳遞可達同樣找不到路徑，結論正確。
在更大的 codebase（所有模組都互相通過 shared utility 間接可達）可能出現漏報；spec §5.3（D4）建議考慮有限跳數。本 spike **不評估**此風險（範圍外）。

---

## 設計輸入觀察（RelationCheck 無法三態的具體表現）

`test_relationcheck_alone_cannot_three_way` 傳給 `RelationCheck.check`：
- `feat-user → feat-db`（❌ 真斷裂）
- `feat-user → feat-redis`（⚠ 目標不在 graph）

`result.errors` 輸出 2 條，兩條形式相同，**無結構性區分「目標存在但無 path」vs「目標不在 graph」**。
因此若直接用 `RelationCheck` 做使用者面的判定，⚠ 會被呈現成 ❌，違反 G3（喊狼）。
**三態分類必須在呼叫 `_has_path` 之前加「被依賴方是否為程式碼節點」的存在性前置檢查。**

---

## 與計畫假設的差異

| 計畫假設 | 實際觀察 | 差異說明 |
|---|---|---|
| node_id 格式為 `{file_path}::{name}` | 確認：相對路徑段（如 `auth_service.py::login`），非絕對路徑 | 無差異；`endswith(filename)` 比對法正確 |
| `edges` 鍵為 `from`/`to` | 確認：`[{"from": ..., "to": ...}]` | 無差異 |
| 跨模組呼叫有 AST edge | **確認：** OrderService/ReportService/AuthService 所有 `import Database` + 呼叫方法都有 edges | 這是 GO 的最重要發現——抽取器確實能解析跨模組靜態呼叫到 node 級 edge |
| `RelationCheck._has_path` 可重用 | 確認：signature `(from_nodes: set, to_nodes: set, adjacency: dict)` 與測試相符 | 無差異 |

---

## 測試執行摘要

```
2 passed in 0.12s
```

所有斷言通過，無任何弱化（"do NOT change the test to make it pass" 規則未觸發）。

---

## 結論

**GO。**

最關鍵的一條證據：**ASTExtractor 確實能將跨模組的 `import + method call` 解析成 node 對 node 的有向 edge**（OrderService/ReportService/AuthService → Database 各有 3–4 條真實 edges）。這意味「結構本身有足夠的精度」來判斷宣稱依賴是否落地，不需要執行期資訊。

同樣重要的是 G4 非循環性通過：`claims.md` 從純描述語意推出宣稱、早於抽取 commit，宣稱 1（UserService 應連 Database）是獨立命題，不是事後讀 edges 反推——這排除了「比了等於沒比」的循環性顧慮，正是 spec §3.3 要求的中心命題。

下一步：依 spec §7 的建議，走 D3 選項 B（獨立 `integration_check` MCP 工具，現算、不動既有持久化 schema）+ D2 分型（static/inferred 區分）+ D4 帶證據的路徑輸出 + D1 push 優先。進入 writing-plans 前需先拍板 D1/D2/D3/D4 未決選項。

---

## Commit 清單

```
c2571d3  test(spike): add deliberately-broken integration fixture
9795e1c  test(spike): pin integration claims from semantics (pre-extraction, G4)
37d2bba  test(spike): three-way integration verdict + RelationCheck conflation proof
```
