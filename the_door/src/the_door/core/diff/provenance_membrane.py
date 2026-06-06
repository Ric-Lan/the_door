"""provenance 線的膜詞彙：snapshot 出生契約戳 vs 當前契約 → current/legacy/unknown Signal。

provenance＝乙案第三主軸（種子 §181）、唯一淨新增軸（§445）。per-snapshot 出生事實：
contract_version(出生戳) vs SNAPSHOT_CONTRACT_VERSION(當前) 的機械事實比對（fact-finder、
不裁決）。unknown＝格內哨兵真值（§390「格內對格外命名橋」：pre-stamp 快照）⟹ 純 3-Signal、
無 None 分支、無 NoisePosition。emit 面＝diff/incremental/list（§283「diff 才點亮」）。
與 inherited/affected 正交（§0：出生契約 ⊥ 本次重算與否）。
"""
from __future__ import annotations

from the_door.core.membrane import MembraneElement, SignalPosition
from the_door.models.snapshot import SNAPSHOT_CONTRACT_VERSION

PROVENANCE_CONTRASTS: tuple[str, ...] = ("current", "legacy", "unknown")

_GLOSS = {
    "current": "出生於當前契約版本（與當前分析同 footing）",
    "legacy": "出生於非當前契約版本（跨契約邊界、語義可能漂移）",  # !=current，不假設方向
    "unknown": "無契約戳（pre-stamp 快照，出生契約不可知）",
}


def derive_provenance(contract_version: str | None) -> str:
    """戳 vs 當前契約 → provenance 值（純事實比對、不裁決）。

    None（pre-stamp）→ unknown；==當前 → current；present 且 != → legacy。
    """
    if contract_version is None:
        return "unknown"
    return "current" if contract_version == SNAPSHOT_CONTRACT_VERSION else "legacy"


def provenance_signal(value: str) -> SignalPosition:
    return SignalPosition(contrasts=PROVENANCE_CONTRASTS, gloss=_GLOSS[value])


def provenance_element(value: str) -> MembraneElement:
    """provenance 值 → MembraneElement（格內 Signal、unknown 是真值非缺值）。"""
    return MembraneElement(payload=value, position=provenance_signal(value))


def provenance_element_for(contract_version: str | None) -> MembraneElement:
    """便捷：直接由 snapshot 戳投影（衍生＋升膜）。"""
    return provenance_element(derive_provenance(contract_version))
