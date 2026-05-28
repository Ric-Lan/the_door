"""Tests that run_analyze_pipeline forwards config.context_mode to BatchReader."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@patch("the_door.core.pipeline.analyze_pipeline.BatchReader")
@patch("the_door.core.pipeline.analyze_pipeline.create_provider")
@patch("the_door.core.pipeline.analyze_pipeline.ASTExtractor")
def test_pipeline_passes_context_mode_to_batch_reader(
    mock_extractor_cls, mock_create_provider, mock_br_class, tmp_path
):
    from the_door.core.pipeline.analyze_pipeline import run_analyze_pipeline
    from the_door.models import AnalyzeConfig, StructureJSON

    mock_structure = MagicMock(spec=StructureJSON)
    mock_structure.files = []
    mock_structure.nodes = []
    mock_structure.edges = []
    mock_structure.topology = []
    mock_extractor_cls.return_value.extract.return_value = mock_structure

    mock_create_provider.return_value = MagicMock()

    mock_br_instance = MagicMock()
    mock_br_instance.read = AsyncMock(return_value=MagicMock(
        l1_output=MagicMock(features=[], feature_relations=[], unclassified_nodes=[], infrastructure_nodes=[], summary=""),
        total_tokens_used=0,
        pruned_node_count=0,
    ))
    mock_br_class.return_value = mock_br_instance

    config = AnalyzeConfig(context_mode="minimal", skip_cost_confirm=True)
    try:
        run_analyze_pipeline(tmp_path, config, progress_callback=lambda m: None)
    except Exception:
        pass

    assert mock_br_class.called, "BatchReader should have been constructed"
    kwargs = mock_br_class.call_args.kwargs if mock_br_class.call_args else {}
    assert kwargs.get("context_mode") == "minimal", (
        f"Expected context_mode='minimal', got {kwargs}"
    )
