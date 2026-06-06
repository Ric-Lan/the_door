"""report 面的 agent 邊界膜投影 APPLIER（非軸詞彙來源——CONTRASTS 住 diff/scope_membrane）。

把 render_json（人類/persisted bare 報告）的已知 enum 欄在 agent 消費邊界投影為膜
{value, position}，不動 render_json 本身（人類/viewer/CLI/schema/frontend JS 全保持 bare）。
複用 diff_membrane（change_type=4-val／diff_state node5/edge3）＋scope_membrane（scope 可空）。
膜＝emission 邊界投影（§8.12），此處 emission 邊界＝agent 讀共用 renderer。
"""
from __future__ import annotations

import copy

from the_door.core.diff.diff_membrane import (
    change_type_element,
    edge_diff_element,
    node_diff_element,
)
from the_door.core.scope.scope_membrane import scope_element_or_indeterminate


def project_report_for_agent(report: dict) -> dict:
    """深拷貝 report、就地把已知 enum 軸欄升膜投影。純函式、不改入參。"""
    r = copy.deepcopy(report)

    for e in r.get("l1_changes", []):
        if "change_type" in e:
            e["change_type"] = change_type_element(e["change_type"]).to_json()

    for d in r.get("l2_details", []):
        if "change_type" in d:
            d["change_type"] = change_type_element(d["change_type"]).to_json()
        if "scope_state" in d:
            d["scope_state"] = scope_element_or_indeterminate(d["scope_state"]).to_json()

    appendix = r.get("l3_appendix") or {}
    diff_json = appendix.get("diff_result_json") or {}
    for nd in diff_json.get("node_diffs", []):
        if "diff_state" in nd:
            nd["diff_state"] = node_diff_element(nd["diff_state"]).to_json()
    for ed in diff_json.get("edge_diffs", []):
        if "diff_state" in ed:
            ed["diff_state"] = edge_diff_element(ed["diff_state"]).to_json()

    scope_json = appendix.get("scope_result_json") or {}
    for entry in scope_json.get("entries", []):
        if "scope_state" in entry:
            entry["scope_state"] = scope_element_or_indeterminate(entry["scope_state"]).to_json()

    return r
