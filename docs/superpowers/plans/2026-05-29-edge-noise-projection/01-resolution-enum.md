# Task 01: Resolution Enum Extension

**Files:**
- Modify: `the_door/src/the_door/models.py:41`
- Test: `the_door/tests/unit/core/test_models_resolution.py` (new)
- Test: `the_door/tests/unit/core/diff/test_diff_engine_ignores_resolution.py` (new)

**Goal:** 把 `Edge.resolution` 的合法值從 4 個擴張為 5 個（加 `name_match_ambiguous`），並用 source-level regression test 釘住「diff engine 從不讀取 `edge.resolution`」這個事實，避免未來有人新增 diff 模組時把 resolution 帶入比對。

**Why source-level guard:** `Edge.resolution` 不參與 diff（已 grep 驗證），構造完整 `VersionSnapshot` fixture 只為了證明這點是 over-engineering。改用對 `core/diff/` 全資料夾的 source scan，未來新增 diff 模組也會被自動檢出。

---

- [ ] **Step 1: Write the failing unit test**

Create `the_door/tests/unit/core/test_models_resolution.py`:

```python
"""Edge.resolution accepts the new name_match_ambiguous value."""
from the_door.models import Edge


def test_edge_accepts_name_match_ambiguous_resolution():
    """name_match_ambiguous is a valid resolution value."""
    edge = Edge(
        from_node="a",
        to_node="b",
        type="calls",
        resolution="name_match_ambiguous",
    )
    assert edge.resolution == "name_match_ambiguous"


def test_edge_resolution_legacy_default_unchanged():
    """Default resolution remains 'name_match' for backward compat."""
    edge = Edge(from_node="a", to_node="b", type="calls")
    assert edge.resolution == "name_match"


def test_edge_all_known_resolutions_accepted():
    """All five known resolution values construct without error."""
    for res in ("scope_rule", "import_alias", "name_match",
                "name_match_ambiguous", "skipped_dynamic"):
        edge = Edge(from_node="a", to_node="b", type="calls", resolution=res)
        assert edge.resolution == res
```

- [ ] **Step 2: Run test**

Run: `cd the_door && python -m pytest tests/unit/core/test_models_resolution.py -v`

Expected: PASS (resolution is `str`, no enum constraint — but these tests pin behavior).

- [ ] **Step 3: Update the comment註記 in `models.py`**

Edit `the_door/src/the_door/src/the_door/models.py:41` (or the closest line that defines `resolution`):

```python
    resolution: str = "name_match"  # "scope_rule" | "import_alias" | "name_match" | "name_match_ambiguous" | "skipped_dynamic"
```

(Just add `| "name_match_ambiguous"` to the inline comment.)

- [ ] **Step 4: Write the source-level diff regression guard**

Create `the_door/tests/unit/core/diff/test_diff_engine_ignores_resolution.py`:

```python
"""Source-level guard: nothing in core/diff/ reads edge.resolution.

This guarantees adding new resolution values (e.g. name_match_ambiguous)
cannot cause spurious diff churn between snapshots.

If a future diff module legitimately needs resolution, this test should
be updated alongside a deliberate decision about bucketing strategy
(see spec §6.4).
"""
from pathlib import Path

import the_door


DIFF_DIR = Path(the_door.__file__).resolve().parent / "core" / "diff"


def test_core_diff_does_not_reference_edge_resolution():
    assert DIFF_DIR.is_dir(), f"diff dir missing: {DIFF_DIR}"
    offenders: list[str] = []
    for py in DIFF_DIR.rglob("*.py"):
        text = py.read_text(encoding="utf-8")
        # Strip comments+docstrings? Too brittle. A plain substring match is
        # the contract: no code OR comment in core/diff/ may reference
        # edge.resolution. If someone wants to add it, they update this test.
        if ".resolution" in text:
            offenders.append(py.name)
    assert offenders == [], (
        f"core/diff modules reference .resolution: {offenders}. "
        f"Adding resolution-aware diff requires updating spec §6.4 and this test."
    )
```

- [ ] **Step 5: Run the regression guard**

Run: `cd the_door && python -m pytest tests/unit/core/diff/test_diff_engine_ignores_resolution.py -v`

Expected: PASS — `core/diff/` 確認不引用 `.resolution`。

If FAIL: stop. 某個 diff 模組偷偷讀了 resolution，需要先決定 spec §6.4 bucket 策略再繼續。

- [ ] **Step 6: Run the full test suite**

Run: `cd the_door && python -m pytest 2>&1 | tail -5`

Expected: 既有測試全 PASS，+ 4 new passed。

- [ ] **Step 7: Commit**

```bash
git add the_door/src/the_door/models.py \
        the_door/tests/unit/core/test_models_resolution.py \
        the_door/tests/unit/core/diff/test_diff_engine_ignores_resolution.py
git commit -m "feat(edge): add name_match_ambiguous resolution + diff source guard"
```
