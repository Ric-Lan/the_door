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
