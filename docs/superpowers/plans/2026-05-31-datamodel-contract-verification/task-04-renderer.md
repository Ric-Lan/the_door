# Task 04 — 報告呈現（datamodel_renderer）

**內容分類：** 純呈現。定位圖文字（CLI 用）+ 契約 diff JSON（MCP 持久化用）。v1 **不做**人類可讀的契約 diff 文字（無消費者、YAGNI）。

**設計來源：** spec §4（輸出）、§8（持久化用 JSON）。依賴 Task 01。

**Files:**
- Create: `the_door/src/the_door/core/datamodel/datamodel_renderer.py`
- Create: `the_door/tests/unit/datamodel/test_renderer.py`

---

- [ ] **Step 1: 寫失敗測試**

`the_door/tests/unit/datamodel/test_renderer.py`：

```python
import json

from the_door.core.datamodel.models import (
    DataModelCandidate, DataModelLocalization, ContractEntry, ContractDiff,
)
from the_door.core.datamodel.datamodel_renderer import (
    render_localization, contract_diff_to_json,
)


def test_render_localization_with_candidates():
    loc = DataModelLocalization(
        code_candidates=(DataModelCandidate("m1", "models/u.py", "code_site", "name contains 'save'"),),
        schema_candidates=(DataModelCandidate("", "init.sql", "schema_file", "schema file (.sql)"),),
    )
    out = render_localization(loc)
    assert "Code candidates: 1" in out
    assert "m1" in out and "models/u.py" in out
    assert "Schema candidates: 1" in out
    assert "init.sql" in out


def test_render_localization_empty():
    out = render_localization(DataModelLocalization())
    assert "未偵測到資料模型觸點" in out


def test_contract_diff_to_json_roundtrip():
    diff = ContractDiff(entries=(
        ContractEntry("User", "name", "match", "declared and touched"),
    ))
    parsed = json.loads(contract_diff_to_json(diff))
    assert parsed["entries"][0] == {
        "entity": "User", "field": "name", "status": "match", "detail": "declared and touched",
    }
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `cd the_door && python -m pytest tests/unit/datamodel/test_renderer.py -q`
Expected: FAIL（`ModuleNotFoundError: ...datamodel_renderer`）。

- [ ] **Step 3: 實作 datamodel_renderer.py**

`the_door/src/the_door/core/datamodel/datamodel_renderer.py`：

```python
"""Rendering for data-model localization + contract diff (text + JSON)."""
from __future__ import annotations

import json

from the_door.core.datamodel.models import ContractDiff, DataModelLocalization


def render_localization(loc: DataModelLocalization) -> str:
    """Human-readable Tier 0 localization report."""
    lines = ["# Data-Model Localization (Tier 0)", ""]
    lines.append(f"Code candidates: {len(loc.code_candidates)}")
    for c in loc.code_candidates:
        lines.append(f"  - {c.node_id} ({c.file}) — {c.flagged_reason}")
    lines.append(f"Schema candidates: {len(loc.schema_candidates)}")
    for c in loc.schema_candidates:
        lines.append(f"  - {c.file} — {c.flagged_reason}")
    if not loc.code_candidates and not loc.schema_candidates:
        lines.append("")
        lines.append("未偵測到資料模型觸點。")
    return "\n".join(lines)


def contract_diff_to_json(diff: ContractDiff) -> str:
    """Serialize contract diff for persistence under .the-door/datamodel/."""
    return json.dumps(
        {
            "entries": [
                {"entity": e.entity, "field": e.field, "status": e.status, "detail": e.detail}
                for e in diff.entries
            ],
        },
        ensure_ascii=False,
        indent=2,
    )
```

- [ ] **Step 4: 跑測試確認通過 + 覆蓋率**

Run: `cd the_door && python -m pytest tests/unit/datamodel/test_renderer.py --cov=the_door.core.datamodel.datamodel_renderer --cov-report=term-missing -q`
Expected: PASS；datamodel_renderer.py **100%**。

- [ ] **Step 5: Commit**

```bash
cd the_door
git add src/the_door/core/datamodel/datamodel_renderer.py tests/unit/datamodel/test_renderer.py
git commit -m "feat(datamodel): localization + contract-diff renderers (text + json)"
```

## Done when
- [ ] 定位圖含計數 + 候選；空時印「未偵測到資料模型觸點」
- [ ] 契約 diff JSON 序列化結構正確（ensure_ascii=False）
- [ ] datamodel_renderer.py 覆蓋率 100%（僅 render_localization + contract_diff_to_json 兩函式）
