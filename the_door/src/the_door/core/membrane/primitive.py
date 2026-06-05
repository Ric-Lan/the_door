"""膜 primitive：意義經結構位置送達消費端 LLM 的單一 emit 原語。

非持久化層——住 emission/呈現邊界（種子檔 §8.12）。snapshot 等照舊存 bare 值，
本原語在 emit 時把「值 + 它在結構空間的位置」一起投影出去。

per-value 切法（種子檔 §8.13 勘誤）：膜的格內/格外界線切在「值」、非「欄位」。
落在閉集的值 → 格內 Signal（本檔建）；格外殘餘 → 格外 Noise（S2 建）。
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SignalPosition:
    """B 側（CWA／格內／封閉訊號）：值的意義＝它在封閉兄弟集中的對比位置。

    四個操作位置欄位皆 optional：純 enum 只填 contrasts + gloss；帶轉換文法的
    enum（如 doubt current_state）填滿，源自內部單一來源（DoubtLifecycle）。
    contrasts 是 tuple（有序）：doubt states＝圖；severity＝全序——同型別容兩者。
    gloss＝極短指稱注解（非散文，面對遞迴必須短）。
    """
    contrasts: tuple[str, ...]              # 對比：完整封閉兄弟集（含本值）
    gloss: str                             # 極短指稱注解
    preconditions: tuple[str, ...] = ()    # 前件：可轉入本值的條件
    consequences: tuple[str, ...] = ()     # 後件：本值產生的效果
    co_requires: tuple[str, ...] = ()      # 共依：本值必填的伴隨欄位

    def __post_init__(self) -> None:
        if not self.contrasts:
            raise ValueError(
                "SignalPosition.contrasts 必須是非空的封閉兄弟集（B 側 CWA）"
            )
