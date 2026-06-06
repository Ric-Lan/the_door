"""scope 線的膜詞彙：把 scope_state 3-值 enum 的每值意義結構化為 SignalPosition。

scope_state＝feature 對 ScopeDefinition 的範圍驗核分類（scope_verifier.verify）：由
(在 scope定義?) × (在 L1?) 的 2×2 presence 比對產生三值，**全覆蓋、恆指派、無格外殘餘、
無缺值**（verify 對每 feature 恆得一值）⟹ 純格內 Signal、無 None 分支、無 NoisePosition。

意義來源單一化（種子檔 §8.10）：SCOPE_CONTRASTS＝唯一來源；gloss＝此處唯一手寫。
承 S1 doubt_type 樣板（純 enum：只 contrasts+gloss）。scope_state 與 doubt_type 共享
'out_of_scope'/'in_scope_incomplete' 兩字串但 contrasts 集不同（3 vs 4）＝正交軸、不單源化
（種子檔 §181 軸正交；強綁不同 contrast 集才是同縫別名）。
"""
from __future__ import annotations

from the_door.core.membrane import MembraneElement, SignalPosition

# 唯一來源：scope_state 封閉 3 值（categorical、非全序——2×2 presence 分類）。
SCOPE_CONTRASTS: tuple[str, ...] = (
    "in_scope_complete",
    "in_scope_incomplete",
    "out_of_scope",
)

# 唯一手寫處：每值極短 gloss（人類意圖殘餘，語法捕不到）。
_GLOSS = {
    "in_scope_complete": "範圍內且已實作（scope 定義 ∩ L1）",
    "in_scope_incomplete": "範圍內但未見實作（僅 scope 定義）",
    "out_of_scope": "已實作但不在宣告範圍（僅 L1）",
}


def scope_signal(value: str) -> SignalPosition:
    """scope_state（3 值 categorical enum）→ Signal（只 contrasts+gloss，承 doubt_type 樣板）。"""
    return SignalPosition(contrasts=SCOPE_CONTRASTS, gloss=_GLOSS[value])


def scope_element(value: str) -> MembraneElement:
    """單一 scope_state 值 → MembraneElement（格內 Signal）。

    scope_state 恆有值（verify 恆指派）⟹ 無 None 分支、無 NoisePosition 退路。
    value ∉ SCOPE_CONTRASTS → _GLOSS[value] KeyError（防呆；正常經 verify 守住）。
    """
    return MembraneElement(payload=value, position=scope_signal(value))
