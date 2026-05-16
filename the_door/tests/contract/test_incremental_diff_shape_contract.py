"""Contract: IncrementalDiff shape from Task 03 (analyze_changes MCP tool +
compute_affected_features) matches what Task 05 displays in the viewer.

Producer side: 03-pipeline-mcp.md Task 03.5 — analyze_changes JSON output.
Consumer side: 05-viewer-frontend.md (not yet — viewer doesn't display affected_features
list directly today, but a future task will). Until then this contract pins the
producer-to-MCP-agent shape.
"""
import pytest


@pytest.mark.contract
def test_analyze_changes_response_shape():
    pytest.skip("blocked on 03-pipeline-mcp Task 03.5 (producer)")

    # PRODUCER — populated in 03.5:
    # response = await analyze_changes_tool.execute({"codebase_path": ..., "baseline": "v1.0.0"})
    #
    # MCP-AGENT CONSUMER — what an LLM agent reading the response needs:
    # required_top_level = {"baseline_version_id", "baseline_label", "inherited_features",
    #                       "affected_features", "unmapped_nodes", "next_actions"}
    # assert required_top_level <= set(response.keys()) or "error" in response
    #
    # # Each affected feature exposes the delta:
    # for af in response.get("affected_features", []):
    #     assert "feature_id" in af
    #     assert "delta" in af
    #     assert set(af["delta"].keys()) >= {"added", "removed", "modified"}
