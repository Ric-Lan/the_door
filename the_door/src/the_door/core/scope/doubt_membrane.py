"""doubt 線的膜詞彙：把 doubt 三 enum 的每值意義結構化為 SignalPosition。

意義來源單一化（種子檔 §8.10）：current_state 的前件/後件/共依從 DoubtLifecycle
導出（不重寫死文法）；gloss＝極短指稱注解（此處唯一手寫處）。
S2–S7 照此樣板各建 {domain}_membrane.py。
"""
from __future__ import annotations

from the_door.core.membrane import MembraneElement, ReservedPassthrough, SignalPosition
from the_door.core.scope.doubt_lifecycle import DoubtLifecycle

_LC = DoubtLifecycle()

# 唯一手寫處：每值極短 gloss（人類意圖殘餘，語法捕不到）。
_STATE_GLOSS = {
    "discovered": "剛發現、未調查",
    "investigating": "調查中（已指派）",
    "escalated": "已升級待裁決",
    "explained": "已查證為預期行為、非缺陷（終態）",
    "fixed": "已修復（終態）",
    "accepted_risk": "風險已接受（終態）",
}
_TYPE_GLOSS = {
    "out_of_scope": "超出已宣告範圍",
    "in_scope_incomplete": "範圍內但不完整",
    "anomaly": "異常、與預期不符",
    "low_confidence": "抽取信心低",
}
_RESOLUTION_GLOSS = {  # ＝ _RESOLVING_STATES，終態裁決方式
    "explained": "查證為預期行為",
    "fixed": "已修復",
    "accepted_risk": "風險已接受",
}


def current_state_signal(value: str) -> SignalPosition:
    """current_state（6 值圖）→ Signal；文法從 DoubtLifecycle 導出。"""
    states = tuple(_LC.VALID_TRANSITIONS.keys())
    preconds = tuple(s for s, tos in _LC.VALID_TRANSITIONS.items() if value in tos)
    return SignalPosition(
        contrasts=states,
        gloss=_STATE_GLOSS[value],
        preconditions=preconds,                                  # 反查圖
        consequences=("terminal",) if _LC.is_terminal(value) else
                     tuple(sorted(_LC.VALID_TRANSITIONS[value])),  # 可達 targets
        co_requires=("reason",) if value in _LC._RESOLVING_STATES else (),
    )


def doubt_type_signal(value: str) -> SignalPosition:
    """doubt_type（4 值純 enum）→ Signal（只 contrasts+gloss）。"""
    return SignalPosition(contrasts=tuple(_TYPE_GLOSS.keys()), gloss=_TYPE_GLOSS[value])


def resolution_type_signal(value: str) -> SignalPosition:
    """resolution.type（3 值純 enum）→ Signal；contrasts＝_RESOLVING_STATES。"""
    return SignalPosition(
        contrasts=tuple(sorted(_LC._RESOLVING_STATES)), gloss=_RESOLUTION_GLOSS[value]
    )


def current_state_element(value: str) -> MembraneElement:
    return MembraneElement(payload=value, position=current_state_signal(value))


def doubt_type_element(value: str) -> MembraneElement:
    return MembraneElement(payload=value, position=doubt_type_signal(value))


def resolution_type_element(value: str) -> MembraneElement:
    return MembraneElement(payload=value, position=resolution_type_signal(value))


def free_text_element(text: str) -> MembraneElement:
    """doubt 線的 free-text（reason／resolution.description）＝reserved 窗。"""
    return MembraneElement(payload=text, position=ReservedPassthrough())


# === input schema 衍生（零副本：input 的 enum+description 從 gloss 建構，非手抄）===
_TARGET_STATES = ("investigating", "explained", "fixed", "escalated", "accepted_risk")  # discovered 非 target


def _enum_schema(keys: tuple[str, ...], gloss: dict[str, str], lead: str) -> dict:
    """enum＝contrasts（結構化封閉集）；description＝lead＋gloss 串接（§8.10：contrasts+gloss）。"""
    return {
        "type": "string",
        "enum": list(keys),
        "description": lead + "；".join(f"{k}={gloss[k]}" for k in keys) + "。",
    }


def target_state_schema() -> dict:
    return _enum_schema(_TARGET_STATES, _STATE_GLOSS, "目標狀態。")


def state_filter_schema() -> dict:
    return _enum_schema(tuple(_STATE_GLOSS.keys()), _STATE_GLOSS, "依狀態篩選。")


def type_filter_schema() -> dict:
    return _enum_schema(tuple(_TYPE_GLOSS.keys()), _TYPE_GLOSS, "依類型篩選。")
