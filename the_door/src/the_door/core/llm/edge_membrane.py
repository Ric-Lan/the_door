"""edge 線的膜詞彙：把 edge resolution 的「格外殘餘」結構化為 NoisePosition。

per-value 切法（種子檔 §8.13）：edge resolution 5 值中，skipped_dynamic 是唯一
格外殘餘（dynamic dispatch → 知識上 indeterminate）；name_match_ambiguous 是格內
低信心（confidence 軸，S4），不在此（不歸 gap_kind）。

聚合殘餘必帶基數比例（§8.3）：殘餘按 caller 聚合，cardinality＝真實計數（不去重、
修 F5 病灶①），proportion＝佔全體 edge 比例。S2-S7 照此樣板各建 {domain}_membrane.py。
"""
from __future__ import annotations

from the_door.core.membrane import MembraneElement, NoisePosition

# resolution → gap_kind 單一來源（只列格外殘餘；格內/低信心 resolution 不在此）。
# skipped_dynamic＝dynamic dispatch context（edge_builder.py:49）→ 知識上 indeterminate。
_RESIDUE_GAP_KIND = {
    "skipped_dynamic": "indeterminate",
}


def is_residue(resolution: str) -> bool:
    """此 resolution 是否為格外殘餘（→NoisePosition）。"""
    return resolution in _RESIDUE_GAP_KIND


def indeterminate_residue_element(
    caller: str, method_counts: dict[str, int], total_edges: int
) -> MembraneElement:
    """skipped_dynamic 殘餘（單一 caller、聚合）→ NoisePosition element。

    payload＝殘餘本體（caller＋逐 method 計數，基數保留、**method 鍵排序**＝決定性）；
    position＝NoisePosition（gap_kind=indeterminate, cardinality=Σcount, proportion）。
    意義由 gap_kind（結構）＋ prompt 教學（§3.4）承載——payload **不**塞 gloss
    （NoisePosition＝純殘餘描述子無 gloss 欄；gloss 在 payload 會與膜模型自相矛盾＋雙源）。
    proportion 分母＝**本批全 edge**（total_edges＝len(edges)）：語意＝此 caller 的
    indeterminate 殘餘佔整批呼叫圖的比例。
    """
    cardinality = sum(method_counts.values())
    proportion = (cardinality / total_edges) if total_edges else 0.0
    return MembraneElement(
        payload={"caller": caller, "methods": dict(sorted(method_counts.items()))},
        position=NoisePosition(
            gap_kind="indeterminate",
            cardinality=cardinality,
            proportion=proportion,
            aggregated=True,
        ),
    )
