"""Unit tests for narrative_chain module.

Tests are written BEFORE implementation (TDD red phase).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from the_door.core.reading.narrative_chain import NarrativeChain
from the_door.models import NarrativeRecord, NarrativeNodeRead, StructureJSON, ASTNode, TopologyEntry


class TestNarrativeChainAppendAndRead:
    """Unit tests for NarrativeChain append + read_all."""

    def test_append_and_read_all_round_trip(self, tmp_path: Path):
        """append + read_all round-trip preserves records."""
        chain_path = tmp_path / "chain.jsonl"
        chain = NarrativeChain(chain_path)

        record = NarrativeRecord(
            record_type="batch",
            timestamp="2025-01-15T10:30:00Z",
            batch=1,
            strategy="topology_guided",
            nodes_read=[
                NarrativeNodeRead(node_id="app.py::login", topology_rank=1, in_degree=0, is_entry_point=True)
            ],
            llm_judgment="Identified 1 feature",
            pruned_nodes=["app.py::login"],
            pending_low_confidence=[],
        )
        chain.append(record)

        records = chain.read_all()
        assert len(records) == 1
        assert records[0].record_type == "batch"
        assert records[0].batch == 1
        assert records[0].timestamp == "2025-01-15T10:30:00Z"
        assert len(records[0].nodes_read) == 1
        assert records[0].nodes_read[0].node_id == "app.py::login"

    def test_empty_chain_returns_empty_list(self, tmp_path: Path):
        """Empty chain file → read_all returns empty list."""
        chain_path = tmp_path / "chain.jsonl"
        chain_path.write_text("")
        chain = NarrativeChain(chain_path)

        records = chain.read_all()
        assert records == []

    def test_nonexistent_file_returns_empty_list(self, tmp_path: Path):
        """Nonexistent chain file → read_all returns empty list."""
        chain_path = tmp_path / "nonexistent.jsonl"
        chain = NarrativeChain(chain_path)

        records = chain.read_all()
        assert records == []

    def test_corrupted_line_skipped_with_warning(self, tmp_path: Path):
        """Corrupted JSONL line → skipped with warning, valid records preserved."""
        chain_path = tmp_path / "chain.jsonl"
        chain_path.write_text(
            '{"record_type": "batch", "timestamp": "2025-01-15T10:30:00Z", "batch": 1, '
            '"strategy": "topology_guided", "nodes_read": [], "llm_judgment": "test", '
            '"pruned_nodes": [], "pending_low_confidence": []}\n'
            'this is not valid json\n'
            '{"record_type": "regeneration", "timestamp": "2025-01-15T11:00:00Z", '
            '"feature_id": "feat-auth", "previous_summary": "old", "new_summary": "new"}\n'
        )
        chain = NarrativeChain(chain_path)

        records = chain.read_all()
        assert len(records) == 2
        assert records[0].record_type == "batch"
        assert records[1].record_type == "regeneration"


class TestNarrativeChainGetLastState:
    """Unit tests for NarrativeChain.get_last_state()."""

    def test_get_last_state_returns_last_batch(self, tmp_path: Path):
        """get_last_state returns last batch record's state."""
        chain_path = tmp_path / "chain.jsonl"
        chain = NarrativeChain(chain_path)

        chain.append(NarrativeRecord(
            record_type="batch", timestamp="2025-01-15T10:30:00Z", batch=1,
            strategy="topology_guided", nodes_read=[], llm_judgment="batch 1",
            pruned_nodes=["node_a"], pending_low_confidence=[],
        ))
        chain.append(NarrativeRecord(
            record_type="batch", timestamp="2025-01-15T10:31:00Z", batch=2,
            strategy="topology_guided", nodes_read=[], llm_judgment="batch 2",
            pruned_nodes=["node_a", "node_b"], pending_low_confidence=["node_c"],
        ))

        state = chain.get_last_state()
        assert state is not None
        assert state.batch == 2
        assert state.pruned_nodes == ["node_a", "node_b"]


class TestNarrativeChainStructuralChange:
    """Unit tests for structural change detection."""

    def test_identical_structures_returns_none(self, tmp_path: Path):
        """detect_structural_change with identical structures → None."""
        chain = NarrativeChain(tmp_path / "chain.jsonl")

        nodes = [ASTNode(node_id="app.py::func", type="function", name="func", file="app.py", language="python")]
        topo = [TopologyEntry(node_id="app.py::func", in_degree=0, out_degree=0, topology_rank=1, is_entry_point=True, batch_assignment=1)]
        structure = StructureJSON(nodes=nodes, topology=topo)

        result = chain.detect_structural_change(structure, structure)
        assert result is None

    def test_added_removed_nodes_detected(self, tmp_path: Path):
        """detect_structural_change with added/removed nodes → correct change summary."""
        chain = NarrativeChain(tmp_path / "chain.jsonl")

        before_nodes = [
            ASTNode(node_id="app.py::func_a", type="function", name="func_a", file="app.py", language="python"),
            ASTNode(node_id="app.py::func_b", type="function", name="func_b", file="app.py", language="python"),
        ]
        after_nodes = [
            ASTNode(node_id="app.py::func_a", type="function", name="func_a", file="app.py", language="python"),
            ASTNode(node_id="app.py::func_c", type="function", name="func_c", file="app.py", language="python"),
        ]

        before = StructureJSON(nodes=before_nodes)
        after = StructureJSON(nodes=after_nodes)

        result = chain.detect_structural_change(before, after)
        assert result is not None
        assert "app.py::func_c" in result.added_nodes
        assert "app.py::func_b" in result.removed_nodes


class TestNarrativeChainRecordTypes:
    """Unit tests for different record types."""

    def test_regeneration_record_stored_and_retrieved(self, tmp_path: Path):
        """Regeneration record type correctly stored and retrieved."""
        chain = NarrativeChain(tmp_path / "chain.jsonl")

        record = NarrativeRecord(
            record_type="regeneration",
            timestamp="2025-01-15T11:00:00Z",
            feature_id="feat-auth",
            previous_summary="Old summary",
            new_summary="New summary",
        )
        chain.append(record)

        records = chain.read_all()
        assert len(records) == 1
        assert records[0].record_type == "regeneration"
        assert records[0].feature_id == "feat-auth"
        assert records[0].previous_summary == "Old summary"
        assert records[0].new_summary == "New summary"

    def test_structural_change_record_stored_and_retrieved(self, tmp_path: Path):
        """structural_change record type correctly stored and retrieved."""
        chain = NarrativeChain(tmp_path / "chain.jsonl")

        record = NarrativeRecord(
            record_type="structural_change",
            timestamp="2025-01-16T09:00:00Z",
            added_nodes=["new.py::func"],
            removed_nodes=["old.py::func"],
            modified_nodes=["app.py::main"],
        )
        chain.append(record)

        records = chain.read_all()
        assert len(records) == 1
        assert records[0].record_type == "structural_change"
        assert records[0].added_nodes == ["new.py::func"]
        assert records[0].removed_nodes == ["old.py::func"]
        assert records[0].modified_nodes == ["app.py::main"]


class TestNarrativeChainHumanReadable:
    """Unit tests for format_human_readable."""

    def test_format_produces_readable_output(self, tmp_path: Path):
        """format_human_readable produces readable output."""
        chain = NarrativeChain(tmp_path / "chain.jsonl")

        chain.append(NarrativeRecord(
            record_type="batch", timestamp="2025-01-15T10:30:00Z", batch=1,
            strategy="topology_guided",
            nodes_read=[NarrativeNodeRead(node_id="app.py::login", topology_rank=1, in_degree=0, is_entry_point=True)],
            llm_judgment="Identified feature",
            pruned_nodes=["app.py::login"], pending_low_confidence=[],
        ))

        output = chain.format_human_readable()
        assert isinstance(output, str)
        assert len(output) > 0
        assert "batch" in output.lower() or "1" in output
