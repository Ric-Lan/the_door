# Task 03 — Tier 1 雙向契約 diff（ContractVerifier）

**內容分類：** 純結構欄位集 diff。與 L1 diff 同肌肉但不同資料形狀，**故獨立、不混進 `diff_engine`**（spec §5）。

**設計來源：** spec §1（三類落差）、§4（Tier 1）。依賴 Task 01。

**Files:**
- Create: `the_door/src/the_door/core/datamodel/contract_verifier.py`
- Create: `the_door/tests/unit/datamodel/test_contract_verifier.py`

---

- [ ] **Step 1: 寫失敗測試**

`the_door/tests/unit/datamodel/test_contract_verifier.py`：

```python
from the_door.core.datamodel.models import DeclaredField, CodeTouch
from the_door.core.datamodel.contract_verifier import ContractVerifier


def _status_map(diff):
    return {(e.entity, e.field): e.status for e in diff.entries}


def test_match_write_gap_coverage_gap():
    declared = {"User": [DeclaredField("id"), DeclaredField("name")]}
    touched = [CodeTouch(op="write", entity="User", fields=("name", "email"))]
    diff = ContractVerifier().verify(declared, touched)
    sm = _status_map(diff)
    assert sm[("User", "name")] == "match"
    assert sm[("User", "email")] == "write_gap"      # code writes undeclared field
    assert sm[("User", "id")] == "coverage_gap"        # declared, never touched


def test_entity_only_declared_and_only_touched():
    declared = {"Order": [DeclaredField("total")]}
    touched = [CodeTouch(op="read", entity="Cart", fields=("count",))]
    diff = ContractVerifier().verify(declared, touched)
    sm = _status_map(diff)
    assert sm[("Order", "total")] == "coverage_gap"
    assert sm[("Cart", "count")] == "write_gap"


def test_empty_inputs():
    diff = ContractVerifier().verify({}, [])
    assert diff.entries == ()


def test_multiple_touches_same_entity_union_fields():
    declared = {"User": [DeclaredField("a")]}
    touched = [
        CodeTouch(op="write", entity="User", fields=("a",)),
        CodeTouch(op="read", entity="User", fields=("b",)),
    ]
    sm = _status_map(ContractVerifier().verify(declared, touched))
    assert sm[("User", "a")] == "match"
    assert sm[("User", "b")] == "write_gap"


def test_entries_deterministic_order():
    declared = {"B": [DeclaredField("y")], "A": [DeclaredField("x")]}
    diff = ContractVerifier().verify(declared, [])
    entities = [e.entity for e in diff.entries]
    assert entities == sorted(entities)  # entity 排序穩定
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `cd the_door && python -m pytest tests/unit/datamodel/test_contract_verifier.py -q`
Expected: FAIL（`ModuleNotFoundError: ...contract_verifier`）。

- [ ] **Step 3: 實作 contract_verifier.py**

`the_door/src/the_door/core/datamodel/contract_verifier.py`：

```python
"""Tier 1 — bidirectional field-set contract diff (declared vs code-touched).

刻意不併入 diff_engine：資料形狀（欄位集）與 L1 feature diff 不同，混入會膨脹。
"""
from __future__ import annotations

from the_door.core.datamodel.models import (
    ContractDiff, ContractEntry, DeclaredField, CodeTouch,
)


class ContractVerifier:
    """Compare an agent-normalized declared model vs code-touched model."""

    def verify(
        self,
        declared: dict[str, list[DeclaredField]],
        code_touched: list[CodeTouch],
    ) -> ContractDiff:
        declared_map: dict[str, set[str]] = {
            entity: {f.field for f in fields}
            for entity, fields in declared.items()
        }
        touched_map: dict[str, set[str]] = {}
        for touch in code_touched:
            touched_map.setdefault(touch.entity, set()).update(touch.fields)

        entries: list[ContractEntry] = []
        for entity in sorted(set(declared_map) | set(touched_map)):
            declared_fields = declared_map.get(entity, set())
            touched_fields = touched_map.get(entity, set())
            for field in sorted(touched_fields - declared_fields):
                entries.append(ContractEntry(
                    entity=entity, field=field, status="write_gap",
                    detail="code touches a field not in declared schema",
                ))
            for field in sorted(declared_fields - touched_fields):
                entries.append(ContractEntry(
                    entity=entity, field=field, status="coverage_gap",
                    detail="declared field never touched by code",
                ))
            for field in sorted(declared_fields & touched_fields):
                entries.append(ContractEntry(
                    entity=entity, field=field, status="match",
                    detail="declared and touched",
                ))
        return ContractDiff(entries=tuple(entries))
```

- [ ] **Step 4: 跑測試確認通過 + 覆蓋率**

Run: `cd the_door && python -m pytest tests/unit/datamodel/test_contract_verifier.py --cov=the_door.core.datamodel.contract_verifier --cov-report=term-missing -q`
Expected: PASS；contract_verifier.py **100%**。

- [ ] **Step 5: Commit**

```bash
cd the_door
git add src/the_door/core/datamodel/contract_verifier.py tests/unit/datamodel/test_contract_verifier.py
git commit -m "feat(datamodel): Tier 1 bidirectional contract verifier"
```

## Done when
- [ ] write_gap / coverage_gap / match 三類分類正確
- [ ] entity 只存在單側、多 touch 併集、空輸入、entity 排序穩定皆涵蓋
- [ ] contract_verifier.py 覆蓋率 100%
