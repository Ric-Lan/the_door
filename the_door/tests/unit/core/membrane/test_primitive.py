"""S0 膜 primitive 不變量與投影測試。"""
import pytest

from the_door.core.membrane.primitive import SignalPosition


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
