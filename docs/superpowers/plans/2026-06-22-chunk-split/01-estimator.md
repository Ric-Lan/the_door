# Phase 1 — Token 估計器

> 父計畫：[../2026-06-22-chunk-split-plan.md](../2026-06-22-chunk-split-plan.md)。先讀其「關鍵事實」。
> pytest 從 repo root 跑，路徑形如 `the_door/tests/...`；`from the_door...` import 因 editable 安裝可解析。
> 環境：Windows，必要時 `PYTHONUTF8=1`；hook 擋 Bash 含 `python -c`/`python x.py`/`grep`/`cat`/`find`/`head`/`tail`/`rg`，用 `python -m pytest` 與 Read/Grep/Glob，commit 用 `git commit -F` heredoc。

建立模組骨架與逐節點 token 估計器。**鐵則：不寫死 per-node 常數，CJK 字元另計**（1 中文字 ≈ 1 token 但僅 1 char）。

---

### Task 1: `estimate_tokens` + `_is_cjk`

**Files:**
- Create: `the_door/src/the_door/core/structure_view/chunk_planner.py`
- Test: `the_door/tests/unit/core/structure_view/test_chunk_estimator.py`

- [ ] **Step 1: 寫失敗測試**

建 `the_door/tests/unit/core/structure_view/test_chunk_estimator.py`：

```python
from the_door.core.structure_view import chunk_planner as cp


def test_is_cjk_detects_chinese_and_ascii():
    assert cp._is_cjk("中") is True
    assert cp._is_cjk("あ") is True   # 假名
    assert cp._is_cjk("a") is False
    assert cp._is_cjk("{") is False


def test_estimate_tokens_ascii_is_quarter_chars():
    # 純 ASCII view：token ≈ chars/4
    view = {"node_id": "a.py::f", "name": "f", "docstring": "x" * 100}
    import json
    chars = len(json.dumps(view, ensure_ascii=False))
    est = cp.estimate_tokens(view)
    assert est == (chars + 3) // 4


def test_estimate_tokens_cjk_counted_near_one_per_char():
    # 中文 docstring：每個中文字 ≈ 1 token，遠高於 ascii 的 1/4
    ascii_view = {"node_id": "a.py::f", "docstring": "x" * 200}
    cjk_view = {"node_id": "a.py::f", "docstring": "說" * 200}
    assert cp.estimate_tokens(cjk_view) > cp.estimate_tokens(ascii_view) * 2
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `python -m pytest the_door/tests/unit/core/structure_view/test_chunk_estimator.py -v`
Expected: FAIL（`chunk_planner` 模組不存在 → ImportError/ModuleNotFoundError）

- [ ] **Step 3: 寫模組骨架 + 估計器**

建 `the_door/src/the_door/core/structure_view/chunk_planner.py`：

```python
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
```

- [ ] **Step 4: 跑測試確認通過**

Run: `python -m pytest the_door/tests/unit/core/structure_view/test_chunk_estimator.py -v`
Expected: PASS（3 個測試）

- [ ] **Step 5: Commit**

```bash
git add the_door/src/the_door/core/structure_view/chunk_planner.py the_door/tests/unit/core/structure_view/test_chunk_estimator.py
git commit -F - <<'EOF'
feat(chunk-planner): add CJK-aware per-node token estimator

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
```

---

## Phase 1 自審
- spec §4（逐節點實估、CJK 另計、不寫死常數）→ Task 1。✓
- 純函式、stdlib only（json）、無 placeholder。✓
- 型別：`estimate_tokens(view:dict)->int`、`_is_cjk(ch:str)->bool`，後續 phase 依此呼叫。✓
