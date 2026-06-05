"""S2 edge 膜詞彙：殘餘工廠 + 決定性。"""
from the_door.core.llm import edge_membrane as em


def test_is_residue():
    assert em.is_residue("skipped_dynamic") is True
    assert em.is_residue("name_match_ambiguous") is False     # 格內低信心、非殘餘
    assert em.is_residue("scope_rule") is False


def test_indeterminate_element_counts_and_proportion():
    el = em.indeterminate_residue_element("caller", {"send": 3, "recv": 1}, total_edges=8)
    j = el.to_json()
    assert j["value"]["caller"] == "caller"
    assert j["value"]["methods"] == {"recv": 1, "send": 3}    # 排序（a→z）
    assert j["position"]["kind"] == "noise"
    assert j["position"]["gap_kind"] == "indeterminate"
    assert j["position"]["cardinality"] == 4
    assert j["position"]["proportion"] == 0.5                 # 4/8
    assert j["position"]["aggregated"] is True


def test_methods_sorted_deterministic():
    a = em.indeterminate_residue_element("c", {"z": 1, "a": 1, "m": 1}, total_edges=3)
    b = em.indeterminate_residue_element("c", {"m": 1, "z": 1, "a": 1}, total_edges=3)
    assert a.to_json() == b.to_json()
    assert list(a.to_json()["value"]["methods"].keys()) == ["a", "m", "z"]


def test_zero_total_no_zero_division():
    el = em.indeterminate_residue_element("c", {"x": 1}, total_edges=0)
    assert el.to_json()["position"]["proportion"] == 0.0      # 防呆（實務 total≥1）
