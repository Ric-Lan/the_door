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


def test_ast_extractor_accepts_extra_ignore(tmp_path):
    from the_door.core.extraction.ast_extractor import ASTExtractor
    (tmp_path / "main.py").write_text("def hello(): pass", encoding="utf-8")
    extractor = ASTExtractor()
    result = extractor.extract(str(tmp_path), extra_ignore=["tests/"])
    assert result is not None


def test_analyze_pipeline_passes_extra_ignore_to_extractor(tmp_path):
    """run_analyze_pipeline calls ASTExtractor.extract with extra_ignore."""
    from the_door.models import AnalyzeConfig
    from the_door.core.pipeline.analyze_pipeline import run_analyze_pipeline

    config = AnalyzeConfig(skip_cost_confirm=True, extra_ignore=["docs/"])

    with patch("the_door.core.pipeline.analyze_pipeline.ASTExtractor") as MockExtractor, \
         patch("the_door.core.pipeline.analyze_pipeline.VulnerabilityScanner"), \
         patch("the_door.core.pipeline.analyze_pipeline.SnapshotStore"), \
         patch("the_door.core.pipeline.analyze_pipeline.ConfigManager"):

        mock_extractor_instance = MagicMock()
        mock_extractor_instance.extract.return_value = MagicMock(files=[], nodes=[], edges=[])
        MockExtractor.return_value = mock_extractor_instance

        try:
            run_analyze_pipeline(tmp_path, config)
        except Exception:
            pass

        call_kwargs = mock_extractor_instance.extract.call_args
        assert call_kwargs is not None, "extractor.extract was never called"
        passed_extra_ignore = (
            call_kwargs.kwargs.get("extra_ignore") or
            (call_kwargs.args[1] if len(call_kwargs.args) > 1 else None)
        )
        assert passed_extra_ignore == ["docs/"]


def test_handle_post_analyze_returns_202_with_job_id(tmp_path):
    handlers = _make_handlers(tmp_path)
    with patch("the_door.core.ui.api_handlers.threading.Thread") as mock_thread_cls:
        mock_thread_cls.return_value = MagicMock()
        status, body = handlers.handle_post_analyze({})
    assert status == 202
    assert "job_id" in body


def test_handle_post_analyze_passes_extra_ignore_and_label(tmp_path):
    handlers = _make_handlers(tmp_path)
    with patch("the_door.core.ui.api_handlers.threading.Thread") as mock_thread_cls:
        mock_thread_cls.return_value = MagicMock()
        handlers.handle_post_analyze({"extra_ignore": ["tests/"], "label": "v1.0.0"})
    _, kwargs = mock_thread_cls.call_args
    assert kwargs["args"][1] == ["tests/"]   # extra_ignore
    assert kwargs["args"][2] == "v1.0.0"     # snapshot_label


def test_handle_post_analyze_returns_409_when_job_running(tmp_path):
    handlers = _make_handlers(tmp_path)
    with patch.object(handlers._job_store, "try_create_job", return_value=None):
        status, body = handlers.handle_post_analyze({})
    assert status == 409
    assert body["error"]["code"] == "job_already_running"


def test_handle_post_analyze_empty_extra_ignore_becomes_none(tmp_path):
    handlers = _make_handlers(tmp_path)
    with patch("the_door.core.ui.api_handlers.threading.Thread") as mock_thread_cls:
        mock_thread_cls.return_value = MagicMock()
        handlers.handle_post_analyze({"extra_ignore": [], "label": ""})
    _, kwargs = mock_thread_cls.call_args
    assert kwargs["args"][1] is None   # extra_ignore normalized to None
    assert kwargs["args"][2] is None   # snapshot_label normalized to None


def test_create_auto_snapshot_passes_label_to_store(tmp_path):
    """_create_auto_snapshot passes config.snapshot_label to store.create_snapshot."""
    from the_door.core.pipeline.analyze_pipeline import _create_auto_snapshot
    from the_door.models import AnalyzeConfig

    config = AnalyzeConfig(snapshot_label="v1.0.0")
    extraction = MagicMock(files=[], nodes=[], edges=[])
    result = MagicMock()
    result.l1_output.features = []
    result.l1_output.feature_relations = []
    scan_result = MagicMock(entries=[], db_freshness=None)

    with patch("the_door.core.pipeline.analyze_pipeline.SnapshotStore") as MockStore:
        MockStore.return_value.create_snapshot.return_value = MagicMock(version_id="v1")
        _create_auto_snapshot(tmp_path, extraction, result, scan_result, lambda _: None, config)

    kwargs = MockStore.return_value.create_snapshot.call_args.kwargs
    assert kwargs.get("label") == "v1.0.0"
