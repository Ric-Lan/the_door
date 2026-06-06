"""S5 scope 膜：3-state 格內 Signal / 與 doubt_type 正交。"""
from the_door.core.scope.scope_membrane import (
    SCOPE_CONTRASTS, scope_element, scope_signal,
)


def test_contrasts_three_state():
    assert SCOPE_CONTRASTS == ("in_scope_complete", "in_scope_incomplete", "out_of_scope")  # C1


def test_value_to_signal():
    sig = scope_signal("out_of_scope")
    assert sig.contrasts == SCOPE_CONTRASTS and sig.gloss      # C1（純 enum：contrasts+gloss）
    assert sig.preconditions == () and sig.consequences == ()  # 無前件/後件（categorical）


def test_element_value_is_signal():
    j = scope_element("in_scope_complete").to_json()
    assert j["value"] == "in_scope_complete" and j["position"]["kind"] == "signal"
    assert j["position"]["contrasts"] == list(SCOPE_CONTRASTS)


def test_orthogonal_to_doubt_type():
    """C4：scope_state 與 doubt_type 共享字串但 contrasts 集不同（3 vs 4）＝正交、不單源化。"""
    from the_door.core.scope.doubt_membrane import _TYPE_GLOSS
    assert set(SCOPE_CONTRASTS) != set(_TYPE_GLOSS)                       # 集不等
    assert {"out_of_scope", "in_scope_incomplete"} <= set(SCOPE_CONTRASTS) & set(_TYPE_GLOSS)  # 共享 2 字串
