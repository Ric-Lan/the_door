# 整合落差驗證 — 驗證 Spike 實作計畫

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在一個**故意斷開**的 target 上，證實/證偽「能否建出**不循環的宣稱來源**＋對整合落差的偵測**不喊狼**」，產出可量測的 go/no-go 證據，決定整合落差支線要不要落地。

**Architecture:** 純驗證 spike，**不寫任何 production code**。建一個小型真實 Python fixture（含 1 條已知斷裂、N≥3 條已知良好、1 條外部非程式碼依賴）→ 用 The Door **真實**的 `ASTExtractor` 抽結構 → 用「描述語意」獨立寫出宣稱（先於看 edges，證非循環）→ 一個 spike-only 的三態分類器（reuse `RelationCheck._has_path` + 節點存在性前置檢查）跑出 ✅/❌/⚠ → 斷言驗證對照現實 → 寫 go/no-go 報告。同時用一個對照測試證明「`RelationCheck` 單獨無法三態」以指導後續設計。

**Tech Stack:** Python 3.12、pytest、The Door 既有 `the_door.core.extraction.ast_extractor.ASTExtractor`、`the_door.core.validation.relation_check.RelationCheck`。

**對應 spec：** [`docs/superpowers/specs/2026-06-19-integration-gap-verification-design.md`](../specs/2026-06-19-integration-gap-verification-design.md) §3.3（中心命題：循環性）、§6（可量測閘門）。

---

## 環境須知（每個 Task 都適用）

- **pytest 的 cwd ＝內層 `the_door/`**（雙層 repo）。所有 `python -m pytest` 指令在 `C:/Users/Ric/Desktop/the_door/the_door` 下執行。
- Windows 前置 **`PYTHONUTF8=1`**。
- ⚠ **C4 hook**：禁用 `python -c` 與臨時 `.py` 腳本繞過；一切執行走 `python -m pytest`。
- spike 產物全部隔離在 `the_door/tests/spike/`，go/no-go 後再決定刪除或晉升（見 Task 5）。

## 閘門（這個 spike 要回答的，全部來自 spec §6）

| 閘門 | 可觀察條件 |
|---|---|
| G2 偵測有效性（真陽性） | 已知斷裂者被標 `gap`（❌） |
| G3 假陽性控制（不喊狼） | N≥3 條已知良好全標 `backed`（✅）；外部非程式碼依賴標 `undetermined`（⚠），**不得**標 ❌ |
| G4 非循環性 | 宣稱清單在「看 edges 之前」就從描述語意寫定（Task 2 先於 Task 3） |
| 設計輸入 | 證明 `RelationCheck` 單獨會把 ❌ 與 ⚠ 混為錯誤 → 需要存在性前置檢查 |

任一 G2/G3/G4 證偽 → 比照互動問答**判定不做**，spec 轉「已評估、不落地」。

---

## File Structure

- Create: `the_door/tests/spike/fixtures/broken_integration/db.py` — 共用資料庫存取（被依賴方，程式碼節點）
- Create: `the_door/tests/spike/fixtures/broken_integration/order_service.py` — 控制組：正確連 DB
- Create: `the_door/tests/spike/fixtures/broken_integration/report_service.py` — 控制組：正確連 DB
- Create: `the_door/tests/spike/fixtures/broken_integration/auth_service.py` — 控制組：正確連 DB
- Create: `the_door/tests/spike/fixtures/broken_integration/user_service.py` — **已知斷裂**：宣稱持久化卻只存記憶體
- Create: `the_door/tests/spike/claims.md` — 從描述語意獨立寫定的宣稱（非循環證據）
- Create: `the_door/tests/spike/test_integration_gap_spike.py` — 抽取 + 三態分類器 + 對照斷言 + RelationCheck 混淆證明
- Create: `docs/superpowers/specs/2026-06-19-integration-gap-spike-report.md` — go/no-go 報告

---

### Task 1: 建立故意斷開的 fixture target

**Files:**
- Create: `the_door/tests/spike/fixtures/broken_integration/db.py`
- Create: `the_door/tests/spike/fixtures/broken_integration/order_service.py`
- Create: `the_door/tests/spike/fixtures/broken_integration/report_service.py`
- Create: `the_door/tests/spike/fixtures/broken_integration/auth_service.py`
- Create: `the_door/tests/spike/fixtures/broken_integration/user_service.py`

- [ ] **Step 1: 建立 `db.py`（被依賴方，程式碼節點）**

```python
"""共用資料庫存取層。"""


class Database:
    def connect(self):
        return "conn"

    def query(self, sql):
        return []
```

- [ ] **Step 2: 建立 `order_service.py`（控制組：正確連 DB）**

```python
"""訂單服務：正確把資料寫進 Database。"""
from db import Database


class OrderService:
    def __init__(self):
        self.db = Database()

    def create(self, order):
        self.db.connect()
        return self.db.query("INSERT INTO orders ...")
```

- [ ] **Step 3: 建立 `report_service.py`（控制組）**

```python
"""報表服務：正確從 Database 讀資料。"""
from db import Database


class ReportService:
    def __init__(self):
        self.db = Database()

    def monthly(self):
        self.db.connect()
        return self.db.query("SELECT * FROM orders ...")
```

- [ ] **Step 4: 建立 `auth_service.py`（控制組）**

```python
"""認證服務：正確查 Database 驗證使用者。"""
from db import Database


class AuthService:
    def __init__(self):
        self.db = Database()

    def login(self, name, pw):
        self.db.connect()
        rows = self.db.query("SELECT * FROM users WHERE ...")
        return bool(rows)
```

- [ ] **Step 5: 建立 `user_service.py`（已知斷裂）**

```python
"""使用者服務：描述上「持久化使用者」，但實作只存在記憶體 —— 故意斷裂。
完全不 import / 不呼叫 Database。"""


class UserService:
    def __init__(self):
        self._users = []

    def save_user(self, user):
        # BUG（故意）：宣稱寫入資料庫，實際只 append 到記憶體 list
        self._users.append(user)
        return True
```

- [ ] **Step 6: Commit**

```bash
git add the_door/tests/spike/fixtures/broken_integration/
git commit -m "test(spike): add deliberately-broken integration fixture"
```

---

### Task 2: 從描述語意獨立寫定宣稱（非循環證據，G4）

**Files:**
- Create: `the_door/tests/spike/claims.md`

> **G4 關鍵紀律**：本檔**必須在 Task 3 抽取 edges 之前**寫定並 commit。內容只依據各功能「描述/命名語意」推出「應該要連什麼」，**不得**參考任何 edge 資料。Task 3 的測試清單須與本檔逐條對應。

- [ ] **Step 1: 寫定宣稱清單**

```markdown
# 整合宣稱（從描述語意獨立推出，未參考 edges）

來源規則：只讀每個功能的「名字 + docstring」推「它語意上應該連到什麼」。

| # | 宣稱（from → to） | 推理依據（純語意） | 預期現實 |
|---|---|---|---|
| 1 | UserService.save_user → Database | 「save_user / 持久化使用者」語意上必須落地到儲存 | ❌ 斷裂（已知） |
| 2 | OrderService.create → Database | 「建立訂單」需寫入儲存 | ✅ 有撐 |
| 3 | ReportService.monthly → Database | 「月報表」需讀儲存 | ✅ 有撐 |
| 4 | AuthService.login → Database | 「登入驗證」需查使用者表 | ✅ 有撐 |
| 5 | UserService.save_user → RedisCache（外部、非程式碼節點） | 「快取」常為外部系統、無對應程式碼節點 | ⚠ 無法判定 |

註：宣稱 1 與 5 的「應該要連」純由語意得出，作者寫此表時尚未執行抽取、未看過任何 edge。
```

- [ ] **Step 2: Commit（先於抽取，鎖住非循環性）**

```bash
git add the_door/tests/spike/claims.md
git commit -m "test(spike): pin integration claims from semantics (pre-extraction, G4)"
```

---

### Task 3: spike 測試 — 真實抽取 + 三態分類器 + 對照斷言

**Files:**
- Create: `the_door/tests/spike/test_integration_gap_spike.py`

- [ ] **Step 1: 寫失敗測試（三態分類器 + RelationCheck 混淆證明）**

完整檔案內容：

```python
"""整合落差驗證 spike。

對照 spec §6 閘門：
- test_three_way_verdict_matches_reality → G2 真陽性 + G3 假陽性
- test_relationcheck_alone_cannot_three_way → 設計輸入（RelationCheck 無法三態）

非循環性（G4）：本測試的宣稱清單對應 tests/spike/claims.md，該檔在抽取前已 commit。
"""
from pathlib import Path

from the_door.core.extraction.ast_extractor import ASTExtractor
from the_door.core.validation.relation_check import RelationCheck

FIXTURE = Path(__file__).parent / "fixtures" / "broken_integration"


# --- 抽取輔助：用 The Door 真實 extractor，回傳 node_ids 與 from/to edges ---
def _extract():
    result = ASTExtractor().extract(str(FIXTURE))
    nodes = [n.node_id for n in result.nodes]
    edges = [{"from": e.from_node, "to": e.to_node} for e in result.edges]
    return nodes, edges


def _adjacency(edges):
    adj = {}
    for e in edges:
        adj.setdefault(e["from"], set()).add(e["to"])
    return adj


def _in_file(nodes, filename):
    """挑出某個 fixture 檔的所有 node_id。

    node_id 真實格式為 ``{file.path}::{name}``（見 node_builder.py:144），
    例如 ``db.py::Database.query``。故以**檔名（:: 左側 path 段）**比對，
    對 name 帶不帶 class 前綴都穩定，避免假設 'Class.method' 的點分格式。
    """
    return {n for n in nodes if n.split("::", 1)[0].endswith(filename)}


# 外部、刻意不在 fixture 的非程式碼依賴（格式對齊 path::name，但 path 不存在於圖中）
REDIS_EXTERNAL = {"redis_cache.py::RedisCache.get", "redis_cache.py::RedisCache.set"}


# --- spike-only 三態分類器：RelationCheck._has_path + 存在性前置檢查 ---
def _classify(from_nodes, claimed_to_nodes, graph_nodes, adjacency):
    present = set(claimed_to_nodes) & set(graph_nodes)
    if not present:
        return "undetermined"  # ⚠ 被依賴方不是程式碼節點
    if RelationCheck()._has_path(set(from_nodes), present, adjacency):
        return "backed"  # ✅
    return "gap"  # ❌


def test_three_way_verdict_matches_reality():
    nodes, edges = _extract()
    adj = _adjacency(edges)

    db = _in_file(nodes, "db.py")
    user = _in_file(nodes, "user_service.py")
    order = _in_file(nodes, "order_service.py")
    report = _in_file(nodes, "report_service.py")
    auth = _in_file(nodes, "auth_service.py")

    # 前置健全性：抽取確實看到這些功能的節點（空集合代表抽取/檔名沒對上，先修再續）
    assert db and user and order and report and auth, f"extractor 漏抽節點: {sorted(nodes)}"

    # G2 真陽性：已知斷裂
    assert _classify(user, db, nodes, adj) == "gap"
    # G3 假陽性控制：N=3 條已知良好
    assert _classify(order, db, nodes, adj) == "backed"
    assert _classify(report, db, nodes, adj) == "backed"
    assert _classify(auth, db, nodes, adj) == "backed"
    # G3 非程式碼節點：標 ⚠ 不得標 ❌
    assert _classify(user, REDIS_EXTERNAL, nodes, adj) == "undetermined"


def test_relationcheck_alone_cannot_three_way():
    """證明 RelationCheck 單獨把『真斷裂』與『非程式碼節點』都當錯誤 → 無法三態。
    這是後續設計需要『存在性前置檢查』的依據。"""
    nodes, edges = _extract()
    structure_json = {"edges": edges}
    llm_output = {
        "l1": {
            "features": [
                {"feature_id": "feat-user", "source_nodes": list(_in_file(nodes, "user_service.py"))},
                {"feature_id": "feat-db", "source_nodes": list(_in_file(nodes, "db.py"))},
                {"feature_id": "feat-redis", "source_nodes": ["redis_cache.py::RedisCache.get"]},
            ],
            "feature_relations": [
                {"from": "feat-user", "to": "feat-db", "relation_type": "static"},
                {"from": "feat-user", "to": "feat-redis", "relation_type": "static"},
            ],
        }
    }
    result = RelationCheck().check(llm_output, structure_json)
    # 兩條都被當錯誤：無法區分 ❌（真斷裂）與 ⚠（非程式碼節點）
    assert not result.passed
    assert len(result.errors) == 2
```

- [ ] **Step 2: 跑測試確認失敗（先確認 import 與抽取可運作）**

Run（cwd = `the_door/`）：
```bash
PYTHONUTF8=1 python -m pytest tests/spike/test_integration_gap_spike.py -v
```
Expected：能 import、能抽取。可能出現的失敗有兩種，需分辨：
- **預期內**：`test_three_way_verdict_matches_reality` 在控制組斷言失敗，**且** `assert db and user ...` 通過 → 代表抽取看得到節點，但 extractor **沒把控制組的跨模組呼叫連成 edge**。這是 spike 的真實發現（見 Task 4 判讀），不是程式 bug。
- **環境問題**：`ModuleNotFoundError` / 抽取丟例外 → 先修環境再續。

- [ ] **Step 3: 判讀並（必要時）校準檔名比對**

`_in_file` 以 `node_id` 的 `::` 左側 path 段 `endswith(檔名)` 比對。若 `assert db and user ...` 失敗，pytest assert 訊息已含 `sorted(nodes)`——確認真實 path 段（可能是相對/絕對/含子目錄）是否真的 `endswith` 那些檔名，必要時調整傳入的檔名字串。**不要**為了讓測試過而捏造 edges 或 nodes——一律來自真實抽取。

- [ ] **Step 4: 跑測試確認通過 / 或鎖定為 NO-GO 證據**

Run：
```bash
PYTHONUTF8=1 python -m pytest tests/spike/test_integration_gap_spike.py -v
```
Expected（GO 情形）：兩個測試皆 PASS → G2/G3 機制成立、且 RelationCheck 混淆已證實。
若控制組仍 `gap`（extractor 不出跨模組邊）→ 不改測試，保留為 **NO-GO 證據**，於 Task 5 報告如實記錄。

- [ ] **Step 5: Commit**

```bash
git add the_door/tests/spike/test_integration_gap_spike.py
git commit -m "test(spike): three-way integration verdict + RelationCheck conflation proof"
```

---

### Task 4: 真實抽取邊的判讀（決定 G2/G3 是否真的由真實結構支撐）

**Files:**
- 無新增檔案；本 Task 產生要寫進 Task 5 報告的觀察。

- [ ] **Step 1: 匯出真實抽取的邊供人工檢視**

新增一個**暫時**的診斷測試到 `test_integration_gap_spike.py` 末端：

```python
def test_dump_real_edges(capsys):
    """診斷用：印出真實抽取的 nodes/edges，供報告引用。永遠 PASS。"""
    nodes, edges = _extract()
    print("\n=== NODES ===")
    for n in sorted(nodes):
        print(n)
    print("=== EDGES ===")
    for e in edges:
        print(f'{e["from"]} -> {e["to"]}')
    assert True
```

Run：
```bash
PYTHONUTF8=1 python -m pytest tests/spike/test_integration_gap_spike.py::test_dump_real_edges -v -s
```
Expected：印出真實 node_id 與 edge 清單。

- [ ] **Step 2: 人工確認非對稱性**

從輸出確認兩件事，記到報告：
1. **斷裂方**：`UserService.*` 沒有任何路徑通到 `Database.*`（支撐 G2）。
2. **控制方**：`OrderService.* / ReportService.* / AuthService.*` 至少各有一條路徑通到 `Database.*`（支撐 G3）。

若 (2) 不成立（extractor 不解析跨模組呼叫）→ 結論為「The Door 現行抽取**尚不足以**支撐此支線」，屬 NO-GO 或「需先補 extractor」的設計輸入。

- [ ] **Step 3: 移除診斷測試並 commit**

刪掉 `test_dump_real_edges`（其輸出已抄進報告，留著會污染常規測試）。

```bash
git add the_door/tests/spike/test_integration_gap_spike.py
git commit -m "test(spike): drop diagnostic edge dump after capturing output"
```

---

### Task 5: 撰寫 go/no-go 報告

**Files:**
- Create: `docs/superpowers/specs/2026-06-19-integration-gap-spike-report.md`

- [ ] **Step 1: 寫報告**

```markdown
# 整合落差驗證 Spike — go/no-go 報告

對應 spec：`2026-06-19-integration-gap-verification-design.md`（§3.3 中心命題、§6 閘門）。
對應計畫：`../plans/2026-06-19-integration-gap-spike.md`。

## 閘門結果
| 閘門 | 結果 | 證據 |
|---|---|---|
| G2 真陽性（斷裂被標 ❌） | PASS / FAIL | test_three_way_verdict_matches_reality |
| G3 假陽性控制（N=3 全 ✅、外部 ⚠） | PASS / FAIL | 同上 |
| G4 非循環性（宣稱先於 edges 寫定） | PASS / FAIL | claims.md commit 早於 test commit |
| 設計輸入：RelationCheck 無法三態 | 確認 / 否 | test_relationcheck_alone_cannot_three_way |

## 真實抽取觀察（Task 4）
- 斷裂方 UserService → Database：<貼實際：有/無路徑>
- 控制方各服務 → Database：<貼實際邊>
- extractor 是否解析跨模組呼叫：<是/否，影響支線可行性>

## 結論
<GO ／ NO-GO ／ 需先補 extractor>。一句話理由。

## 若 GO，回填 spec 的未決項建議
- §5 D2/D4：<分類器三態 + 存在性前置檢查 的具體形狀>
- 下一步：進完整建置 writing-plans（D1/D3/D5 仍待使用者拍板）。
```

- [ ] **Step 2: 依實際測試結果填入 PASS/FAIL、貼上 Task 4 觀察、寫結論**

把上一步的 `<...>` 佔位全部換成實際結果。**不得**留任何 `<...>`。

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/specs/2026-06-19-integration-gap-spike-report.md
git commit -m "docs(spike): integration-gap verification go/no-go report"
```

- [ ] **Step 4: spike 產物去留決策（交還使用者）**

報告完成後，向使用者回報結論，並請其決定 `the_door/tests/spike/` 要：
（a）保留為迴歸測試（若 GO 並晉升為正式 fixture）、或（b）刪除（若 NO-GO）。**不自行刪除或晉升。**

---

## Self-Review

**1. Spec coverage（對 spec §6 閘門）：**
- G2 真陽性 → Task 3 `test_three_way_verdict_matches_reality`（user→db == "gap"）✓
- G3 假陽性 → 同測試（3 控制組 == "backed"、redis == "undetermined"）✓
- G4 非循環 → Task 2 claims.md 先於 Task 3 commit ✓
- 設計輸入（RelationCheck 無法三態）→ Task 3 `test_relationcheck_alone_cannot_three_way` ✓
- 真實結構支撐 → Task 4 邊判讀 ✓
- go/no-go 落檔 → Task 5 ✓

**2. Placeholder scan：** 計畫本身無 TBD/TODO。報告模板的 `<...>` 由 Task 5 Step 2 強制填實、並明令不得殘留——這是產物內容、非計畫佔位。✓

**3. Type/名稱一致性：**
- `ASTExtractor().extract(str)` → `result.nodes`（`.node_id`）/ `result.edges`（`.from_node`/`.to_node`）— 對齊 `models/extraction.py`。✓
- `RelationCheck().check(llm_output, structure_json)` → `CheckResult(passed, errors)`；`_has_path(set, set, adjacency)` — 對齊 `relation_check.py`。✓
- structure_json edges 用 `from/to` — 對齊 `structure_serializer.py:45`。✓
- 分類器三態字串 `"gap"/"backed"/"undetermined"` 全檔一致。✓

> **誠實邊界**：本 spike 的最大未知＝The Door 的 `ASTExtractor` 是否解析 fixture 的跨模組呼叫成 node-to-node edge。Task 3 Step 2／Task 4 已明確把「控制組無邊」判讀為**真實 NO-GO 證據**而非測試 bug——這正是 spike 該揭露的事，不是計畫缺陷。
