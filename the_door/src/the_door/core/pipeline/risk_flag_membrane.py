"""risk_flags 線的膜詞彙：L1 變更的多選風險旗標 → PresenceFlagPosition。

risk_flags＝封閉 3-詞彙（對齊 update-report.schema enum）的多選 presence 旗標；
膜暴露完整詞彙使 agent 知封閉旗標全集（可能性空間）。未舉之旗標＝「未帶此旗標」、
**不**斷言已驗證 clear（生產者條件式檢查，fact-finder 守界）。emit 在 report_membrane
agent 邊界（§8.12）。
"""
from __future__ import annotations

from the_door.core.membrane import MembraneElement, PresenceFlagPosition

# 單一來源：risk_flags 封閉詞彙（對齊 update-report.schema.json risk_flags enum）。
RISK_FLAG_VOCABULARY: tuple[str, ...] = ("out_of_scope", "vulnerability", "semantic_drift")

_GLOSS: tuple[tuple[str, str], ...] = (
    ("out_of_scope", "變更落在宣告 scope 之外"),
    ("vulnerability", "關聯到已知漏洞"),
    ("semantic_drift", "時間軸偵測到語義漂移"),
)


def risk_flags_element(present: list[str]) -> MembraneElement:
    """present 旗標子集 → MembraneElement（多選格內、absence 經 vocabulary 顯式）。

    payload＝present 子集（保序）；position 載完整詞彙＋per-flag gloss。
    present 含 vocabulary 外值 → MembraneElement 子集不變量 ValueError（防呆）。
    """
    return MembraneElement(
        payload=list(present),
        position=PresenceFlagPosition(vocabulary=RISK_FLAG_VOCABULARY, glosses=_GLOSS),
    )
