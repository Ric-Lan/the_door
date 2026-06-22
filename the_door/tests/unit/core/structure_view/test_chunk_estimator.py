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
