"""diff 線的膜詞彙：把 diff_state 兩條閉集 enum（node 5-值／edge 3-值）的每值意義
結構化為 SignalPosition。

diff_state＝版本快照比對的結構分類（diff_engine.compute_l1_diff/_compute_edge_diffs）：
- NodeDiff.diff_state（5 值）：feature/block 在 baseline↔current 的 presence＋屬性/依賴變更分類。
- EdgeDiff.diff_state（3 值）：feature 關係邊的 presence＋關係文字變更分類。
兩者**全覆蓋、恆指派、無格外殘餘、無缺值**（engine 對每筆恆得一值）⟹ 純格內 Signal、
無 None 分支、無 NoisePosition。

兩子軸正交（種子檔 §181 軸正交；S5 C4 判準）：node 與 edge 共享 'added'/'removed' 兩字串
但 contrasts 集不同（5 vs 3）＝同字串在兩集帶不同對比位置＝兩條正交子軸、各自 Signal、
不單源化（強綁不同 contrast 集才是同縫別名）。diff_state 與三主軸（confidence/scope/
provenance）正交（diff 面專屬）。

意義來源單一化（種子檔 §8.10）：NODE_/EDGE_DIFF_CONTRASTS＝emit 詞彙唯一來源；gloss＝
此處唯一手寫。承 S5 scope_membrane（純格內全覆蓋分類軸最小樣板）。
"""
from __future__ import annotations

from the_door.core.membrane import MembraneElement, SignalPosition

# 唯一來源：NodeDiff.diff_state 封閉 5 值（categorical、非全序——結構分類。engine 內有
# 計算優先序〔added/removed terminal、dependency_changed>attribute_changed〕，但該序＝
# 生產端內部裁決、非送達消費端的對比磁量 ⟹ contrasts 不編序）。
NODE_DIFF_CONTRASTS: tuple[str, ...] = (
    "added",
    "removed",
    "attribute_changed",
    "dependency_changed",
    "unchanged",
)

# 唯一來源：EdgeDiff.diff_state 封閉 3 值（categorical）。
EDGE_DIFF_CONTRASTS: tuple[str, ...] = (
    "added",
    "removed",
    "modified",
)

# 唯一手寫處：每值極短 gloss（人類意圖殘餘，語法捕不到）。
_NODE_GLOSS = {
    "added": "本版新增（僅現版有此 node）",
    "removed": "本版移除（僅基線有此 node）",
    "attribute_changed": "標籤/描述變更（依賴邊未變）",
    "dependency_changed": "依賴邊變更（屬性變更併入 secondary_changes）",
    "unchanged": "無變更",
}
_EDGE_GLOSS = {
    "added": "新增關係邊（僅現版有）",
    "removed": "移除關係邊（僅基線有）",
    "modified": "關係文字變更（端點不變）",
}


# S8-report：change_type（l1_changes/l2_details）＝diff 軸的 changed-only 閉集
# （4-val、無 unchanged——l1/l2 只收變更項；schema update-report.schema.json:99,143 即此）。
# S6 C4：契約閉集 ≠ node(5-val) ⟹ 獨立 contrasts、不複用 node element（否則謊報 unchanged 為兄弟值）。
CHANGE_TYPE_CONTRASTS: tuple[str, ...] = (
    "added",
    "removed",
    "attribute_changed",
    "dependency_changed",
)


def change_type_signal(value: str) -> SignalPosition:
    """change_type（4 值 categorical enum、無 unchanged）→ Signal。gloss 零副本＝_NODE_GLOSS 子集。"""
    return SignalPosition(contrasts=CHANGE_TYPE_CONTRASTS, gloss=_NODE_GLOSS[value])


def change_type_element(value: str) -> MembraneElement:
    """單一 change_type 值 → MembraneElement（格內 Signal、4-val 閉集）。

    value=="unchanged"：_NODE_GLOSS 有此鍵但 ∉ CHANGE_TYPE_CONTRASTS → MembraneElement I4 ValueError。
    value 不明（如 bogus）：_NODE_GLOSS KeyError。
    """
    return MembraneElement(payload=value, position=change_type_signal(value))


def node_diff_signal(value: str) -> SignalPosition:
    """NodeDiff.diff_state（5 值 categorical enum）→ Signal（contrasts 5-set+gloss）。"""
    return SignalPosition(contrasts=NODE_DIFF_CONTRASTS, gloss=_NODE_GLOSS[value])


def edge_diff_signal(value: str) -> SignalPosition:
    """EdgeDiff.diff_state（3 值 categorical enum）→ Signal（contrasts 3-set+gloss）。"""
    return SignalPosition(contrasts=EDGE_DIFF_CONTRASTS, gloss=_EDGE_GLOSS[value])


def node_diff_element(value: str) -> MembraneElement:
    """單一 NodeDiff.diff_state 值 → MembraneElement（格內 Signal）。

    diff_state 恆有值（engine 恆指派）⟹ 無 None 分支、無 NoisePosition 退路。
    value ∉ NODE_DIFF_CONTRASTS → _NODE_GLOSS[value] KeyError（防呆；正常經 engine 守住）。
    """
    return MembraneElement(payload=value, position=node_diff_signal(value))


def edge_diff_element(value: str) -> MembraneElement:
    """單一 EdgeDiff.diff_state 值 → MembraneElement（格內 Signal）。"""
    return MembraneElement(payload=value, position=edge_diff_signal(value))
