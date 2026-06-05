"""S1 doubt 膜詞彙：工廠正確性 + J4 文法從 DoubtLifecycle 導出。"""
import pytest

from the_door.core.scope import doubt_membrane as dm
from the_door.core.scope.doubt_lifecycle import DoubtLifecycle


def test_current_state_signal_derives_grammar():
    """current_state→Signal；preconditions 反查、co_requires 由 _RESOLVING 導出。"""
    sp = dm.current_state_signal("explained")
    assert set(sp.contrasts) == set(DoubtLifecycle.VALID_TRANSITIONS.keys())
    assert set(sp.preconditions) == {"investigating", "escalated"}   # 哪些 from→explained
    assert sp.consequences == ("terminal",)                          # is_terminal
    assert sp.co_requires == ("reason",)                             # explained ∈ _RESOLVING
    assert "預期行為" in sp.gloss


def test_current_state_non_terminal_consequences_are_targets():
    """非終態的 consequences＝可達 targets（非 'terminal'）。"""
    sp = dm.current_state_signal("discovered")
    assert set(sp.consequences) == {"investigating", "escalated"}
    assert sp.co_requires == ()


def test_doubt_type_signal_minimal():
    sp = dm.doubt_type_signal("anomaly")
    assert set(sp.contrasts) == {"out_of_scope", "in_scope_incomplete", "anomaly", "low_confidence"}
    assert sp.preconditions == ()


def test_resolution_type_signal_contrasts_are_resolving_states():
    sp = dm.resolution_type_signal("fixed")
    assert set(sp.contrasts) == DoubtLifecycle._RESOLVING_STATES


def test_element_factories_project():
    assert dm.current_state_element("explained").to_json()["value"] == "explained"
    assert dm.free_text_element("任意說明").to_json() == {
        "value": "任意說明", "position": {"kind": "reserved"}
    }


def test_j4_grammar_follows_lifecycle(monkeypatch):
    """J4：擴 VALID_TRANSITIONS 加新狀態，contrasts 自動含之（證非寫死）。"""
    patched = dict(DoubtLifecycle.VALID_TRANSITIONS)
    patched["discovered"] = {"investigating", "escalated", "snoozed"}
    patched["snoozed"] = set()
    monkeypatch.setattr(dm._LC, "VALID_TRANSITIONS", patched)
    sp = dm.current_state_signal("discovered")
    assert "snoozed" in sp.contrasts          # 自動跟動、未改 doubt_membrane 碼


def test_input_schema_builders_derive_from_gloss():
    """零副本：input schema 的 enum＝gloss key 集、各 gloss ∈ description（衍生鎖）。"""
    ts = dm.target_state_schema()
    assert ts["enum"] == ["investigating", "explained", "fixed", "escalated", "accepted_risk"]
    assert dm._STATE_GLOSS["explained"] in ts["description"]
    assert dm.state_filter_schema()["enum"] == list(dm._STATE_GLOSS.keys())   # 6
    assert dm.type_filter_schema()["enum"] == list(dm._TYPE_GLOSS.keys())     # 4
    assert dm._TYPE_GLOSS["anomaly"] in dm.type_filter_schema()["description"]
