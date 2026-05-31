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
