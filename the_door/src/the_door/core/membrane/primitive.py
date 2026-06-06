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


# === gap-kind 優先序：膜核心單一來源（種子檔 §8.8 F1）===
# 知識上被迫的偏序：corrupt 讀不出 → 無法得知是否也 evolutionary，故 corrupt 優先。
# 多 gap-kind 共現時取最高優先者（單值、非子集）。edge 域只觸發 indeterminate；
# 共現解析由首個真觸發的試點實例化（S3+），此處只立來源 + 合法集。
GAP_KIND_PRIORITY: tuple[str, ...] = ("corrupt", "indeterminate", "evolutionary", "reserved")


@dataclass(frozen=True)
class NoisePosition:
    """A 側（OWA／格外／殘餘）：值落在契約閉集之外的純殘餘描述子。

    非裁決、非分數——只報「殘餘的性質(gap_kind)＋量(cardinality)＋佔比(proportion)」
    （種子檔 §8.3：殘餘格恆帶三件）。聚合殘餘（多筆併報）必帶基數與比例，
    否則就是偷渡減法（§8.12／§8.14）——型別強制，不帶基數不能 emit 聚合殘餘。

    （presence-only 旗標〔S0 §3a 曾草擬 is_flag〕**不在 S2 建**：edge 殘餘恆聚合、
    無生產者；單筆 off-grid 哨兵以 aggregated=False＋無 cardinality 表達即足。
    照 spec 自身「不預建死碼」原則，待首個 presence-only 生產者〔S4/S5 哨兵〕落地再加。）
    """
    gap_kind: str | None = None          # ∈ GAP_KIND_PRIORITY（或 None＝未分類）
    cardinality: int | None = None       # 殘餘筆數（真實計數、不去重）
    proportion: float | None = None      # 佔全體比例 [0,1]
    aggregated: bool = False             # 是否為多筆聚合殘餘（True ⟹ 必帶基數比例）

    def __post_init__(self) -> None:
        if self.gap_kind is not None and self.gap_kind not in GAP_KIND_PRIORITY:
            raise ValueError(
                f"NoisePosition.gap_kind {self.gap_kind!r} 不在 GAP_KIND_PRIORITY "
                f"{GAP_KIND_PRIORITY!r}（種子檔 §8.8 F1 單一來源）"
            )
        if self.cardinality is not None and self.cardinality < 0:
            raise ValueError("NoisePosition.cardinality 不可為負")
        if self.proportion is not None and not (0.0 <= self.proportion <= 1.0):
            raise ValueError("NoisePosition.proportion 必須在 [0,1]")
        if self.aggregated and (self.cardinality is None or self.proportion is None):
            raise ValueError(
                "聚合殘餘必帶 cardinality 與 proportion（不偷渡減法，§8.3/§8.12）"
            )


@dataclass(frozen=True)
class RelayedVerdict:
    """特例變體：忠實轉述外部權威的裁決（如 OSV/CVSS）。

    fact-finder 禁「自鑄」裁決，但「轉述帶 provenance 的外部裁決」＝事實、可轉述
    （種子檔 §8.12 修正③）。守衛＝evidence（外部證據本體，如 CVSS vector）非空方可構造：
    非空 authority 標籤對真假分零鑑別力（scanner 實證：捏造中點也蓋 source="osv-scanner"），
    故守衛切在證據本體（§8.13 勘誤「RelayedVerdict 強制外部 provenance」列）。
    無 evidence ⟹ 不可構造 ⟹ 退 NoisePosition(indeterminate)（§8.13 通則）。

    score 選填＝外部實際給的數值裁決（或 None＝只有 vector 無數值）；**不自行計算**
    （自算 base score＝自鑄裁決，違 fact-finder）。只轉述外部給的。
    """
    authority: str            # 外部權威標籤（如 "osv-scanner"）
    evidence: str             # 外部證據本體（如 CVSS vector string）——非空方可構造
    score: float | None = None  # 外部給的數值裁決（或 None；不自算）

    def __post_init__(self) -> None:
        if not self.evidence:
            raise ValueError(
                "RelayedVerdict.evidence 必須非空（外部證據本體，如 CVSS vector）——"
                "無證據不可鑄裁決，缺證據退 NoisePosition(indeterminate)（§8.13）"
            )
        if self.score is not None and not (0.0 <= self.score <= 10.0):
            raise ValueError("RelayedVerdict.score（CVSS）必須在 [0,10]")


@dataclass(frozen=True)
class PresenceFlagPosition:
    """CWA 多選旗標：封閉詞彙集中的獨立 presence 旗標（非單選互斥）。

    與 SignalPosition 區別：Signal＝單選（payload 是兄弟集中的『那一個』）；
    PresenceFlag＝多選（payload 是詞彙集的『子集』、旗標可共現）。vocabulary 暴露
    封閉旗標全集（agent 知可能性空間）；未列入 present 的旗標＝**未舉此旗標**
    （fact-finder 守界：不自鑄「已驗證 clear」——生產者只條件式檢查）。
    glosses＝per-flag 極短意義（tuple of (flag, gloss) pairs，frozen-hashable）。
    """
    vocabulary: tuple[str, ...]                 # 全部可能旗標（CWA 封閉詞彙）
    glosses: tuple[tuple[str, str], ...] = ()   # per-flag (flag, 極短意義)

    def __post_init__(self) -> None:
        if not self.vocabulary:
            raise ValueError("PresenceFlagPosition.vocabulary 必須非空（封閉詞彙集）")
        gloss_keys = {k for k, _ in self.glosses}
        if not gloss_keys <= set(self.vocabulary):
            raise ValueError("PresenceFlagPosition.glosses 的 flag 必須 ⊆ vocabulary")


# Position union——S3 階段 4 變體＋presence-flag 第 5 變體（S0 §3a 完整 union）。
Position = (
    SignalPosition | ReservedPassthrough | NoisePosition | RelayedVerdict
    | PresenceFlagPosition
)


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
        if isinstance(self.position, PresenceFlagPosition):
            if not set(self.payload) <= set(self.position.vocabulary):
                raise ValueError(
                    f"payload {self.payload!r} 含 vocabulary 外旗標——"
                    f"present 子集必須 ⊆ {self.position.vocabulary!r}"
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
    if isinstance(position, NoisePosition):
        return {
            "kind": "noise",
            "gap_kind": position.gap_kind,
            "cardinality": position.cardinality,
            "proportion": position.proportion,
            "aggregated": position.aggregated,
        }
    if isinstance(position, RelayedVerdict):
        return {
            "kind": "relayed_verdict",
            "authority": position.authority,
            "evidence": position.evidence,
            "score": position.score,
        }
    if isinstance(position, PresenceFlagPosition):
        return {
            "kind": "presence_flag",
            "vocabulary": list(position.vocabulary),
            "glosses": {k: v for k, v in position.glosses},
        }
    raise TypeError(f"未知 position 變體：{type(position).__name__}")
