"""S5 C3：scope_verify_tool entry 投影 scope_state 經膜（值→signal、無裸 enum）。"""
from the_door.mcp.tools.scope_verify_tool import _entry_to_json
from the_door.models import ScopeEntry


def test_entry_scope_state_membrane_projection():
    e = ScopeEntry(feature_id="feat-x", scope_state="out_of_scope",
                   feature_label="L", expected_label="E")
    j = _entry_to_json(e)
    assert isinstance(j["scope_state"], dict)                              # C3 無裸 enum
    assert j["scope_state"]["value"] == "out_of_scope"
    assert j["scope_state"]["position"]["kind"] == "signal"
    assert j["scope_state"]["position"]["contrasts"] == [
        "in_scope_complete", "in_scope_incomplete", "out_of_scope"]
    assert j["feature_id"] == "feat-x"                                     # 載體欄保留
    assert j["feature_label"] == "L" and j["expected_label"] == "E"
