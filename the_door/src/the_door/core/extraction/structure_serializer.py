"""Serialize StructureJSON + vulnerability data to the canonical
``.the-door/structure.json`` shape on disk.

Shared by:
- ``the-door extract -o <file>`` CLI
- ``the-door analyze`` pipeline (auto-persist after topology)

The on-disk shape is the union of :class:`StructureJSON` plus the
non-fatal vulnerability scan results. Keeping a single serializer
guarantees both code paths produce byte-identical files for the same
inputs.
"""
from __future__ import annotations

import gzip
import json
from pathlib import Path

from the_door.models import ASTNode, Edge, FileInfo, ScanResult, StructureJSON, TopologyEntry


def build_structure_dict(
    structure: StructureJSON,
    scan_result: ScanResult | None,
) -> dict:
    """Return the canonical dict that ``.the-door/structure.json`` stores."""
    output: dict = {
        "files": [
            {"path": f.path, "language": f.language}
            for f in structure.files
        ],
        "nodes": [
            {
                "node_id": n.node_id, "type": n.type, "name": n.name,
                "file": n.file, "language": n.language,
                "decorators": n.decorators, "parameters": n.parameters,
                "return_type": n.return_type, "docstring": n.docstring,
                "comments": n.comments,
                "start_line": n.start_line, "end_line": n.end_line,
                "body_hash": n.body_hash,
            }
            for n in structure.nodes
        ],
        "edges": [
            {"from": e.from_node, "to": e.to_node, "type": e.type, "resolution": e.resolution}
            for e in structure.edges
        ],
        "topology": [
            {
                "node_id": t.node_id, "in_degree": t.in_degree,
                "out_degree": t.out_degree, "topology_rank": t.topology_rank,
                "is_entry_point": t.is_entry_point,
                "batch_assignment": t.batch_assignment,
            }
            for t in structure.topology
        ],
        "vulnerabilities": [
            {
                "cve_id": v.cve_id, "package": v.package, "version": v.version,
                "severity": v.severity, "cvss": v.cvss, "source": v.source,
                "evidence": v.evidence,
            }
            for v in (scan_result.entries if scan_result else [])
        ],
    }

    if scan_result and scan_result.db_freshness:
        output["vulnerability_db_freshness"] = {
            "timestamp": scan_result.db_freshness.timestamp,
            "mode": scan_result.db_freshness.mode,
            "stale_warning": scan_result.db_freshness.stale_warning,
        }

    return output


def parse_structure_dict(data: dict) -> StructureJSON:
    """Inverse of build_structure_dict. Reconstructs StructureJSON from a parsed dict."""
    files = [
        FileInfo(path=f["path"], language=f["language"])
        for f in data["files"]
    ]
    nodes = [
        ASTNode(
            node_id=n["node_id"],
            type=n["type"],
            name=n["name"],
            file=n["file"],
            language=n["language"],
            decorators=n.get("decorators", []),
            parameters=n.get("parameters", []),
            return_type=n.get("return_type"),
            docstring=n.get("docstring"),
            comments=n.get("comments", []),
            start_line=n.get("start_line"),
            end_line=n.get("end_line"),
            body_hash=n.get("body_hash"),
        )
        for n in data["nodes"]
    ]
    edges = [
        Edge(from_node=e["from"], to_node=e["to"], type=e["type"], resolution=e.get("resolution", "name_match"))
        for e in data["edges"]
    ]
    topology = [
        TopologyEntry(
            node_id=t["node_id"],
            in_degree=t["in_degree"],
            out_degree=t["out_degree"],
            topology_rank=t["topology_rank"],
            is_entry_point=t["is_entry_point"],
            batch_assignment=t["batch_assignment"],
        )
        for t in data["topology"]
    ]
    return StructureJSON(files=files, nodes=nodes, edges=edges, topology=topology)


def write_versioned_structure(
    project_path: Path,
    version_id: str,
    structure: StructureJSON,
    scan_result: ScanResult | None,
) -> Path:
    """Write a gzipped structure dict to .the-door/structures/<version_id>.json.gz."""
    dst_dir = Path(project_path) / ".the-door" / "structures"
    dst_dir.mkdir(parents=True, exist_ok=True)
    path = dst_dir / f"{version_id}.json.gz"
    data = build_structure_dict(structure, scan_result)
    with gzip.open(path, "wt", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    return path


def default_structure_path(codebase_path: str | Path) -> Path:
    """The path where downstream tooling (viewer L2 generation,
    /api/structure) expects to find the file.
    """
    return Path(codebase_path) / ".the-door" / "structure.json"


def write_structure_json(
    target: str | Path,
    structure: StructureJSON,
    scan_result: ScanResult | None,
) -> Path:
    """Serialize and write structure.json. Creates parent dirs if missing.

    Returns the resolved target ``Path``.
    """
    target_path = Path(target)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    data = build_structure_dict(structure, scan_result)
    target_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return target_path
