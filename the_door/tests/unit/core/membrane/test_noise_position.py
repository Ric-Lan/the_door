"""S2 NoisePosition：A 側殘餘描述子 + N1/N2 型驅動守衛。"""
import pytest

from the_door.core.membrane import GAP_KIND_PRIORITY, MembraneElement, NoisePosition


def test_priority_order_is_canonical():
    assert GAP_KIND_PRIORITY == ("corrupt", "indeterminate", "evolutionary", "reserved")


def test_aggregated_requires_cardinality_and_proportion():
    with pytest.raises(ValueError, match="必帶"):
        NoisePosition(gap_kind="indeterminate", aggregated=True)            # 兩者皆缺
    with pytest.raises(ValueError, match="必帶"):
        NoisePosition(gap_kind="indeterminate", cardinality=3, aggregated=True)  # 缺 proportion


def test_aggregated_happy_path():
    np = NoisePosition(gap_kind="indeterminate", cardinality=3, proportion=0.5, aggregated=True)
    assert np.cardinality == 3 and np.proportion == 0.5


def test_gap_kind_must_be_in_priority():
    with pytest.raises(ValueError, match="GAP_KIND_PRIORITY"):
        NoisePosition(gap_kind="banana")
    for k in GAP_KIND_PRIORITY:
        NoisePosition(gap_kind=k)                # 4 合法值皆可構造


def test_cardinality_nonnegative():
    with pytest.raises(ValueError, match="不可為負"):
        NoisePosition(gap_kind="indeterminate", cardinality=-1)


def test_proportion_in_range():
    with pytest.raises(ValueError, match="必須在"):
        NoisePosition(gap_kind="indeterminate", proportion=1.5)


def test_non_aggregated_single_residue_ok():
    """單筆殘餘＝aggregated=False、不要求基數（presence 情境，取代舊 is_flag）。"""
    np = NoisePosition(gap_kind="indeterminate")
    assert np.aggregated is False and np.cardinality is None


def test_to_json_noise_shape():
    el = MembraneElement(
        payload={"caller": "c", "methods": {"send": 2}},
        position=NoisePosition(gap_kind="indeterminate", cardinality=2, proportion=0.4, aggregated=True),
    )
    j = el.to_json()
    assert j["position"] == {
        "kind": "noise", "gap_kind": "indeterminate",
        "cardinality": 2, "proportion": 0.4, "aggregated": True,
    }
    assert j["value"] == {"caller": "c", "methods": {"send": 2}}
