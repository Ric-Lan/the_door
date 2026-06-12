"""撥離理由膜：照 confidence_membrane 樣板（CONTRASTS＋_GLOSS 單一來源）。

第一刀 enum 僅 one_way_consumer（2026-06-12 spike 實測 4362:9 成立的唯一訊號）。
禁止用可達性/isolation 當撥離訊號（project_t1_guidance_falsified 已證偽）。
判定＝決定性結構計算（surface 不 judge）；「要不要跳過該區」裁決留給消費端 LLM。
"""
from __future__ import annotations

from the_door.core.membrane import MembraneElement, SignalPosition
from the_door.core.structure_view.region_partition import Region

# 唯一來源：撥離理由 enum（低基數，遇真實新案例才擴值）。
PEEL_CONTRASTS: tuple[str, ...] = ("one_way_consumer",)

_GLOSS = {
    "one_way_consumer": "單向消費區：大量消費其他區、幾乎不被回頭消費（如測試碼之於主體）",
}

# 判定閾值（spike 實測 tests/ 流向 4362:9 ≈ 485:1，餘量充足）。寫進 evidence 供消費端稽核。
PEEL_FLOW_RATIO_THRESHOLD = 50   # outbound/inbound 比
PEEL_MIN_OUTBOUND = 50           # 避免小樣本誤標


def peel_signal(value: str) -> SignalPosition:
    return SignalPosition(contrasts=PEEL_CONTRASTS, gloss=_GLOSS[value])


def peel_element(value: str) -> MembraneElement:
    return MembraneElement(payload=value, position=peel_signal(value))


def evaluate_peel(region: Region) -> dict | None:
    """單向消費判定。回 {"reason": 膜元素 json, "evidence": 計數+閾值} 或 None（不標）。"""
    a, b = region.outbound_edges, region.inbound_edges
    ratio = a / max(b, 1)
    if a >= PEEL_MIN_OUTBOUND and ratio >= PEEL_FLOW_RATIO_THRESHOLD:
        return {
            "reason": peel_element("one_way_consumer").to_json(),
            "evidence": {
                "outbound": a, "inbound": b, "ratio": round(ratio, 1),
                "min_outbound": PEEL_MIN_OUTBOUND,
                "ratio_threshold": PEEL_FLOW_RATIO_THRESHOLD,
            },
        }
    return None
