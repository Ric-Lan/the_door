"""Tests for BatchReader reporter integration."""
from the_door.core.reading.batch_reader import BatchReader


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
