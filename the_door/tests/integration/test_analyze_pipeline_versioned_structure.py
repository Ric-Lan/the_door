"""Integration tests: analyze_pipeline writes per-version structure non-fatally."""
from __future__ import annotations

import logging
import shutil
from pathlib import Path

import pytest

from the_door.core.diff.snapshot_store import SnapshotStore
from the_door.core.pipeline.analyze_pipeline import run_analyze_pipeline
from the_door.core.reading.batch_reader import BatchReadResult
from the_door.models import AnalyzeConfig, L1Output

_PYTHON_SIMPLE = (
    Path(__file__).parent.parent / "fixtures" / "sample_codebases" / "python_simple"
)


async def _async_return(value):
    return value


@pytest.fixture()
def tiny_python_fixture(tmp_path):
    """Copy the smallest Python sample codebase into a writable tmp directory."""
    dst = tmp_path / "codebase"
    shutil.copytree(_PYTHON_SIMPLE, dst)
    return dst


@pytest.fixture()
def _stub_llm(monkeypatch):
    """Patch create_provider and BatchReader.read to avoid network calls."""
    from tests.conftest import MockLLMProvider

    stub = MockLLMProvider(responses="")
    monkeypatch.setattr(
        "the_door.core.pipeline.analyze_pipeline.create_provider",
        lambda *a, **k: stub,
    )
    empty_result = BatchReadResult(
        l1_output=L1Output(), total_batches=0, total_tokens_used=0
    )
    monkeypatch.setattr(
        "the_door.core.reading.batch_reader.BatchReader.read",
        lambda self, *a, **k: _async_return(empty_result),
    )


def test_analyze_pipeline_writes_versioned_structure(
    tiny_python_fixture, _stub_llm
):
    config = AnalyzeConfig(skip_cost_confirm=True, offline_vuln=True)
    result = run_analyze_pipeline(codebase_path=tiny_python_fixture, config=config)

    snapshot = result.snapshot
    gz_path = (
        tiny_python_fixture / ".the-door" / "structures" / f"{snapshot.version_id}.json.gz"
    )
    assert gz_path.is_file()

    loaded = SnapshotStore(tiny_python_fixture).get_structure(snapshot.version_id)
    assert loaded is not None
    # Option 3: verify the round-trip preserved structural integrity, not just
    # non-emptiness.  Every node must carry the three identity fields that
    # downstream L2/L3 stages rely on; a "garbage payload" bug would surface here.
    assert len(loaded.nodes) > 0
    assert all(
        node.node_id and node.name and node.file
        for node in loaded.nodes
    ), "every node must have truthy node_id, name, and file after round-trip"


def test_analyze_pipeline_versioned_structure_write_failure_is_nonfatal(
    tiny_python_fixture, _stub_llm, monkeypatch, caplog
):
    monkeypatch.setattr(
        "the_door.core.pipeline.analyze_pipeline.write_versioned_structure",
        lambda *a, **k: (_ for _ in ()).throw(IOError("disk full")),
    )

    config = AnalyzeConfig(skip_cost_confirm=True, offline_vuln=True)
    with caplog.at_level(logging.WARNING):
        result = run_analyze_pipeline(codebase_path=tiny_python_fixture, config=config)

    assert result is not None
    assert any("versioned_structure_write_failed" in r.message for r in caplog.records)
