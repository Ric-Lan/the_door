"""Chunk Split Principle: 純程式把 structure-view 切成 token 預算內的 chunk。

只讀既有 artifact（複用 locator.load_views），零 LLM、純決定性、純加法。
spec: docs/superpowers/specs/2026-06-22-chunk-split-principle-design.md
"""
from __future__ import annotations

import json

# CJK 範圍（通用近似，非窮舉）：中日韓表意 + 假名 + 諺文 + 全形。
_CJK_RANGES = (
    (0x3040, 0x30FF),   # Hiragana + Katakana
    (0x3400, 0x4DBF),   # CJK Ext A
    (0x4E00, 0x9FFF),   # CJK Unified Ideographs
    (0xAC00, 0xD7A3),   # Hangul syllables
    (0xF900, 0xFAFF),   # CJK Compatibility Ideographs
    (0xFF00, 0xFFEF),   # Halfwidth/Fullwidth forms
)


def _is_cjk(ch: str) -> bool:
    o = ord(ch)
    return any(lo <= o <= hi for lo, hi in _CJK_RANGES)


def estimate_tokens(view: dict) -> int:
    """逐節點 token 估計：CJK 每字 ~1 token，其餘 ~4 char/token。保守、不寫死常數。"""
    s = json.dumps(view, ensure_ascii=False)
    cjk = sum(1 for ch in s if _is_cjk(ch))
    other = len(s) - cjk
    return cjk + (other + 3) // 4
