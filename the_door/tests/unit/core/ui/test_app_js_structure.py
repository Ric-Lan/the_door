"""Characterization tests for app.js function structure.

Reads app.js as text. Fails if key functions are renamed or removed,
and fails if the RI-2 hook stubs do not exist yet.

Run: pytest tests/unit/core/ui/test_app_js_structure.py -v
"""
from __future__ import annotations

from pathlib import Path

_APP_JS = (
    Path(__file__).parents[5]
    / "docs"
    / "frontend-local-version-viewer"
    / "viewer"
    / "app.js"
)


def _src() -> str:
    return _APP_JS.read_text(encoding="utf-8")


class TestExistingFunctions:
    """Guard against accidental rename of existing functions."""

    def test_render_diff_detail_panel_exists(self):
        assert "function renderDiffDetailPanel(" in _src()

    def test_render_detail_panel_diff_exists(self):
        assert "function renderDetailPanelDiff(" in _src()

    def test_render_single_version_detail_panel_exists(self):
        assert "function renderSingleVersionDetailPanel(" in _src()

    def test_render_top_bar_exists(self):
        assert "function renderTopBar(" in _src()

    def test_render_change_list_exists(self):
        assert "function renderChangeList(" in _src()

    def test_submit_update_exists(self):
        assert "function submitUpdate(" in _src()

    def test_attribution_section_exists(self):
        assert "function attributionSection(" in _src()


class TestRI2HookStubs:
    """These fail before RI-2 is implemented."""

    def test_append_diff_explanation_section_stub_exists(self):
        assert "function _appendDiffExplanationSection(" in _src()

    def test_append_user_notes_section_stub_exists(self):
        assert "function _appendUserNotesSection(" in _src()

    def test_diff_explanation_hook_exists_in_file(self):
        src = _src()
        assert "_appendDiffExplanationSection(" in src

    def test_user_notes_hook_exists_in_file(self):
        src = _src()
        assert "_appendUserNotesSection(" in src

    def test_diff_explanation_hook_called_from_both_diff_panels(self):
        # Must appear at least 3 times:
        # once in the function definition, once in renderDiffDetailPanel,
        # once in renderDetailPanelDiff
        src = _src()
        count = src.count("_appendDiffExplanationSection(")
        assert count >= 3, f"Expected ≥3 occurrences (definition + 2 call sites), got {count}"

    def test_user_notes_hook_called_from_all_three_panels(self):
        src = _src()
        count = src.count("_appendUserNotesSection(")
        assert count >= 4, f"Expected ≥4 occurrences (definition + 3 call sites), got {count}"
