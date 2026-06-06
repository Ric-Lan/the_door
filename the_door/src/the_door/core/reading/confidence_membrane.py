"""confidence 線的膜詞彙：把 confidence enum 的每值意義結構化為 SignalPosition。

意義來源單一化（種子檔 §8.10）：CONFIDENCE_CONTRASTS＝全序唯一來源（high>medium>low）；
gloss＝極短指稱注解（此處唯一手寫處）。缺值（None＝來源未評估信心）退
NoisePosition(indeterminate)（§8.13 通則、復用 S2/S3 退路），不靜默自鑄 default。
S5–S7 照此樣板各建 {domain}_membrane.py。
"""
from __future__ import annotations

from the_door.core.membrane import (
    MembraneElement, NoisePosition, ReservedPassthrough, SignalPosition,
)

# 唯一有序來源（全序：high 最強信心 → low 最弱）。consumers 一律衍生、不另列副本。
CONFIDENCE_CONTRASTS: tuple[str, ...] = ("high", "medium", "low")

# 唯一手寫處：每值極短 gloss（人類意圖殘餘，語法捕不到）。
_GLOSS = {
    "high": "抽取信心高",
    "medium": "抽取信心中",
    "low": "抽取信心低",
}


def confidence_signal(value: str) -> SignalPosition:
    """confidence（3 值全序 enum）→ Signal（contrasts 全序＋gloss）。"""
    return SignalPosition(contrasts=CONFIDENCE_CONTRASTS, gloss=_GLOSS[value])


def confidence_element(value: str | None) -> MembraneElement:
    """單一 confidence 值 → MembraneElement。

    value ∈ contrasts → SignalPosition（格內）；
    value is None（來源未評估信心）→ NoisePosition(indeterminate)（格外殘餘、
    aggregated=False＝單筆 presence 殘餘，承 S2／S3 缺值退路）。
    """
    if value is None:
        return MembraneElement(payload=None, position=NoisePosition(gap_kind="indeterminate"))
    return MembraneElement(payload=value, position=confidence_signal(value))


def confidence_reason_element(text: str) -> MembraneElement:
    """confidence_reason＝reserved 窗（明文開放、自由文字，§443）。"""
    return MembraneElement(payload=text, position=ReservedPassthrough())


def confidence_schema_fragment() -> dict:
    """input/output schema 的 confidence 片段（oneOf+const+description、缺值容 null）。

    與 _GLOSS 同源（零副本）；nullable＝缺值＝未評估（向後相容：舊資料 enum 值仍合法）。
    """
    return {
        "oneOf": [{"const": v, "description": _GLOSS[v]} for v in CONFIDENCE_CONTRASTS]
                 + [{"type": "null", "description": "未評估（來源未給信心）"}],
    }
