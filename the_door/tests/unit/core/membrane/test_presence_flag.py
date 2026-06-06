"""presence-flag：第 5 變體 PresenceFlagPosition 不變量與投影（P1/P2/P6）。

fact-finder 守界（spec §0）：vocabulary＝可能性空間（封閉旗標全集），
未列入 present 的旗標＝「未舉此旗標」、絕非「已驗證 clear」。
"""
import pytest

from the_door.core.membrane.primitive import (
    MembraneElement,
    PresenceFlagPosition,
    SignalPosition,
)


# --- P1：PresenceFlagPosition 自身不變量 ---
def test_presence_flag_minimal():
    """vocabulary 必填、glosses 預設空 tuple。"""
    pf = PresenceFlagPosition(vocabulary=("a", "b", "c"))
    assert pf.vocabulary == ("a", "b", "c")
    assert pf.glosses == ()


def test_presence_flag_with_glosses():
    pf = PresenceFlagPosition(
        vocabulary=("a", "b"), glosses=(("a", "旗 a"), ("b", "旗 b"))
    )
    assert dict(pf.glosses) == {"a": "旗 a", "b": "旗 b"}


def test_presence_flag_empty_vocabulary_raises():
    """P1：vocabulary 非空（CWA 封閉詞彙集）。"""
    with pytest.raises(ValueError, match="非空"):
        PresenceFlagPosition(vocabulary=())


def test_presence_flag_gloss_outside_vocabulary_raises():
    """P1：glosses 的 flag 必須 ⊆ vocabulary。"""
    with pytest.raises(ValueError, match="vocabulary"):
        PresenceFlagPosition(vocabulary=("a",), glosses=(("b", "越界旗"),))


# --- P2：MembraneElement + PresenceFlag 子集不變量 ---
def test_element_present_subset_ok():
    """happy-path：present 子集 ⊆ vocabulary。"""
    el = MembraneElement(
        payload=["a", "c"],
        position=PresenceFlagPosition(vocabulary=("a", "b", "c")),
    )
    assert el.payload == ["a", "c"]


def test_element_empty_present_ok():
    """空 present（未舉任何旗）合法——vocabulary 仍全曝。"""
    el = MembraneElement(
        payload=[], position=PresenceFlagPosition(vocabulary=("a", "b"))
    )
    assert el.payload == []


def test_element_present_outside_vocabulary_raises():
    """P2：present 含 vocabulary 外旗標 → ValueError。"""
    with pytest.raises(ValueError, match="vocabulary 外旗標"):
        MembraneElement(
            payload=["x"],
            position=PresenceFlagPosition(vocabulary=("a", "b")),
        )


# --- to_json 形狀 ---
def test_to_json_presence_flag_shape():
    el = MembraneElement(
        payload=["a"],
        position=PresenceFlagPosition(
            vocabulary=("a", "b", "c"),
            glosses=(("a", "旗 a"), ("b", "旗 b"), ("c", "旗 c")),
        ),
    )
    assert el.to_json() == {
        "value": ["a"],
        "position": {
            "kind": "presence_flag",
            "vocabulary": ["a", "b", "c"],
            "glosses": {"a": "旗 a", "b": "旗 b", "c": "旗 c"},
        },
    }


# --- P6：既有變體不破（純加法回歸哨兵）---
def test_p6_signal_variant_unchanged():
    """加第 5 變體後，既有 SignalPosition 投影逐字不變。"""
    el = MembraneElement(
        payload="high",
        position=SignalPosition(contrasts=("high", "low"), gloss="x"),
    )
    assert el.to_json()["position"]["kind"] == "signal"
