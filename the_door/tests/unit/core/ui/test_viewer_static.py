"""Static-file tests for viewer HTML, CSS, and JS strings.

Reads the static viewer files as text — no browser or server needed.
Run: pytest tests/unit/core/ui/test_viewer_static.py -v
"""
from __future__ import annotations

from pathlib import Path

_VIEWER = (
    Path(__file__).parents[5]
    / "docs"
    / "frontend-local-version-viewer"
    / "viewer"
)
_HTML = _VIEWER / "index.html"
_CSS  = _VIEWER / "styles.css"
# After the Step 10–11 modular refactor, the per-area Chinese labels live in
# js/ui-topbar.js (count badges). We grep that file instead of the deleted
# monolithic app.js.
_UI_TOPBAR = _VIEWER / "js" / "ui-topbar.js"


def _html() -> str:
    return _HTML.read_text(encoding="utf-8")


def _css() -> str:
    return _CSS.read_text(encoding="utf-8")


def _ui_topbar() -> str:
    return _UI_TOPBAR.read_text(encoding="utf-8")


class TestTopbarTooltips:
    """index.html: all topbar controls must have title attributes."""

    def test_btn_diff_has_title(self):
        assert 'title="查看 A 版與 B 版之間的功能差異"' in _html()

    def test_btn_baseline_has_title(self):
        assert 'title="查看 A 版的功能狀態"' in _html()

    def test_btn_current_has_title(self):
        assert 'title="查看 B 版的功能狀態"' in _html()

    def test_select_version_a_has_title(self):
        assert 'title="選擇比較基準版本"' in _html()

    def test_select_version_b_has_title(self):
        assert 'title="選擇要比較的新版本"' in _html()

    def test_count_added_has_title(self):
        assert 'title="B 版相較 A 版新增的功能數量"' in _html()

    def test_count_removed_has_title(self):
        assert 'title="B 版相較 A 版移除的功能數量"' in _html()

    def test_count_modified_has_title(self):
        assert 'title="B 版相較 A 版內容或關聯改變的功能數量"' in _html()

    def test_count_risk_has_title(self):
        assert 'title="需要留意的差異項目數量"' in _html()


class TestChineseLabelsInJS:
    """ui-topbar.js renderTopBar must output Chinese labels."""

    def test_count_added_uses_chinese(self):
        assert "'新增 '" in _ui_topbar()

    def test_count_removed_uses_chinese(self):
        assert "'移除 '" in _ui_topbar()

    def test_count_modified_uses_chinese(self):
        assert "'修改 '" in _ui_topbar()

    def test_count_risk_uses_chinese(self):
        # "注意 " + totalRisk
        assert "'注意 '" in _ui_topbar()


class TestActiveModeButtonCSS:
    """styles.css .mode-button.active must use accent-soft background and accent color."""

    def test_mode_button_active_uses_accent_soft_background(self):
        css = _css()
        idx = css.index(".mode-button.active")
        block_end = css.index("}", idx)
        block = css[idx:block_end]
        assert "var(--accent-soft)" in block

    def test_mode_button_active_color_is_accent(self):
        css = _css()
        idx = css.index(".mode-button.active")
        block_end = css.index("}", idx)
        block = css[idx:block_end]
        assert "color: var(--accent)" in block


class TestModalLanguageField:
    def test_modal_has_language_select(self):
        assert 'id="input-language"' in _html()

    def test_language_select_has_zh_hant_option(self):
        assert 'value="zh-Hant"' in _html()

    def test_language_select_has_en_option(self):
        assert 'value="en"' in _html()
