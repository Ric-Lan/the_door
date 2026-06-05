"""S0 膜 primitive 不變量與投影測試。"""
import pytest

from the_door.core.membrane.primitive import (
    MembraneElement,
    ReservedPassthrough,
    SignalPosition,
)


def test_signal_position_minimal_enum():
    """純 enum 只需 contrasts + gloss，操作位置欄位預設空 tuple。"""
    sp = SignalPosition(contrasts=("high", "medium", "low"), gloss="信心三級")
    assert sp.contrasts == ("high", "medium", "low")
    assert sp.preconditions == ()
    assert sp.consequences == ()
    assert sp.co_requires == ()


def test_signal_position_full_grammar():
    """帶轉換文法的 enum 填滿四欄。"""
    sp = SignalPosition(
        contrasts=("discovered", "investigating", "explained"),
        gloss="已查證為預期行為",
        preconditions=("investigating",),
        consequences=("terminal",),
        co_requires=("reason",),
    )
    assert sp.preconditions == ("investigating",)


def test_signal_position_empty_contrasts_raises():
    """I1：contrasts 非空（B 側 CWA 封閉集）。"""
    with pytest.raises(ValueError, match="非空"):
        SignalPosition(contrasts=(), gloss="x")


def test_reserved_passthrough_is_marker():
    rp = ReservedPassthrough()
    assert isinstance(rp, ReservedPassthrough)


def test_membrane_element_signal_payload_in_contrasts():
    """happy-path：Signal 值在自己的兄弟集裡。"""
    el = MembraneElement(
        payload="high",
        position=SignalPosition(contrasts=("high", "medium", "low"), gloss="信心三級"),
    )
    assert el.payload == "high"


def test_membrane_element_reserved_free_text():
    """reserved 窗：free-text payload 無約束。"""
    el = MembraneElement(payload="任意自由文字", position=ReservedPassthrough())
    assert el.payload == "任意自由文字"


def test_i4_payload_not_in_contrasts_raises():
    """I4：Signal 值必須定位於自己的封閉兄弟集。"""
    with pytest.raises(ValueError, match="不在"):
        MembraneElement(
            payload="banana",
            position=SignalPosition(contrasts=("high", "low"), gloss="x"),
        )


def test_i2_membrane_element_has_no_score_field():
    """I2：base 型無 score 欄位（禁自鑄裁決的結構性保證）。"""
    el = MembraneElement(payload="high",
                         position=SignalPosition(contrasts=("high",), gloss="x"))
    assert not hasattr(el, "score")
    assert not hasattr(el, "risk")


def test_to_json_signal_full_shape():
    el = MembraneElement(
        payload="explained",
        position=SignalPosition(
            contrasts=("discovered", "investigating", "explained"),
            gloss="已查證為預期行為",
            preconditions=("investigating",),
            consequences=("terminal",),
            co_requires=("reason",),
        ),
    )
    assert el.to_json() == {
        "value": "explained",
        "position": {
            "kind": "signal",
            "contrasts": ["discovered", "investigating", "explained"],
            "gloss": "已查證為預期行為",
            "preconditions": ["investigating"],
            "consequences": ["terminal"],
            "co_requires": ["reason"],
        },
    }


def test_to_json_reserved_shape():
    el = MembraneElement(payload="自由文字", position=ReservedPassthrough())
    assert el.to_json() == {"value": "自由文字", "position": {"kind": "reserved"}}


def test_i3_unknown_position_variant_raises():
    """I3：未知 position 變體顯式拋 TypeError（防 S2/S3 擴 union 漏更新投影）。"""
    from the_door.core.membrane.primitive import _position_to_json

    class _Fake:
        pass

    with pytest.raises(TypeError, match="未知 position"):
        _position_to_json(_Fake())
