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


@dataclass(frozen=True)
class ReservedPassthrough:
    """reserved 窗：CWA 世界裡明文宣告的 OWA 窗。free-text，不要求結構。

    標記型別——free-text 內容住 MembraneElement.payload，本變體只宣告
    「此處刻意永久開放」。
    """
    pass


# Position union——S0 階段 2 變體；S2 加 NoisePosition、S3 加 RelayedVerdict。
Position = SignalPosition | ReservedPassthrough


@dataclass(frozen=True)
class MembraneElement:
    """一個輸出元素＝它的值（payload）＋它在結構空間的位置（position）。

    base 型刻意無 score/risk/severity 欄位：裁決只能經（未來的）RelayedVerdict
    position，且該變體強制外部證據——自鑄裁決在型別上無處可放（I2）。

    payload 語意 per-variant：
      - SignalPosition → payload＝該閉集的某個值（str），型別強制 payload ∈ contrasts（I4）。
      - ReservedPassthrough → payload＝free-text 字串（無約束）。
    payload 寬型 object 是為未來 RelayedVerdict（S3）預留。
    """
    payload: object
    position: Position

    def __post_init__(self) -> None:
        # 核心膜保證（意義靠關係定位）：Signal 值必須真的在它宣稱的封閉兄弟集裡。
        # 跨欄不變量必須放 element 層——SignalPosition 自身拿不到 payload。
        if isinstance(self.position, SignalPosition):
            if self.payload not in self.position.contrasts:
                raise ValueError(
                    f"payload {self.payload!r} 不在其 SignalPosition.contrasts "
                    f"{self.position.contrasts!r} 中——值必須定位於自己的封閉兄弟集"
                )

    def to_json(self) -> dict:
        """唯一受祝福的投影路徑（§8.11 affordance）。意義不靠 prompt。"""
        return {"value": self.payload, "position": _position_to_json(self.position)}


def _position_to_json(position: Position) -> dict:
    if isinstance(position, SignalPosition):
        return {
            "kind": "signal",
            "contrasts": list(position.contrasts),
            "gloss": position.gloss,
            "preconditions": list(position.preconditions),
            "consequences": list(position.consequences),
            "co_requires": list(position.co_requires),
        }
    if isinstance(position, ReservedPassthrough):
        return {"kind": "reserved"}
    raise TypeError(f"未知 position 變體：{type(position).__name__}")
