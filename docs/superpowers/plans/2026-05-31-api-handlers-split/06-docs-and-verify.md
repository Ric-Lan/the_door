# Phase 06 — 同源生成文件 + 最終驗收（Task 13–14）

> 讀本檔 + README 即可執行。前置：Phase 05 完成。

## Task 13: 兩份同源生成文件 + contract 測試

**Files:**
- Create: `the_door/src/the_door/core/ui/api/docgen.py`（從 ROUTES + ERROR_CODES 生成 markdown）
- Create: `the_door/src/the_door/core/ui/api/_gen_docs.py`（一次性生成腳本）
- Create: `docs/api/ai-agent-api-index.md`、`docs/api/error-codes.md`（生成產物）
- Test: `the_door/tests/unit/core/ui/api/test_docgen.py`

- [ ] **Step 1: 寫失敗測試（contract：文件涵蓋所有 route / 所有碼）**

```python
from pathlib import Path
from the_door.core.ui.api.docgen import render_api_index, render_error_codes
from the_door.core.ui.api.router import build_routes
from the_door.core.ui.api.context import APIContext
from the_door.core.ui.api.error_codes import ERROR_CODES
from the_door.core.ui.api.handlers.project import ProjectHandlers
from the_door.core.ui.api.handlers.analysis import AnalysisHandlers
from the_door.core.ui.api.handlers.catalog import CatalogHandlers
from the_door.core.ui.api.handlers.graph import GraphHandlers
from the_door.core.ui.api.handlers.diff import DiffHandlers
from the_door.core.ui.api.handlers.annotation import AnnotationHandlers

def _routes():
    ctx = APIContext(lambda: Path("."), lambda: None, lambda p, f: {})
    return build_routes(ProjectHandlers(ctx), AnalysisHandlers(ctx), CatalogHandlers(ctx),
                        GraphHandlers(ctx), DiffHandlers(ctx), AnnotationHandlers(ctx))

def test_api_index_covers_every_route():
    routes = _routes()
    md = render_api_index(routes)
    for rt in routes:
        assert rt.path in md and rt.summary in md

def test_error_doc_covers_every_code():
    md = render_error_codes(ERROR_CODES)
    for code, ec in ERROR_CODES.items():
        assert code in md and ec.desc in md

def test_every_route_summary_nonempty():
    for rt in _routes():
        assert rt.summary.strip()
```

- [ ] **Step 2: 跑測試確認 FAIL** — `cd the_door && python -m pytest tests/unit/core/ui/api/test_docgen.py -v`
- [ ] **Step 3: 實作 docgen.py**（`render_api_index(routes)`：快速索引表 method·path·summary·handler + 錯誤碼附錄；`render_error_codes(codes)`：code·http·file·desc 表）
- [ ] **Step 4: 跑測試確認 PASS** — `cd the_door && python -m pytest tests/unit/core/ui/api/test_docgen.py -v`
- [ ] **Step 5: 生成兩份文件**

新增 `the_door/src/the_door/core/ui/api/_gen_docs.py`：

```python
"""Generate the two API docs from ROUTES + ERROR_CODES. Run from the_door/."""
from pathlib import Path
from the_door.core.ui.api import docgen, error_codes
from the_door.core.ui.api.router import build_routes
from the_door.core.ui.api.context import APIContext
from the_door.core.ui.api.handlers.project import ProjectHandlers
from the_door.core.ui.api.handlers.analysis import AnalysisHandlers
from the_door.core.ui.api.handlers.catalog import CatalogHandlers
from the_door.core.ui.api.handlers.graph import GraphHandlers
from the_door.core.ui.api.handlers.diff import DiffHandlers
from the_door.core.ui.api.handlers.annotation import AnnotationHandlers

ctx = APIContext(lambda: Path("."), lambda: None, lambda p, f: {})
routes = build_routes(ProjectHandlers(ctx), AnalysisHandlers(ctx), CatalogHandlers(ctx),
                      GraphHandlers(ctx), DiffHandlers(ctx), AnnotationHandlers(ctx))
out = Path("../docs/api"); out.mkdir(parents=True, exist_ok=True)
(out / "ai-agent-api-index.md").write_text(docgen.render_api_index(routes), encoding="utf-8")
(out / "error-codes.md").write_text(docgen.render_error_codes(error_codes.ERROR_CODES), encoding="utf-8")
print("generated 2 docs")
```

Run: `cd the_door && PYTHONUTF8=1 python -m the_door.core.ui.api._gen_docs`
Expected: 印出 `generated 2 docs`，`docs/api/` 下出現兩檔。

- [ ] **Step 6: Commit**

```bash
cd the_door && git add src/the_door/core/ui/api/docgen.py src/the_door/core/ui/api/_gen_docs.py tests/unit/core/ui/api/test_docgen.py
cd .. && git add docs/api/ai-agent-api-index.md docs/api/error-codes.md
git commit -m "feat(api): doc generators + generated AI-agent API index & error-code catalog"
```

---

## Task 14: 最終驗收

- [ ] **Step 1: 兩道安全網 + 全套 + 覆蓋率**

Run: `cd the_door && PYTHONUTF8=1 python -m pytest --cov=the_door/core/ui/api --cov-report=term-missing -q`
Expected: 全 PASS；`api/` package 各檔 100% 覆蓋（缺口補測試）。

- [ ] **Step 2: 確認 server.py 已是純殼、舊類已除**

Run: `cd the_door && grep -rn "if path ==.*api\|elif path" src/the_door/core/ui/server.py`
Expected: 無大段 if-elif 路由（已由 router 取代）。

- [ ] **Step 3: 結構 diff 驗「只搬位置」**

啟 viewer 對 the_door 重抽取，確認拓樸語意一致（功能集合不因搬檔而少）。或人工核對 21 端點在 `build_routes` 齊全。

- [ ] **Step 4: 最終 commit（如有覆蓋補測）**

```bash
cd the_door && git add -A && git commit -m "test(api): close coverage gaps to 100% for api/ package"
```

---

## 完成後

對照 README 驗收清單逐項打勾。本刀完成且兩道安全網綠即可**獨立 merge**（不必等其他刀）。
