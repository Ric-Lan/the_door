"""S8-report characterization：render_json 人類面零改動（R2）＋ agent 邊界升膜（R1）。

直接構造 PipelineResult（frozen dataclass，免跑 orchestrator）→ 真實 render_json，
釘現狀 bare（R2），再經 project_report_for_agent 驗膜（R1）。
"""
from __future__ import annotations

from pathlib import Path

from the_door.core.pipeline.report_membrane import project_report_for_agent
from the_door.core.pipeline.report_renderer import ReportRenderer
from the_door.models import (
    BaselineInfo, DiffResult, DiffSummary, EdgeDiff, NodeDiff, PipelineConfig,
)
from the_door.models.pipeline import PipelineResult
from the_door.models.scope import ScopeEntry, ScopeResult


def _result() -> PipelineResult:
    bi = BaselineInfo(version_id="v0", timestamp="2026-01-01T00:00:00Z", trigger="manual")
    ci = BaselineInfo(version_id="v1", timestamp="2026-01-02T00:00:00Z", trigger="manual")
    diff = DiffResult(
        baseline_info=bi, current_info=ci,
        node_diffs=[
            NodeDiff(node_id="f1", diff_state="added", current_label="F1"),
            NodeDiff(node_id="f2", diff_state="attribute_changed",
                     current_label="F2", baseline_label="F2old"),
        ],
        edge_diffs=[EdgeDiff(from_node="f1", to_node="f2", diff_state="modified")],
        summary=DiffSummary(), layer="l1",
    )
    scope = ScopeResult(scope_name="s", entries=[
        ScopeEntry(feature_id="f1", scope_state="out_of_scope"),
        # f2 不在 scope → l2 scope_state None（report 面缺值）
    ])
    cfg = PipelineConfig(old_path=Path("old"), new_path=Path("new"))
    return PipelineResult(config=cfg, diff_result=diff, scope_result=scope)


# ── R2：人類面零改動——render_json 仍 bare ──
def test_render_json_stays_bare():
    report = ReportRenderer().render_json(_result())
    assert all(isinstance(e["change_type"], str) for e in report["l1_changes"])
    for d in report["l2_details"]:
        assert isinstance(d["change_type"], str)
        assert d["scope_state"] is None or isinstance(d["scope_state"], str)
    nds = report["l3_appendix"]["diff_result_json"]["node_diffs"]
    assert all(isinstance(nd["diff_state"], str) for nd in nds)


# ── R1：agent 邊界投影後升膜、無裸 enum ──
def test_agent_projection_lifts_to_membrane():
    report = ReportRenderer().render_json(_result())
    agent = project_report_for_agent(report)

    for e in agent["l1_changes"]:
        assert isinstance(e["change_type"], dict) and e["change_type"]["position"]["kind"] == "signal"
    for d in agent["l2_details"]:
        assert isinstance(d["change_type"], dict)
        ss = d["scope_state"]
        assert isinstance(ss, dict)
        assert ss["position"]["kind"] in ("signal", "noise")  # f1 signal / f2 None→noise
    # f2 的 scope_state None → noise(indeterminate)
    f2 = next(d for d in agent["l2_details"] if d["feature_id"] == "f2")
    assert f2["scope_state"]["position"]["kind"] == "noise"
    assert f2["scope_state"]["position"]["gap_kind"] == "indeterminate"
    nds = agent["l3_appendix"]["diff_result_json"]["node_diffs"]
    assert all(isinstance(nd["diff_state"], dict) for nd in nds)

    # 原 report 未被改（純函式）
    assert isinstance(report["l1_changes"][0]["change_type"], str)
