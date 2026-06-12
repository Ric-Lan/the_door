"""peel_membrane：膜樣板（contrasts/gloss 同源）＋單向流動判定（含閾值邊界）。"""
from the_door.core.structure_view.peel_membrane import (
    PEEL_CONTRASTS, PEEL_FLOW_RATIO_THRESHOLD, PEEL_MIN_OUTBOUND,
    evaluate_peel, peel_element,
)
from the_door.core.structure_view.region_partition import Region


def _region(outbound: int, inbound: int) -> Region:
    return Region(region_id="tests", node_ids=("tests/t.py::t1",),
                  internal_edges=0, inbound_edges=inbound, outbound_edges=outbound,
                  flow_to={"src": outbound} if outbound else {},
                  flow_from={"src": inbound} if inbound else {})


def test_membrane_template_single_value():
    el = peel_element("one_way_consumer").to_json()
    assert el["value"] == "one_way_consumer"
    assert el["position"]["contrasts"] == list(PEEL_CONTRASTS)
    assert el["position"]["gloss"]  # 非空 gloss


def test_one_way_consumer_detected_above_threshold():
    verdict = evaluate_peel(_region(outbound=60, inbound=1))  # ratio 60 >= 50, outbound >= 50
    assert verdict is not None
    assert verdict["reason"]["value"] == "one_way_consumer"
    ev = verdict["evidence"]
    assert ev["outbound"] == 60 and ev["inbound"] == 1
    assert ev["ratio_threshold"] == PEEL_FLOW_RATIO_THRESHOLD
    assert ev["min_outbound"] == PEEL_MIN_OUTBOUND


def test_balanced_flow_not_peeled():
    assert evaluate_peel(_region(outbound=60, inbound=10)) is None  # ratio 6 < 50


def test_small_region_not_peeled_even_if_one_way():
    assert evaluate_peel(_region(outbound=10, inbound=0)) is None  # outbound 10 < 50


def test_zero_inbound_uses_max_one_denominator():
    verdict = evaluate_peel(_region(outbound=50, inbound=0))  # 50/max(0,1)=50 >= 50
    assert verdict is not None
