"""S0→S1 連貫性回驗：膜 primitive 接得住 doubt 三欄（current_state / resolution.type / reason）。

用真實 DoubtLifecycle 資料當輸入，證 S0 的 base+Signal+Reserved 對 S1 充分且無剩。
不改任何生產碼。
"""
from the_door.core.membrane import MembraneElement, ReservedPassthrough, SignalPosition
from the_door.core.scope.doubt_lifecycle import DoubtLifecycle


def test_coherence_current_state_signal():
    """current_state（6 值閉集）→ SignalPosition；前件/後件源自 DoubtLifecycle。"""
    lc = DoubtLifecycle()
    states = tuple(lc.VALID_TRANSITIONS.keys())          # 封閉兄弟集
    value = "explained"
    preconds = tuple(s for s, tos in lc.VALID_TRANSITIONS.items() if value in tos)
    el = MembraneElement(
        payload=value,
        position=SignalPosition(
            contrasts=states,
            gloss="已查證為預期行為，非缺陷",
            preconditions=preconds,                       # 反查 VALID_TRANSITIONS
            consequences=("terminal",) if lc.is_terminal(value) else (),  # 從 is_terminal 導出
            co_requires=("reason",),
        ),
    )
    j = el.to_json()
    assert j["value"] == "explained"
    assert set(j["position"]["contrasts"]) == set(states)
    assert "investigating" in j["position"]["preconditions"]
    assert "escalated" in j["position"]["preconditions"]
    assert j["position"]["consequences"] == ["terminal"]


def test_coherence_resolution_type_signal():
    """resolution.type（3 值閉集）→ SignalPosition；contrasts＝_RESOLVING_STATES。"""
    lc = DoubtLifecycle()
    contrasts = tuple(sorted(lc._RESOLVING_STATES))       # {explained, fixed, accepted_risk}
    el = MembraneElement(
        payload="fixed",
        position=SignalPosition(contrasts=contrasts, gloss="已修復"),
    )
    assert el.to_json()["value"] == "fixed"
    assert "fixed" in el.to_json()["position"]["contrasts"]


def test_coherence_reason_reserved():
    """reason（free-text）→ ReservedPassthrough。"""
    el = MembraneElement(payload="使用者確認為框架慣例", position=ReservedPassthrough())
    assert el.to_json() == {"value": "使用者確認為框架慣例", "position": {"kind": "reserved"}}
