"""Round-trip tests for write_versioned_structure / SnapshotStore.get_structure."""
from __future__ import annotations

import gzip
from pathlib import Path

import pytest

from the_door.core.extraction.structure_serializer import build_structure_dict
from the_door.core.diff.snapshot_store import SnapshotStore
from the_door.models import StructureJSON


def _sample_structure() -> StructureJSON:
    return StructureJSON(
        files=[],
        nodes=[],
        edges=[],
        topology=[],
    )


class TestWriteAndReadRoundtrip:
    def test_write_and_read_roundtrip(self, tmp_path):
        from the_door.core.extraction.structure_serializer import write_versioned_structure

        vid = "11111111-2222-3333-4444-555555555555"
        structure = _sample_structure()
        path = write_versioned_structure(tmp_path, vid, structure, scan_result=None)
        assert path.exists()
        assert path.name == f"{vid}.json.gz"
        loaded = SnapshotStore(tmp_path).get_structure(vid)
        assert loaded is not None
        assert build_structure_dict(loaded, scan_result=None) == build_structure_dict(
            structure, scan_result=None
        )

    def test_get_structure_missing_returns_none(self, tmp_path):
        assert SnapshotStore(tmp_path).get_structure("does-not-exist") is None

    def test_get_structure_corrupted_gzip_warns_returns_none(self, tmp_path):
        dst = tmp_path / ".the-door" / "structures"
        dst.mkdir(parents=True)
        (dst / "vid.json.gz").write_bytes(b"\x1f\x8bnotgzip")
        with pytest.warns(UserWarning, match="structure_corrupted"):
            result = SnapshotStore(tmp_path).get_structure("vid")
        assert result is None
