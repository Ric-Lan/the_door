# Phase 03 — 6 領域 handler 提取（Task 5–10）

> **執行前必讀 README 的「共用：領域 handler 搬移做法 + 精確簽名表」一節**——搬移轉換規則與每個方法的具名參數簽名都在那；本檔不重複，只列各 handler 的搬移來源與步驟。
> 6 個 handler 彼此獨立，可任意序或並行。每個完成即 commit。舊 `api_handlers.py` 全程保留（Phase 05 才刪）。

---

## Task 5: ProjectHandlers

**Files:**
- Create: `the_door/src/the_door/core/ui/api/handlers/__init__.py`（空）
- Create: `the_door/src/the_door/core/ui/api/handlers/project.py`
- Test: `the_door/tests/unit/core/ui/api/handlers/test_project.py`

**搬移來源（api_handlers.py 行）:** `handle_get_project`(104) → `get`、`handle_post_set_project`(328) → `set_project`、`handle_get_status`(615) → `status`。

- [ ] **Step 1: 寫失敗測試**（搬 `test_api_handlers.py` / `test_api_handlers_set_project.py` 中 project/status/set-project 相關斷言；建構用 APIContext）

```python
from pathlib import Path
from the_door.core.ui.api.context import APIContext
from the_door.core.ui.api.handlers.project import ProjectHandlers
from the_door.core.ui.job_store import JobStore

def _ctx(tmp_path):
    return APIContext(lambda: tmp_path, lambda: JobStore(), lambda p, f: {"status": "ok"})

def test_get_project_uninitialized(tmp_path):
    h = ProjectHandlers(_ctx(tmp_path))
    status, body = h.get()
    assert status == 200
    assert "project_path" in body
# …status / set_project 各補（沿用舊斷言）
```

- [ ] **Step 2: 跑測試確認 FAIL** — `cd the_door && python -m pytest tests/unit/core/ui/api/handlers/test_project.py -v`（FAIL：module 不存在）
- [ ] **Step 3: 實作 project.py** — 依 README 共通做法搬 3 個方法體 + ctx 轉換。class 殼：

```python
"""Project lifecycle handlers: current project, switch, status."""
from the_door.core.ui.api.context import APIContext

class ProjectHandlers:
    def __init__(self, ctx: APIContext) -> None:
        self._ctx = ctx

    def get(self, ctx=None, *, body=None, **_):
        ...  # 搬 handle_get_project 體，self._project_root → self._ctx.project_root
    def set_project(self, ctx=None, *, body=None, **_):
        ...  # 搬 handle_post_set_project；self._switch_project_fn → self._ctx.switch_project
    def status(self, ctx=None, *, body=None, **_):
        ...  # 搬 handle_get_status
```

- [ ] **Step 4: 跑測試確認 PASS** — `cd the_door && python -m pytest tests/unit/core/ui/api/handlers/test_project.py -v`
- [ ] **Step 5: Commit** — `cd the_door && git add src/the_door/core/ui/api/handlers/__init__.py src/the_door/core/ui/api/handlers/project.py tests/unit/core/ui/api/handlers/test_project.py && git commit -m "feat(api): extract ProjectHandlers"`

---

## Task 6: AnalysisHandlers

**Files:** Create `handlers/analysis.py`；Test `handlers/test_analysis.py`
**搬移來源:** `handle_post_analyze`(275) → `analyze`、`handle_post_update`(194) → `update`、`handle_get_update_status`(361) → `update_status`。
**注意:** 這些走 async job（用 `self._ctx.job_store`）；行為不變，job 啟動邏輯原樣搬。簽名：`analyze`/`update` 收 `body`；`update_status` 收 `job_id`（見 README 簽名表）。

- [ ] **Step 1: 寫失敗測試**（搬 `test_api_handlers_analyze.py` 斷言；建構用 APIContext，含 job_store）
- [ ] **Step 2: 跑測試確認 FAIL** — `cd the_door && python -m pytest tests/unit/core/ui/api/handlers/test_analysis.py -v`
- [ ] **Step 3: 實作 analysis.py**（class `AnalysisHandlers(ctx)`，搬 3 方法 + ctx 轉換）
- [ ] **Step 4: 跑測試確認 PASS**
- [ ] **Step 5: Commit** — `... && git commit -m "feat(api): extract AnalysisHandlers"`

---

## Task 7: CatalogHandlers

**Files:** Create `handlers/catalog.py`；Test `handlers/test_catalog.py`
**搬移來源:** `handle_get_snapshots`(148) → `snapshots`、`handle_get_timeline`(406) → `timeline`、`handle_get_report_latest`(165) → `report_latest`。簽名：三者皆無具名參數。

- [ ] **Step 1: 寫失敗測試**（snapshots/timeline/report-latest 斷言）
- [ ] **Step 2: 跑測試確認 FAIL** — `cd the_door && python -m pytest tests/unit/core/ui/api/handlers/test_catalog.py -v`
- [ ] **Step 3: 實作 catalog.py**（class `CatalogHandlers(ctx)`，搬 3 方法）
- [ ] **Step 4: 跑測試確認 PASS**
- [ ] **Step 5: Commit** — `... && git commit -m "feat(api): extract CatalogHandlers"`

---

## Task 8: GraphHandlers

**Files:** Create `handlers/graph.py`；Test `handlers/test_graph.py`
**搬移來源:** `handle_get_l1`(425) → `get_l1`、`handle_get_l2`(628) → `get_l2`、`handle_post_l2_generate`(651) → `generate_l2`、`handle_get_structure`(766) → `get_structure`、`handle_get_layer_explanation`(695) → `get_layer_explanation`、`handle_post_layer_explanation_generate`(734) → `generate_layer_explanation`。
**注意:** generate 類用 `create_provider(config)`（需 API key 路徑）；行為不變，原樣搬。簽名見 README 簽名表（get_l1: `version_id`；l2/structure/layer-explanation 各自的 path 參數）。

- [ ] **Step 1: 寫失敗測試**（搬 `test_api_handlers_ui3.py` 的 l1/l2/structure/layer-explanation 斷言）
- [ ] **Step 2: 跑測試確認 FAIL** — `cd the_door && python -m pytest tests/unit/core/ui/api/handlers/test_graph.py -v`
- [ ] **Step 3: 實作 graph.py**（class `GraphHandlers(ctx)`，搬 6 方法 + ctx 轉換）
- [ ] **Step 4: 跑測試確認 PASS**
- [ ] **Step 5: Commit** — `... && git commit -m "feat(api): extract GraphHandlers"`

---

## Task 9: DiffHandlers

**Files:** Create `handlers/diff.py`；Test `handlers/test_diff.py`
**搬移來源:** `handle_diff_versions`(508) → `versions`、`handle_get_diff_explanation`(889) → `get_explanation`、`handle_post_diff_explanation_generate`(913) → `generate_explanation`。
**注意:** `versions` 從 query 取 `baseline`/`current`，**搬入後須加 `baseline_id, current_id = baseline, current`**（見 README 簽名表）；缺參數回 `missing_params`。

- [ ] **Step 1: 寫失敗測試**（搬 `test_api_handlers_diff_explanation.py` 斷言 + diff versions 缺參數 400）
- [ ] **Step 2: 跑測試確認 FAIL** — `cd the_door && python -m pytest tests/unit/core/ui/api/handlers/test_diff.py -v`
- [ ] **Step 3: 實作 diff.py**（class `DiffHandlers(ctx)`，搬 3 方法；`versions(self, ctx=None, *, body=None, baseline=None, current=None, **_)`）
- [ ] **Step 4: 跑測試確認 PASS**
- [ ] **Step 5: Commit** — `... && git commit -m "feat(api): extract DiffHandlers"`

---

## Task 10: AnnotationHandlers

**Files:** Create `handlers/annotation.py`；Test `handlers/test_annotation.py`
**搬移來源:** `handle_get_notes`(1130) → `get_notes`、`handle_post_notes`(1172) → `post_notes`、`handle_get_doubts`(387) → `doubts`。
**注意:** `get_notes` 收 query（`mode`/`feature_id`/`version_a`/`version_b`）；`post_notes` 收 `body`；`doubts` 無參數（見 README 簽名表）。

- [ ] **Step 1: 寫失敗測試**（搬 `test_api_handlers_notes.py` + doubts 斷言）
- [ ] **Step 2: 跑測試確認 FAIL** — `cd the_door && python -m pytest tests/unit/core/ui/api/handlers/test_annotation.py -v`
- [ ] **Step 3: 實作 annotation.py**（class `AnnotationHandlers(ctx)`，搬 3 方法）
- [ ] **Step 4: 跑測試確認 PASS**
- [ ] **Step 5: Commit** — `... && git commit -m "feat(api): extract AnnotationHandlers"`
