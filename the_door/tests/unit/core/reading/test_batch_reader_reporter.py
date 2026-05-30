"""Tests for BatchReader reporter integration."""
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

from the_door.core.reading.batch_reader import BatchReader
from the_door.models import ASTNode, StructureJSON, TopologyEntry


def test_batch_reader_init_accepts_reporter_kwarg():
    sig = BatchReader.__init__.__code__.co_varnames
    assert "reporter" in sig, "BatchReader.__init__ must accept reporter kwarg"


def test_batch_reader_default_reporter_is_noop():
    """Construction without reporter must default to NoOp (no caller wiring required)."""
    from unittest.mock import MagicMock
    from the_door.core.pipeline.progress_reporter import NoOpProgressReporter
    structure = MagicMock()
    structure.nodes = []
    structure.edges = []
    structure.topology = None
    br = BatchReader(llm_provider=MagicMock(), structure=structure)
    assert isinstance(br._reporter, NoOpProgressReporter)


def test_batch_read_calls_reporter_per_file():
    """BatchReader.read() must call reporter.report_file for each node processed."""
    # Build a minimal structure with 2 nodes in different files
    node_a = ASTNode(node_id="a.py::func_a", type="function", name="func_a", file="a.py", language="python")
    node_b = ASTNode(node_id="b.py::func_b", type="function", name="func_b", file="b.py", language="python")
    topo_a = TopologyEntry(node_id="a.py::func_a", in_degree=0, out_degree=0, topology_rank=0, is_entry_point=True, batch_assignment=1)
    topo_b = TopologyEntry(node_id="b.py::func_b", in_degree=0, out_degree=0, topology_rank=0, is_entry_point=True, batch_assignment=1)

    structure = StructureJSON(
        nodes=[node_a, node_b],
        edges=[],
        topology=[topo_a, topo_b],
    )

    # LLM provider that returns a valid empty response
    llm_response = json.dumps({"features": [], "feature_relations": [], "unclassified_nodes": [], "infrastructure_nodes": []})
    provider = MagicMock()
    provider.complete = AsyncMock(return_value=llm_response)
    provider.estimate_tokens = MagicMock(return_value=10)

    # Recording reporter
    recorded_paths: list[str] = []

    class RecordingReporter:
        def report_file(self, path: str) -> None:
            recorded_paths.append(path)

    reader = BatchReader(llm_provider=provider, structure=structure, reporter=RecordingReporter())
    asyncio.run(reader.read())

    assert "a.py" in recorded_paths
    assert "b.py" in recorded_paths
