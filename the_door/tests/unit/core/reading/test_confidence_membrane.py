"""S4 confidence 膜：全序 Signal / 缺值退 Noise / reserved。"""
from the_door.core.reading.confidence_membrane import (
    CONFIDENCE_CONTRASTS, confidence_element, confidence_reason_element,
    confidence_schema_fragment, confidence_signal,
)


def test_contrasts_full_order():
    assert CONFIDENCE_CONTRASTS == ("high", "medium", "low")   # C2 全序


def test_value_to_signal():
    sig = confidence_signal("low")
    assert sig.contrasts == ("high", "medium", "low") and sig.gloss      # C1


def test_element_value_is_signal():
    j = confidence_element("high").to_json()
    assert j["value"] == "high" and j["position"]["kind"] == "signal"
    assert j["position"]["contrasts"] == ["high", "medium", "low"]


def test_element_none_retreats_to_noise_indeterminate():
    j = confidence_element(None).to_json()                                # C3
    assert j["position"]["kind"] == "noise"
    assert j["position"]["gap_kind"] == "indeterminate"
    assert j["position"]["aggregated"] is False


def test_reason_is_reserved():
    j = confidence_reason_element("節點明確").to_json()                    # C5
    assert j["position"] == {"kind": "reserved"} and j["value"] == "節點明確"


def test_schema_fragment_oneof_const_plus_null():
    frag = confidence_schema_fragment()
    consts = [o["const"] for o in frag["oneOf"] if "const" in o]
    assert consts == ["high", "medium", "low"]                            # C2 parity 基礎
    assert any(o.get("type") == "null" for o in frag["oneOf"])            # nullable


def test_valid_confidence_derived_from_single_source():
    from the_door.mcp.tools.snapshot_write_tool import VALID_CONFIDENCE
    assert VALID_CONFIDENCE == set(CONFIDENCE_CONTRASTS)                  # C2 單一來源
