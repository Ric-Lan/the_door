"""非-high 信心交叉驗證引導（projection；infra surface 不 judge）。

固定、無狀態、與工具無關的引導：宣告「自評為非-high 信心（觸發處境）的判斷，
可選用哪些已註冊證據工具交叉驗證」。**不掃 payload、不偵測 confidence、不下結論**——
觸發與否、調哪個、結論為何，全由消費端 LLM 自決。

觸發處境 canonical（spec §3.3）＝非-high 信心 ＝ {未評估(None) ∪ 中信心 ∪ 低信心}。
"""
from __future__ import annotations


def verification_guidance() -> dict:
    """回傳固定引導 dict（JSON-safe、決定性）。"""
    return {
        "applies_when": (
            "當你自評當前判斷為非-high 信心（未評估／中信心／低信心）時，"
            "可選用下列已註冊工具交叉驗證；high 信心無需。"
        ),
        "causes": [
            {
                "cause": "unassessed",
                "meaning": "未評估＝你尚未執行評估這個動作（≠ 產出不可評估）。",
                "action": "去調證據工具把評估補做（可填補的流程缺口）。",
            },
            {
                "cause": "low_or_medium",
                "meaning": "中/低信心＝你已評估、但證據不足所顯示的中低水準。",
                "action": "去調證據工具補強證據。",
            },
        ],
        "evidence_tools": [
            {
                "tool": "extract_structure",
                "usage": "查節點 callers/callees/resolution/topology，"
                         "判斷『孤立／低信心邊』是真是假。",
            },
        ],
        "note": "可選、非強制：是否調用、調哪個、結論為何，由你決定。",
    }
