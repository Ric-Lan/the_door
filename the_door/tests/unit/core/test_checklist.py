"""C2: checklist schema module (single source of truth, write side)."""
from __future__ import annotations

import json
from datetime import datetime

from the_door.core.checklist import (
    CHECKLIST_FILENAME,
    STAGE_EDGE_RESIDUE,
    FIELD_CONTRACT_VERSION,
    FIELD_STAGES,
    FIELD_COVERED_NODES,
    FIELD_NODE_COUNT,
    FIELD_STAMPED_AT,
    checklist_path,
    read_checklist,
    stamp_stage,
)


def test_c2_1_stamp_creates_file_sorted_deduped(tmp_path):
    stamp_stage(tmp_path, STAGE_EDGE_RESIDUE, covered_nodes=["b", "a", "a"], contract_version="1")
    data = json.loads(checklist_path(tmp_path).read_text(encoding="utf-8"))
    assert data[FIELD_CONTRACT_VERSION] == "1"
    stage = data[FIELD_STAGES][STAGE_EDGE_RESIDUE]
    assert stage[FIELD_COVERED_NODES] == ["a", "b"]  # sorted + deduped
    assert stage[FIELD_NODE_COUNT] == 2
    # stamped_at is a parseable UTC ISO timestamp
    ts = stage[FIELD_STAMPED_AT]
    parsed = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    assert parsed.utcoffset() is not None  # tz-aware (UTC)


def test_c2_2_stamp_adds_second_stage_keeps_first(tmp_path):
    stamp_stage(tmp_path, STAGE_EDGE_RESIDUE, covered_nodes=["a"], contract_version="1")
    stamp_stage(tmp_path, "other_stage", covered_nodes=[], contract_version="1")
    data = json.loads(checklist_path(tmp_path).read_text(encoding="utf-8"))
    assert STAGE_EDGE_RESIDUE in data[FIELD_STAGES]
    assert "other_stage" in data[FIELD_STAGES]
    assert data[FIELD_CONTRACT_VERSION] == "1"


def test_c2_2b_contract_version_overwritten_to_latest(tmp_path):
    stamp_stage(tmp_path, STAGE_EDGE_RESIDUE, covered_nodes=["a"], contract_version="0")
    stamp_stage(tmp_path, "other_stage", covered_nodes=[], contract_version="1")
    data = json.loads(checklist_path(tmp_path).read_text(encoding="utf-8"))
    assert data[FIELD_CONTRACT_VERSION] == "1"


def test_c2_3_read_missing_and_corrupt_returns_none(tmp_path):
    assert read_checklist(tmp_path) is None  # missing
    p = checklist_path(tmp_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("{not json", encoding="utf-8")
    assert read_checklist(tmp_path) is None  # corrupt


def test_c2_4_covered_nodes_dedup_sort_stable(tmp_path):
    stamp_stage(tmp_path, STAGE_EDGE_RESIDUE, covered_nodes=["z", "a", "z", "m"], contract_version="1")
    first = read_checklist(tmp_path)[FIELD_STAGES][STAGE_EDGE_RESIDUE][FIELD_COVERED_NODES]
    stamp_stage(tmp_path, STAGE_EDGE_RESIDUE, covered_nodes=["m", "z", "a"], contract_version="1")
    second = read_checklist(tmp_path)[FIELD_STAGES][STAGE_EDGE_RESIDUE][FIELD_COVERED_NODES]
    assert first == ["a", "m", "z"]
    assert second == ["a", "m", "z"]


def test_c2_filename_constant():
    assert CHECKLIST_FILENAME == "checklist.json"
    assert checklist_path(".").name == "checklist.json"
