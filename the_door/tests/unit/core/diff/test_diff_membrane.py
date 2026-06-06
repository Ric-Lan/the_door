"""S6 unit：diff_state 膜詞彙（node 5-val／edge 3-val 兩條閉集 enum）。

對應 spec §4 不變量 C1（值→Signal＋to_json 形狀）／C4（node/edge 正交）。
承 S5 test_scope_membrane 樣板（純 enum、無 None 分支、無 schema_fragment）。
"""
from __future__ import annotations

import pytest

from the_door.core.diff.diff_membrane import (
    EDGE_DIFF_CONTRASTS,
    NODE_DIFF_CONTRASTS,
    edge_diff_element,
    edge_diff_signal,
    node_diff_element,
    node_diff_signal,
)
from the_door.core.scope.doubt_membrane import _TYPE_GLOSS  # 正交對照（S5 C4 風格）


# ── C1-node：5 值各→Signal、contrasts==NODE_DIFF_CONTRASTS、gloss 非空 ──
@pytest.mark.parametrize("value", list(NODE_DIFF_CONTRASTS))
def test_node_diff_signal_contrasts_and_gloss(value):
    sig = node_diff_signal(value)
    assert sig.contrasts == NODE_DIFF_CONTRASTS
    assert len(NODE_DIFF_CONTRASTS) == 5
    assert sig.gloss  # 非空
    # 純 enum 樣板：無前件/後件/共依
    assert sig.preconditions == ()
    assert sig.consequences == ()
    assert sig.co_requires == ()


# ── C1-edge：3 值各→Signal、contrasts==EDGE_DIFF_CONTRASTS ──
@pytest.mark.parametrize("value", list(EDGE_DIFF_CONTRASTS))
def test_edge_diff_signal_contrasts_and_gloss(value):
    sig = edge_diff_signal(value)
    assert sig.contrasts == EDGE_DIFF_CONTRASTS
    assert len(EDGE_DIFF_CONTRASTS) == 3
    assert sig.gloss


# ── to_json 形狀（B 側送達 element）──
def test_node_diff_element_to_json_shape():
    j = node_diff_element("attribute_changed").to_json()
    assert j["value"] == "attribute_changed"
    assert j["position"]["kind"] == "signal"
    assert j["position"]["contrasts"] == list(NODE_DIFF_CONTRASTS)
    assert j["position"]["gloss"]
    assert j["position"]["preconditions"] == []
    assert j["position"]["consequences"] == []
    assert j["position"]["co_requires"] == []


def test_edge_diff_element_to_json_shape():
    j = edge_diff_element("modified").to_json()
    assert j["value"] == "modified"
    assert j["position"]["kind"] == "signal"
    assert j["position"]["contrasts"] == list(EDGE_DIFF_CONTRASTS)
    assert j["position"]["gloss"]


# ── C4：node/edge 兩子軸正交（共享字串、contrasts 集不同）──
def test_node_edge_axes_orthogonal():
    node_set, edge_set = set(NODE_DIFF_CONTRASTS), set(EDGE_DIFF_CONTRASTS)
    assert node_set != edge_set  # 集不同 ⟹ 不同位置 ⟹ 正交、不單源化
    assert node_set & edge_set == {"added", "removed"}  # 共享字串
    assert node_set - edge_set == {"attribute_changed", "dependency_changed", "unchanged"}
    assert edge_set - node_set == {"modified"}


def test_diff_axes_orthogonal_to_other_axes():
    # diff_state 與三主軸之一（透過 doubt_type 對照）正交：contrasts 集不同。
    assert set(NODE_DIFF_CONTRASTS) != set(_TYPE_GLOSS)
    assert set(EDGE_DIFF_CONTRASTS) != set(_TYPE_GLOSS)


# ── gloss 涵蓋：無漏值/死值（雙向 == contrasts）──
def test_gloss_covers_contrasts_exactly():
    from the_door.core.diff.diff_membrane import _EDGE_GLOSS, _NODE_GLOSS

    assert set(_NODE_GLOSS) == set(NODE_DIFF_CONTRASTS)
    assert set(_EDGE_GLOSS) == set(EDGE_DIFF_CONTRASTS)


# ── I4 防呆：值∉contrasts → KeyError（正常經 engine 閉集守住）──
def test_unknown_value_raises():
    with pytest.raises(KeyError):
        node_diff_element("bogus")
    with pytest.raises(KeyError):
        edge_diff_element("bogus")
