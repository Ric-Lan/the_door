"""S8-report unit：agent 邊界投影器 project_report_for_agent（applier、非詞彙來源）。

對應 spec §4 R1（各軸欄升膜＋無殘留 bare）／R5（純函式、不改入參、防呆）。
"""
from __future__ import annotations

import copy

from the_door.core.diff.diff_membrane import CHANGE_TYPE_CONTRASTS
from the_door.core.pipeline.report_membrane import project_report_for_agent


def _sample_report() -> dict:
    """涵蓋全已知軸欄的 render_json 形狀 report（bare）。"""
    return {
        "report_version": "1.0.0",
        "l1_changes": [
            {"feature_id": "f1", "change_type": "added", "risk_flags": [], "current_label": "F1", "baseline_label": None},
            {"feature_id": "f2", "change_type": "attribute_changed", "risk_flags": ["out_of_scope", "vulnerability"], "current_label": "F2", "baseline_label": "F2"},
        ],
        "l2_details": [
            {"feature_id": "f1", "change_type": "attribute_changed", "scope_state": "in_scope_complete"},
            {"feature_id": "f2", "change_type": "dependency_changed", "scope_state": None},  # 可空
        ],
        "l3_appendix": {
            "diff_result_json": {
                "node_diffs": [{"node_id": "f1", "diff_state": "added"}],
                "edge_diffs": [{"from_node": "f1", "to_node": "f2", "diff_state": "modified"}],
            },
            "scope_result_json": {
                "scope_name": "s",
                "entries": [{"feature_id": "f1", "scope_state": "out_of_scope"}],
            },
        },
    }


def _is_membrane(v) -> bool:
    return isinstance(v, dict) and "value" in v and "position" in v


def test_change_type_projected_with_change_type_contrasts():
    r = project_report_for_agent(_sample_report())
    ct = r["l1_changes"][0]["change_type"]
    assert _is_membrane(ct)
    assert ct["value"] == "added"
    assert ct["position"]["kind"] == "signal"
    assert ct["position"]["contrasts"] == list(CHANGE_TYPE_CONTRASTS)  # 4-set，非 node 5-set
    assert r["l2_details"][0]["change_type"]["position"]["contrasts"] == list(CHANGE_TYPE_CONTRASTS)


def test_scope_state_signal_and_none_noise():
    r = project_report_for_agent(_sample_report())
    s_signal = r["l2_details"][0]["scope_state"]
    assert _is_membrane(s_signal) and s_signal["position"]["kind"] == "signal"
    s_none = r["l2_details"][1]["scope_state"]
    assert _is_membrane(s_none) and s_none["value"] is None
    assert s_none["position"]["kind"] == "noise" and s_none["position"]["gap_kind"] == "indeterminate"


def test_diff_result_and_scope_result_projected():
    r = project_report_for_agent(_sample_report())
    dj = r["l3_appendix"]["diff_result_json"]
    assert _is_membrane(dj["node_diffs"][0]["diff_state"])
    assert len(dj["node_diffs"][0]["diff_state"]["position"]["contrasts"]) == 5  # node 5-set
    assert _is_membrane(dj["edge_diffs"][0]["diff_state"])
    assert len(dj["edge_diffs"][0]["diff_state"]["position"]["contrasts"]) == 3  # edge 3-set
    sj = r["l3_appendix"]["scope_result_json"]
    assert _is_membrane(sj["entries"][0]["scope_state"])


def test_no_bare_enum_axis_field_remains():
    """R1 完整性釘樁：投影後所有已知軸欄皆 dict、無殘留 bare str。"""
    r = project_report_for_agent(_sample_report())
    for e in r["l1_changes"]:
        assert _is_membrane(e["change_type"])
    for d in r["l2_details"]:
        assert _is_membrane(d["change_type"])
        assert _is_membrane(d["scope_state"])
    dj = r["l3_appendix"]["diff_result_json"]
    for nd in dj["node_diffs"]:
        assert _is_membrane(nd["diff_state"])
    for ed in dj["edge_diffs"]:
        assert _is_membrane(ed["diff_state"])
    for entry in r["l3_appendix"]["scope_result_json"]["entries"]:
        assert _is_membrane(entry["scope_state"])


def test_pure_function_does_not_mutate_input():
    """R5：深拷貝、入參不被改。"""
    original = _sample_report()
    snapshot = copy.deepcopy(original)
    project_report_for_agent(original)
    assert original == snapshot  # 入參逐欄不變（change_type 仍 bare str）


def test_missing_keys_do_not_crash():
    """R5：缺 l2_details / 缺 l3_appendix / appendix 為 None 皆防呆。"""
    assert project_report_for_agent({}) == {}
    assert "l3_appendix" not in project_report_for_agent({"l1_changes": []})
    project_report_for_agent({"l3_appendix": None})  # 不炸
    project_report_for_agent({"l3_appendix": {}})  # 不炸


def test_risk_flags_projected_present_subset():
    """P4：present 旗標升膜＝presence_flag、value＝present 子集、vocabulary 全曝。"""
    r = project_report_for_agent(_sample_report())
    rf = r["l1_changes"][1]["risk_flags"]
    assert _is_membrane(rf)
    assert rf["position"]["kind"] == "presence_flag"
    assert rf["value"] == ["out_of_scope", "vulnerability"]
    assert len(rf["position"]["vocabulary"]) == 3  # 封閉 3-詞彙全曝


def test_risk_flags_empty_still_exposes_vocabulary():
    """P4：空 risk_flags → value:[]＋vocabulary 全曝（agent 知封閉旗標全集；未舉旗 ≠ 已驗證 clear）。"""
    r = project_report_for_agent(_sample_report())
    rf = r["l1_changes"][0]["risk_flags"]
    assert _is_membrane(rf)
    assert rf["value"] == []
    assert len(rf["position"]["vocabulary"]) == 3


def test_risk_flags_input_not_mutated():
    """R5：入參 l1_changes[].risk_flags 仍裸 list（純函式）。"""
    original = _sample_report()
    project_report_for_agent(original)
    assert original["l1_changes"][1]["risk_flags"] == ["out_of_scope", "vulnerability"]
