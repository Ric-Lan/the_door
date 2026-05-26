"""Tests for handle_post_analyze."""
from __future__ import annotations
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from the_door.core.ui.api_handlers import APIHandlers
from the_door.core.ui.job_store import JobStore


def _make_handlers(tmp_path: Path) -> APIHandlers:
    return APIHandlers(project_root=tmp_path, job_store=JobStore())


def test_analyze_config_accepts_extra_ignore_and_label():
    from the_door.models import AnalyzeConfig
    cfg = AnalyzeConfig(extra_ignore=["tests/", "docs/"], snapshot_label="v1.0.0")
    assert cfg.extra_ignore == ["tests/", "docs/"]
    assert cfg.snapshot_label == "v1.0.0"


def test_analyze_config_defaults_are_none():
    from the_door.models import AnalyzeConfig
    cfg = AnalyzeConfig()
    assert cfg.extra_ignore is None
    assert cfg.snapshot_label is None
