# Task 02 — Tier 0 定位器（DataModelLocalizer）

**內容分類：** 純結構定位。消費既有 `ExtractionResult`（程式碼候選）+ 走訪目錄找 schema 檔候選。**唯讀，不改 extraction。**

**設計來源：** spec §4（Tier 0）、§5。依賴 Task 01。

**Files:**
- Create: `the_door/src/the_door/core/datamodel/datamodel_localizer.py`
- Create: `the_door/tests/unit/datamodel/test_localizer.py`

---

- [ ] **Step 1: 寫失敗測試**

`the_door/tests/unit/datamodel/test_localizer.py`：

```python
from the_door.models import ASTNode, ExtractionResult
from the_door.core.datamodel.datamodel_localizer import DataModelLocalizer


def _node(node_id, name, file):
    return ASTNode(node_id=node_id, type="method", name=name, file=file, language="python")


def test_code_candidates_hit_and_miss(tmp_path):
    result = ExtractionResult(nodes=[
        _node("m1", "save_user", "svc/user.py"),        # name hit
        _node("m2", "render_page", "ui/view.py"),        # miss
        _node("m3", "load", "app/models/user.py"),       # dir hit
    ])
    loc = DataModelLocalizer().localize(result, str(tmp_path))
    ids = {c.node_id for c in loc.code_candidates}
    assert ids == {"m1", "m3"}
    assert all(c.kind == "code_site" for c in loc.code_candidates)


def test_schema_candidates_from_filesystem(tmp_path):
    (tmp_path / "init.sql").write_text("CREATE TABLE u(id int);", encoding="utf-8")
    (tmp_path / "seed.csv").write_text("id,name\n", encoding="utf-8")
    sub = tmp_path / "conf"
    sub.mkdir()
    (sub / "schema.json").write_text("{}", encoding="utf-8")
    (tmp_path / "package.json").write_text("{}", encoding="utf-8")  # miss

    loc = DataModelLocalizer().localize(ExtractionResult(nodes=[]), str(tmp_path))
    files = {c.file for c in loc.schema_candidates}
    assert files == {"init.sql", "seed.csv", "conf/schema.json"}
    assert all(c.kind == "schema_file" and c.node_id == "" for c in loc.schema_candidates)


def test_zero_hits(tmp_path):
    loc = DataModelLocalizer().localize(
        ExtractionResult(nodes=[_node("m9", "render", "ui/v.py")]), str(tmp_path))
    assert loc.code_candidates == ()
    assert loc.schema_candidates == ()
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `cd the_door && python -m pytest tests/unit/datamodel/test_localizer.py -q`
Expected: FAIL（`ModuleNotFoundError: ...datamodel_localizer`）。

- [ ] **Step 3: 實作 datamodel_localizer.py**

`the_door/src/the_door/core/datamodel/datamodel_localizer.py`：

```python
"""Tier 0 — pure-local structural localization of data-model touch points."""
from __future__ import annotations

import os
from pathlib import Path

from the_door.models import ExtractionResult
from the_door.core.datamodel.models import DataModelCandidate, DataModelLocalization
from the_door.core.datamodel.datamodel_hints import code_site_reason, schema_file_reason


class DataModelLocalizer:
    """Locate persistence-suspect code nodes + declared schema files. Zero token, read-only."""

    def localize(self, result: ExtractionResult, codebase_path: str) -> DataModelLocalization:
        code: list[DataModelCandidate] = []
        for node in result.nodes:
            reason = code_site_reason(node.name, node.file)
            if reason is not None:
                code.append(DataModelCandidate(
                    node_id=node.node_id, file=node.file,
                    kind="code_site", flagged_reason=reason,
                ))

        schema: list[DataModelCandidate] = []
        root = Path(codebase_path)
        for dirpath, _dirs, files in os.walk(root):
            for fname in files:
                rel = os.path.relpath(os.path.join(dirpath, fname), root)
                rel_norm = rel.replace("\\", "/")
                reason = schema_file_reason(rel_norm)
                if reason is not None:
                    schema.append(DataModelCandidate(
                        node_id="", file=rel_norm,
                        kind="schema_file", flagged_reason=reason,
                    ))

        return DataModelLocalization(
            code_candidates=tuple(code),
            schema_candidates=tuple(sorted(schema, key=lambda c: c.file)),
        )
```

- [ ] **Step 4: 跑測試確認通過 + 覆蓋率**

Run: `cd the_door && python -m pytest tests/unit/datamodel/test_localizer.py --cov=the_door.core.datamodel.datamodel_localizer --cov-report=term-missing -q`
Expected: PASS；datamodel_localizer.py **100%**。

- [ ] **Step 5: Commit**

```bash
cd the_door
git add src/the_door/core/datamodel/datamodel_localizer.py tests/unit/datamodel/test_localizer.py
git commit -m "feat(datamodel): Tier 0 localizer (code-site + schema-file candidates)"
```

## Done when
- [ ] 程式碼候選依 name/dir 啟發式正確命中、不命中者排除
- [ ] schema 檔候選由目錄走訪取得（`.sql`/`.csv`/schema-like `.json` 命中、`package.json` 不命中）
- [ ] 零命中時兩清單皆空
- [ ] datamodel_localizer.py 覆蓋率 100%
