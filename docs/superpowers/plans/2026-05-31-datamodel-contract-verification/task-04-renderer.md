# Task 04 — 報告呈現（datamodel_renderer）

**內容分類：** 純呈現。定位圖文字、契約 diff 文字 + 摘要計數、契約 diff JSON。摘要**衍生不存欄位**（spec §6）。

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
    render_localization, render_contract_diff, contract_diff_to_json,
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


def test_render_contract_diff_counts():
    diff = ContractDiff(entries=(
        ContractEntry("User", "email", "write_gap", "x"),
        ContractEntry("User", "id", "coverage_gap", "y"),
        ContractEntry("User", "name", "match", "z"),
    ))
    out = render_contract_diff(diff)
    assert "write_gap=1" in out and "coverage_gap=1" in out and "match=1" in out
    assert "[write_gap] User.email" in out


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


def render_contract_diff(diff: ContractDiff) -> str:
    """Human-readable Tier 1 contract diff with derived summary counts."""
    counts = {"write_gap": 0, "coverage_gap": 0, "match": 0}
    for e in diff.entries:
        counts[e.status] += 1
    lines = ["# Data-Model Contract Diff (Tier 1)", ""]
    lines.append(
        f"write_gap={counts['write_gap']} "
        f"coverage_gap={counts['coverage_gap']} match={counts['match']}"
    )
    for e in diff.entries:
        lines.append(f"  [{e.status}] {e.entity}.{e.field} — {e.detail}")
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

Run: `cd the_door && python -m pytest tests/unit/datamodel/test_renderer.py --cov=the_door/src/the_door/core/datamodel/datamodel_renderer.py --cov-report=term-missing -q`
Expected: PASS；datamodel_renderer.py **100%**。

- [ ] **Step 5: Commit**

```bash
cd the_door
git add src/the_door/core/datamodel/datamodel_renderer.py tests/unit/datamodel/test_renderer.py
git commit -m "feat(datamodel): localization + contract-diff renderers (text + json)"
```

## Done when
- [ ] 定位圖含計數 + 候選；空時印「未偵測到資料模型觸點」
- [ ] 契約 diff 摘要計數正確衍生、條目可讀
- [ ] JSON 序列化結構正確（ensure_ascii=False）
- [ ] datamodel_renderer.py 覆蓋率 100%
