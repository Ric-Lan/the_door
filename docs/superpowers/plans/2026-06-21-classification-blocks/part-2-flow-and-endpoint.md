# 功能分類層 — Part 2：流程指引 + endpoint

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 讓前端能讀到區塊資料（`GET /api/blocks`），並把分類流程寫進 agent 指引（CLAUDE.md + L1.5 prompt）。

**Architecture:** 新增 `BlockHandlers` 群組（對稱既有 `IntegrationHandlers`），讀當前快照的 `l1_5_snapshot` + `l1_snapshot` 組兩層樹回傳；分類流程沿用 version_narrative 形態寫進 guide，不新增工具。

**Tech Stack:** Python 3、既有 UI API router、Markdown

**Spec:** `docs/superpowers/specs/2026-06-21-feature-classification-blocks-design.md`（§6、§7）

**前置：** Part 1 完成（`BlockSummary` 新欄位、序列化、`snapshot_patch` blocks）。

---

## Task 1：`GET /api/blocks` endpoint

**Files:**
- Create: `the_door/src/the_door/core/ui/api/handlers/blocks.py`
- Modify: `the_door/src/the_door/core/ui/api/router.py:134`（build_routes 簽名 + Route）
- Modify: `the_door/src/the_door/core/ui/server.py:55-63`（呼叫加 BlockHandlers）
- Modify: `the_door/src/the_door/core/ui/api/_gen_docs.py:29-36`（同步加）
- Modify: `the_door/tests/unit/core/ui/api/test_docgen.py:14-18`（_routes helper 同步加，否則既有測試紅）
- Test: `the_door/tests/unit/core/ui/test_blocks_handler.py`（新檔）

- [ ] **Step 1：寫 failing test**

建 `the_door/tests/unit/core/ui/test_blocks_handler.py`（仿 `test_integration_handler.py`）：

```python
"""BlockHandlers.get_blocks：回兩層樹 + 成員；無 l1_5 回空；無快照 404。"""
import tempfile
from pathlib import Path

from the_door.core.diff.snapshot_store import SnapshotStore
from the_door.core.ui.api.context import APIContext
from the_door.core.ui.api.handlers.blocks import BlockHandlers
from the_door.models import BlockSummary, FeatureSummary


def _ctx(root):
    return APIContext(lambda: Path(root), lambda *_a, **_k: None)


def _seed(cp, with_blocks=True):
    store = SnapshotStore(Path(cp))
    blocks = {}
    if with_blocks:
        blocks = {
            "blk-top": BlockSummary("blk-top", "品質與安全群組說明", "把關品質"),
            "blk-leaf": BlockSummary(
                "blk-leaf", "輸出與範圍驗證子群組", "驗證輸出",
                related_features=("feat-a",), parent_block_id="blk-top",
            ),
            "blk-core": BlockSummary(
                "blk-core", "核心分析引擎群組說明", "抽取分析",
                related_features=("feat-b",), is_new_this_version=True,
            ),
        }
    return store.create_snapshot(
        l1_snapshot={
            "feat-a": FeatureSummary("feat-a", "輸出驗證", "驗證描述", 1, "high"),
            "feat-b": FeatureSummary("feat-b", "抽取", "抽取描述", 1, "medium"),
        },
        feature_relations=[], analyzed_files=[], trigger="manual", label="v1",
        l1_5_snapshot=blocks,
    )


def test_get_blocks_returns_tree():
    cp = tempfile.mkdtemp()
    snap = _seed(cp)
    status, body = BlockHandlers(_ctx(cp)).get_blocks(version_id=snap.version_id)
    assert status == 200
    by_id = {b["block_id"]: b for b in body["blocks"]}
    assert by_id["blk-leaf"]["parent_block_id"] == "blk-top"
    assert by_id["blk-leaf"]["features"][0]["feature_id"] == "feat-a"
    assert by_id["blk-leaf"]["features"][0]["confidence"] == "high"
    assert by_id["blk-core"]["is_new_this_version"] is True


def test_get_blocks_empty_when_no_l1_5():
    cp = tempfile.mkdtemp()
    snap = _seed(cp, with_blocks=False)
    status, body = BlockHandlers(_ctx(cp)).get_blocks(version_id=snap.version_id)
    assert status == 200
    assert body["blocks"] == []


def test_get_blocks_404_no_snapshot():
    cp = tempfile.mkdtemp()
    status, body = BlockHandlers(_ctx(cp)).get_blocks(version_id="missing")
    assert status == 404
```

- [ ] **Step 2：跑測試確認 fail**

Run: `python -m pytest tests/unit/core/ui/test_blocks_handler.py -v`
Expected: FAIL（`ModuleNotFoundError: handlers.blocks`）

- [ ] **Step 3：建 handler**

建 `the_door/src/the_door/core/ui/api/handlers/blocks.py`（照抄 integration handler 的取版本模式）：

```python
"""BlockHandlers — GET /api/blocks（讀當前快照的 L1.5 區塊樹，零 agent）。"""
from __future__ import annotations

from the_door.core.diff.snapshot_store import SnapshotStore
from the_door.core.guidance.remediation import Remediation, make_error_envelope
from the_door.core.ui.api.context import APIContext


class BlockHandlers:
    def __init__(self, ctx: APIContext) -> None:
        self._ctx = ctx

    def get_blocks(self, ctx=None, *, version_id=None, **_) -> tuple[int, dict]:
        """GET /api/blocks?version_id=<id> — 兩層區塊樹 + 每葉區塊成員。"""
        store = SnapshotStore(self._ctx.project_root)
        snapshot = store.get_snapshot(version_id) if version_id else store.get_latest()
        if snapshot is None:
            msg = (f"Snapshot '{version_id}' not found." if version_id
                   else "尚未為這個專案產出 L1 分析")
            return 404, make_error_envelope(
                code="no_block_data", message=msg,
                remediation=Remediation(code="no_block_data", message=msg),
                source="get_blocks",
            )
        feat = snapshot.l1_snapshot
        blocks = []
        for bid, b in snapshot.l1_5_snapshot.items():
            blocks.append({
                "block_id": b.block_id,
                "label": b.label,
                "responsibility": b.responsibility,
                "parent_block_id": b.parent_block_id,
                "is_new_this_version": b.is_new_this_version,
                "features": [
                    {
                        "feature_id": fid,
                        "label": feat[fid].label if fid in feat else fid,
                        "confidence": feat[fid].confidence if fid in feat else None,
                        "description": feat[fid].description if fid in feat else "",
                    }
                    for fid in b.related_features
                ],
            })
        return 200, {"blocks": blocks}
```

- [ ] **Step 4：wire 進 router + server + docgen**

`router.py:134` 簽名加 `bl`，並在 `/api/integration` 那筆 Route 之後加一筆：

```python
def build_routes(p, c, g, d, n, gr, ig, bl) -> list[Route]:
```
```python
        Route("GET",  "/api/blocks",                              bl.get_blocks, summary="當前版本的功能分類區塊樹（最多兩層）"),
```

`server.py:55-63` 的 `build_routes(...)` 呼叫，在 `IntegrationHandlers(ctx),` 後加 `BlockHandlers(ctx),`，並在檔頭 import 區（緊接 `from ...handlers.integration import IntegrationHandlers`，第 26 行）加：

```python
from the_door.core.ui.api.handlers.blocks import BlockHandlers
```

`_gen_docs.py:29-36` 的 `build_routes(...)` 與 import 做相同兩處同步修改（否則 docgen 會因參數數不符而壞）。

**同步測試 helper（重要，否則既有 docgen 測試紅）**：`tests/unit/core/ui/api/test_docgen.py` 的
`_routes()`（14-18）也呼叫 `build_routes`——這是 `build_routes` 的**第三個呼叫點**。同步：
import 區（11 之後）加 `from the_door.core.ui.api.handlers.blocks import BlockHandlers`；
`_routes()` 的 `build_routes(...)` 末加 `BlockHandlers(ctx)`。
（`test_api_index_covers_every_route` 遍歷 routes 斷言 path+summary 出現在產出，會**自動涵蓋**
`/api/blocks`，無需另寫測試。）

- [ ] **Step 5：跑測試確認 pass + 回歸**

Run: `python -m pytest tests/unit/core/ui/ -v`
Expected: PASS（新 test_blocks_handler + 既有 UI 測試含 api/test_docgen 全綠；
test_docgen 的 test_api_index_covers_every_route 自動驗證 /api/blocks 入列）

- [ ] **Step 6：Commit**

```bash
git add the_door/src/the_door/core/ui/api/handlers/blocks.py the_door/src/the_door/core/ui/api/router.py the_door/src/the_door/core/ui/server.py the_door/src/the_door/core/ui/api/_gen_docs.py the_door/tests/unit/core/ui/test_blocks_handler.py
git commit -m "feat(ui): add GET /api/blocks endpoint for classification tree"
```

---

## Task 2：CLAUDE.md 加分類流程指引

**Files:**
- Modify: `CLAUDE.md`（在 `## Snapshot reference formats` 之前插入）

- [ ] **Step 1：插入 agent-as-LLM 分類流程段**

用 Edit 工具，`old_string` 精確匹配：

```
## Snapshot reference formats
```

`new_string`（新段 + 原標題）：

````
### Agent-as-LLM chain (feature classification / L1.5 blocks)

把已翻譯的 L1 功能歸類成「最多兩層」的區塊（block），存進快照、給 viewer 折疊。
**不需新工具**——你自己讀功能、自己分類、用 `snapshot_patch` 寫回（同 version_narrative 形態）。

1. 讀 current snapshot 的 `l1_snapshot`（功能）。
   - 冷啟動第一版：自己把功能分區塊。
   - 後續版本：先 `analyze_changes(baseline=...)` 取 `inherited_features`/`affected_features`，
     讀 baseline 的 `l1_5_snapshot` 當沿用基礎——inherited 維持原歸屬、affected/新功能歸入
     既有區塊、真的塞不進才自動開新區塊並標 `is_new_this_version=true`。
2. **硬性原則**（`snapshot_patch` 寫入時驗證，不過則整批拒）：
   - 最多兩層（`parent_block_id` 指向的區塊本身須是頂層）
   - 單一歸屬（每個功能恰好歸一個區塊）
   - 功能只掛葉區塊（有子區塊者 `related_features` 必為空）
   - 窮盡（每個功能都要有歸屬；沒分到的放兜底區塊 `blk-unclassified`）
   - 交叉引用（`related_features` / `parent_block_id` 都要存在）
3. **軟性原則**（靠你自律、非 gate）：歸類照功能語意；區塊 label 用白話短語、禁裸技術術語；
   沿用既有區塊名、不每版重洗。
4. **冷啟動互動確認**：第一版分類**先把區塊樹呈現給使用者、得到同意才寫**
   （同 version_narrative「先聲明再執行」）。使用者可先提供偏好區塊表當種子。
   後續版本自動開新類不打擾、靠 `is_new_this_version` 留痕。
5. `snapshot_patch(codebase_path, version_ref, blocks={block_id: {label, responsibility,
   related_features, parent_block_id?, is_new_this_version?}})`。`blocks` 為**整批取代**——
   re-patch 要帶齊所有區塊（含繼承的）。

## Snapshot reference formats
````

- [ ] **Step 2：目視確認（Read 工具，非 cat）**

用 Read 工具讀 `CLAUDE.md` 對應段落，確認新段在 `## Snapshot reference formats` 之前、
措辭完整無截斷。

- [ ] **Step 3：Commit**

```bash
git add CLAUDE.md
git commit -m "docs(guide): add feature-classification agent-as-LLM chain"
```

---

## Task 3：更新 L1.5 prompt

**Files:**
- Modify: `the_door/prompts/l1-5-constraint.md`（整檔重寫）

原 prompt 含本 spec 不啟用的 `trigger_mechanism` / `block_relations` / `infrastructure_block`，
且只有單層。重寫為兩層 + 沿用 + 標記、移除不啟用欄位。

- [ ] **Step 1：整檔重寫**

把 `the_door/prompts/l1-5-constraint.md` 內容整個替換為：

```markdown
# L1.5 Constraint Prompt — 功能分類（區塊）

## 目的

把已翻譯的 L1 功能歸類成「最多兩層」的區塊（block），介於單一功能（L1）與模組互動（L2）
之間。分類由你（agent-as-LLM）親自做；工具只在寫入時驗結構。

## 輸出（傳給 snapshot_patch 的 blocks）

```json
{
  "blk-core-engine": {
    "label": "模組名＋功能描述（禁裸術語，需功能語境）",
    "responsibility": "這個區塊在系統中負責什麼",
    "related_features": ["feat-id-1", "feat-id-2"],
    "parent_block_id": null,
    "is_new_this_version": false
  },
  "blk-quality": {
    "label": "品質與安全功能群組",
    "responsibility": "把關輸出品質與依賴安全",
    "related_features": [],
    "parent_block_id": null
  },
  "blk-validation": {
    "label": "輸出與範圍驗證子群組",
    "responsibility": "驗證 agent 產出與分析範圍",
    "related_features": ["feat-output-validation", "feat-scope-doubt"],
    "parent_block_id": "blk-quality"
  }
}
```

## 硬性規則（snapshot_patch 寫入時驗、不過則整批拒）

- **最多兩層**：`parent_block_id` 指向的區塊本身必須是頂層（其 `parent_block_id` 為 null）。
- **單一歸屬**：每個 `feature_id` 只能出現在一個區塊的 `related_features`。
- **功能只掛葉區塊**：有子區塊的區塊，`related_features` 必須為空（功能掛在最底層）。
- **窮盡**：每個 L1 功能都要有歸屬；沒分到的放兜底區塊 `blk-unclassified`。
- **交叉引用**：`related_features` 的 id 都要存在於 L1；`parent_block_id` 指向的區塊要存在。

## 軟性規則（靠自律）

- 依**功能語意**歸類，不是依檔案路徑。
- `label` 用白話短語、禁裸技術術語（如單獨的 "Controller"）；需帶功能語境。
- **沿用既有**：後續版本先讀 baseline 的區塊，新功能優先塞既有區塊；真的塞不進才開新類、
  標 `is_new_this_version: true`，不每版重洗。

## 深度自適應

不設區塊數量上限。小專案可能全是頂層區塊（單層）；大專案才把過大的頂層區塊展開出子區塊
（第二層）。是否展開第二層由功能多寡與可讀性決定，不固定。
```

- [ ] **Step 2：Commit**

```bash
git add the_door/prompts/l1-5-constraint.md
git commit -m "docs(prompt): rewrite L1.5 constraint for two-level classification"
```

---

## Part 2 Self-Review

- [x] **Spec coverage**：§7 endpoint(T1)；§6 流程指引 guide(T2)/prompt(T3)。
  §6 `inherit_from` 繼承 l1_5 為可延後最佳化，放 Part 後續（spec §12 第 6），本 Part 不含。
- [x] **Placeholder scan**：無 TBD/TODO；endpoint code、guide、prompt 皆完整。
- [x] **Type consistency**：`BlockHandlers.get_blocks`、`build_routes(p,c,g,d,n,gr,ig,bl)`、
  payload 欄位（block_id/label/responsibility/parent_block_id/is_new_this_version/features[]）
  與 Part 1 的 `BlockSummary` 欄位、Part 3 前端讀取一致。
