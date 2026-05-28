"""Tests for AnalyzeConfig context_mode field (Task 07)."""
from __future__ import annotations

from the_door.models import AnalyzeConfig


class TestAnalyzeConfigContextMode:
    def test_default_context_mode_is_detail(self):
        cfg = AnalyzeConfig()
        assert cfg.context_mode == "detail"

    def test_accepts_minimal(self):
        cfg = AnalyzeConfig(context_mode="minimal")
        assert cfg.context_mode == "minimal"

    def test_accepts_detail_explicit(self):
        cfg = AnalyzeConfig(context_mode="detail")
        assert cfg.context_mode == "detail"

    def test_invalid_value_stored_without_validation(self):
        # AnalyzeConfig does not validate — BatchReader validates at pipeline time
        cfg = AnalyzeConfig(context_mode="weird")
        assert cfg.context_mode == "weird"
