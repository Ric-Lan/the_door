"""Unit tests for ``core/extraction/structure_serializer.py``.

The serializer backs ``the-door extract`` and the ``extract_structure`` MCP
tool, so its output must be stable. These tests fix the on-disk schema.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from the_door.core.extraction.structure_serializer import (
    build_structure_dict,
    default_structure_path,
    write_structure_json,
)
from the_door.models import (
    ASTNode,
    DatabaseFreshness,
    Edge,
    FileInfo,
    ScanResult,
    StructureJSON,
    TopologyEntry,
    VulnerabilityEntry,
)


@pytest.fixture
def empty_structure() -> StructureJSON:
    return StructureJSON()


@pytest.fixture
def populated_structure() -> StructureJSON:
    file_a = FileInfo(path="src/a.py", language="python")
    node_a = ASTNode(
        node_id="src/a.py::Greeter",
        type="class",
        name="Greeter",
        file="src/a.py",
        language="python",
        decorators=[],
        parameters=[],
        return_type=None,
        docstring="Says hi.",
        comments=[],
    )
    node_b = ASTNode(
        node_id="src/a.py::Greeter::hello",
        type="method",
        name="hello",
        file="src/a.py",
        language="python",
        decorators=[],
        parameters=["self"],
        return_type="str",
        docstring=None,
        comments=[],
    )
    edge = Edge(from_node=node_a.node_id, to_node=node_b.node_id, type="contains")
    topo = TopologyEntry(
        node_id=node_a.node_id,
        in_degree=0,
        out_degree=1,
        topology_rank=0,
        is_entry_point=True,
        batch_assignment=1,
    )
    return StructureJSON(
        files=[file_a],
        nodes=[node_a, node_b],
        edges=[edge],
        topology=[topo],
    )


@pytest.fixture
def vuln_scan() -> ScanResult:
    entry = VulnerabilityEntry(
        cve_id="CVE-2024-1234",
        package="left-pad",
        version="1.0.0",
        severity="high",
        cvss=7.5,
        source="osv",
    )
    return ScanResult(
        entries=[entry],
        warnings=[],
        db_freshness=DatabaseFreshness(
            timestamp="2025-01-01T00:00:00Z",
            mode="offline",
            stale_warning="db older than 7 days",
        ),
    )


# ── build_structure_dict ────────────────────────────────────────────


class TestBuildStructureDict:
    def test_empty_structure_yields_empty_arrays(self, empty_structure):
        d = build_structure_dict(empty_structure, scan_result=None)
        assert d == {
            "files": [],
            "nodes": [],
            "edges": [],
            "topology": [],
            "vulnerabilities": [],
        }

    def test_populated_structure_includes_all_sections(self, populated_structure):
        d = build_structure_dict(populated_structure, scan_result=None)
        assert len(d["files"]) == 1
        assert d["files"][0] == {"path": "src/a.py", "language": "python"}
        assert len(d["nodes"]) == 2
        # node fields preserved
        assert d["nodes"][0]["node_id"] == "src/a.py::Greeter"
        assert d["nodes"][0]["docstring"] == "Says hi."
        assert d["nodes"][1]["return_type"] == "str"
        # edges use ``from`` / ``to`` keys (matches existing on-disk shape)
        assert d["edges"][0] == {
            "from": "src/a.py::Greeter",
            "to": "src/a.py::Greeter::hello",
            "type": "contains",
            "resolution": "name_match",
        }
        assert d["topology"][0]["is_entry_point"] is True
        assert d["vulnerabilities"] == []
        assert "vulnerability_db_freshness" not in d

    def test_vulnerabilities_included_when_scan_has_entries(
        self, populated_structure, vuln_scan
    ):
        d = build_structure_dict(populated_structure, vuln_scan)
        assert len(d["vulnerabilities"]) == 1
        assert d["vulnerabilities"][0] == {
            "cve_id": "CVE-2024-1234",
            "package": "left-pad",
            "version": "1.0.0",
            "severity": "high",
            "cvss": 7.5,
            "source": "osv",
            "evidence": "",
        }
        assert d["vulnerability_db_freshness"] == {
            "timestamp": "2025-01-01T00:00:00Z",
            "mode": "offline",
            "stale_warning": "db older than 7 days",
        }

    def test_db_freshness_omitted_when_absent(self, empty_structure):
        scan = ScanResult(entries=[], warnings=[])
        d = build_structure_dict(empty_structure, scan)
        assert "vulnerability_db_freshness" not in d

    def test_none_scan_result_treated_as_no_vulnerabilities(self, populated_structure):
        d = build_structure_dict(populated_structure, None)
        assert d["vulnerabilities"] == []
        assert "vulnerability_db_freshness" not in d

    def test_node_start_end_line_survives_round_trip(self, populated_structure):
        from the_door.core.extraction.structure_serializer import parse_structure_dict
        node = ASTNode(
            node_id="src/f.py::my_func",
            type="function",
            name="my_func",
            file="src/f.py",
            language="python",
            start_line=10,
            end_line=15,
        )
        structure = StructureJSON(
            files=[FileInfo(path="src/f.py", language="python")],
            nodes=[node],
        )
        d = build_structure_dict(structure, scan_result=None)
        assert d["nodes"][0]["start_line"] == 10
        assert d["nodes"][0]["end_line"] == 15
        recovered = parse_structure_dict(d)
        assert recovered.nodes[0].start_line == 10
        assert recovered.nodes[0].end_line == 15

    def test_old_structure_dict_without_line_fields_parses_to_none(self):
        from the_door.core.extraction.structure_serializer import parse_structure_dict
        old_dict = {
            "files": [{"path": "src/a.py", "language": "python"}],
            "nodes": [{
                "node_id": "src/a.py::foo",
                "type": "function",
                "name": "foo",
                "file": "src/a.py",
                "language": "python",
                "decorators": [],
                "parameters": [],
                "return_type": None,
                "docstring": None,
                "comments": [],
            }],
            "edges": [],
            "topology": [],
        }
        result = parse_structure_dict(old_dict)
        assert result.nodes[0].start_line is None
        assert result.nodes[0].end_line is None


# ── default_structure_path ──────────────────────────────────────────


class TestDefaultStructurePath:
    def test_default_path_points_inside_dot_the_door(self, tmp_path):
        p = default_structure_path(tmp_path)
        assert p == tmp_path / ".the-door" / "structure.json"

    def test_accepts_string_input(self):
        p = default_structure_path("/some/code/base")
        assert p == Path("/some/code/base") / ".the-door" / "structure.json"


# ── write_structure_json ────────────────────────────────────────────


class TestWriteStructureJson:
    def test_writes_utf8_json_file(self, tmp_path, populated_structure):
        target = tmp_path / "out.json"
        returned = write_structure_json(target, populated_structure, scan_result=None)
        assert returned == target
        assert target.exists()
        # Round-trip
        loaded = json.loads(target.read_text(encoding="utf-8"))
        assert loaded["nodes"][0]["name"] == "Greeter"

    def test_creates_missing_parent_dirs(self, tmp_path, empty_structure):
        target = tmp_path / "nested" / "deep" / "structure.json"
        write_structure_json(target, empty_structure, scan_result=None)
        assert target.exists()

    def test_overwrites_existing_file(self, tmp_path, empty_structure, populated_structure):
        target = tmp_path / "structure.json"
        write_structure_json(target, empty_structure, scan_result=None)
        write_structure_json(target, populated_structure, scan_result=None)
        loaded = json.loads(target.read_text(encoding="utf-8"))
        assert len(loaded["nodes"]) == 2

    def test_non_ascii_content_round_trips(self, tmp_path):
        # Real codebases (e.g. Traditional Chinese docstrings, emoji) must
        # survive serialization on Windows where the platform locale may be
        # cp950 / cp1252. We force ensure_ascii=False, write UTF-8 bytes.
        node = ASTNode(
            node_id="src/a.py::Greeter",
            type="class",
            name="Greeter",
            file="src/a.py",
            language="python",
            decorators=[],
            parameters=[],
            return_type=None,
            docstring="🎯 中文 docstring",
            comments=[],
        )
        target = tmp_path / "structure.json"
        write_structure_json(
            target,
            StructureJSON(files=[], nodes=[node], edges=[], topology=[]),
            scan_result=None,
        )
        loaded = json.loads(target.read_text(encoding="utf-8"))
        assert loaded["nodes"][0]["docstring"] == "🎯 中文 docstring"
