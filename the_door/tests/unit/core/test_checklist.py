"""C2: checklist schema module (single source of truth, write side)."""
from __future__ import annotations

import json
from datetime import datetime

from the_door.core.checklist import (
    CHECKLIST_FILENAME,
    STAGE_EDGE_RESIDUE,
    STAGE_SNAPSHOT_WRITE,
    FIELD_CONTRACT_VERSION,
    FIELD_STAGES,
    FIELD_COVERED_NODES,
    FIELD_NODE_COUNT,
    FIELD_SOURCE_FILES,
    FIELD_STAMPED_AT,
    checklist_path,
    read_checklist,
    read_ledger,
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


# ── C6: details-stage stamping + read_ledger projection ───────────────


def test_c6_1_stamp_stage_with_details_no_node_fields(tmp_path):
    """C6-1：details stage（無 covered_nodes）→ entry 含 stamped_at+details，不含 node 欄位。"""
    stamp_stage(
        tmp_path, STAGE_SNAPSHOT_WRITE, contract_version="1",
        details={"version_id": "v", "feature_count": 3},
    )
    stage = read_checklist(tmp_path)[FIELD_STAGES][STAGE_SNAPSHOT_WRITE]
    assert stage["version_id"] == "v"
    assert stage["feature_count"] == 3
    assert FIELD_STAMPED_AT in stage
    assert FIELD_NODE_COUNT not in stage
    assert FIELD_COVERED_NODES not in stage


def test_c6_2_stamp_stage_covered_nodes_unchanged(tmp_path):
    """C6-2 回歸：既有 covered_nodes 用法行為不變（排序去重+node_count）。"""
    stamp_stage(tmp_path, STAGE_EDGE_RESIDUE, covered_nodes=["b", "a"], contract_version="1")
    stage = read_checklist(tmp_path)[FIELD_STAGES][STAGE_EDGE_RESIDUE]
    assert stage[FIELD_COVERED_NODES] == ["a", "b"]
    assert stage[FIELD_NODE_COUNT] == 2


def test_c6_3_read_ledger_missing_and_corrupt_returns_empty(tmp_path):
    """C6-3：缺檔/壞檔 → []（fail-soft）。"""
    assert read_ledger(tmp_path) == []
    p = checklist_path(tmp_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("{not json", encoding="utf-8")
    assert read_ledger(tmp_path) == []


def test_c6_4_read_ledger_projects_ordered_strips_covered_nodes(tmp_path):
    """C6-4：兩 stage → 依 STAGE_ORDER 排序；每項含 stage 名；covered_nodes 剝除、node_count 留；無 KeyError。"""
    stamp_stage(tmp_path, STAGE_EDGE_RESIDUE, covered_nodes=["x", "y"], contract_version="1")
    stamp_stage(
        tmp_path, STAGE_SNAPSHOT_WRITE, contract_version="1",
        details={"version_id": "v1", "feature_count": 2},
    )
    ledger = read_ledger(tmp_path)
    assert [e["stage"] for e in ledger] == [STAGE_EDGE_RESIDUE, STAGE_SNAPSHOT_WRITE]
    er = ledger[0]
    assert FIELD_COVERED_NODES not in er  # 剝除
    assert er[FIELD_NODE_COUNT] == 2  # 保留
    sw = ledger[1]
    assert sw["version_id"] == "v1"
    assert FIELD_COVERED_NODES not in sw  # 非破壞移除：本就無此鍵、不報錯


def test_c6_5_read_ledger_unknown_stage_appended_after(tmp_path):
    """C6-5：未知 stage 排在已知 stage 之後（向前相容水平推廣）。"""
    stamp_stage(tmp_path, STAGE_EDGE_RESIDUE, covered_nodes=["a"], contract_version="1")
    stamp_stage(tmp_path, STAGE_SNAPSHOT_WRITE, contract_version="1", details={"version_id": "v"})
    stamp_stage(tmp_path, "future_stage", covered_nodes=[], contract_version="1")
    order = [e["stage"] for e in read_ledger(tmp_path)]
    assert order == [STAGE_EDGE_RESIDUE, STAGE_SNAPSHOT_WRITE, "future_stage"]


# ── staleness: source_files fingerprint (write side) ──────────────────


def test_s1_stamp_writes_source_files_keeps_node_fields(tmp_path):
    """S-1：source_files 原樣寫入；既有 covered_nodes/node_count 不受影響。"""
    stamp_stage(
        tmp_path, STAGE_EDGE_RESIDUE, covered_nodes=["a"],
        source_files={"f.py": [111, 222]}, contract_version="1",
    )
    stage = read_checklist(tmp_path)[FIELD_STAGES][STAGE_EDGE_RESIDUE]
    assert stage[FIELD_SOURCE_FILES] == {"f.py": [111, 222]}
    assert stage[FIELD_COVERED_NODES] == ["a"]
    assert stage[FIELD_NODE_COUNT] == 1


def test_s2_read_ledger_strips_source_files_keeps_node_count(tmp_path):
    """S-2：read_ledger 剝除 source_files、保留 node_count；無 KeyError。"""
    stamp_stage(
        tmp_path, STAGE_EDGE_RESIDUE, covered_nodes=["x", "y"],
        source_files={"f.py": [1, 2]}, contract_version="1",
    )
    er = read_ledger(tmp_path)[0]
    assert er["stage"] == STAGE_EDGE_RESIDUE
    assert FIELD_SOURCE_FILES not in er  # 剝除（避免淹沒 C6 ledger）
    assert er[FIELD_NODE_COUNT] == 2  # 保留


def test_s3_stamp_without_source_files_has_no_key(tmp_path):
    """S-3：不給 source_files → entry 無該鍵（向後相容、既有 caller 零 churn）。"""
    stamp_stage(tmp_path, STAGE_EDGE_RESIDUE, covered_nodes=["a"], contract_version="1")
    stage = read_checklist(tmp_path)[FIELD_STAGES][STAGE_EDGE_RESIDUE]
    assert FIELD_SOURCE_FILES not in stage


def test_c7_read_ledger_strips_inherited_hashes(tmp_path):
    """C7：read_ledger 剝除 inherited_hashes（每未變動 feature 一筆，大專案會淹沒
    C6 ledger）；baseline_ref 等小欄保留、stage 仍在。"""
    from the_door.core.checklist import (
        STAGE_ANALYZE_CHANGES,
        FIELD_INHERITED_HASHES,
        FIELD_BASELINE_REF,
    )
    stamp_stage(
        tmp_path, STAGE_ANALYZE_CHANGES, contract_version="1",
        details={
            FIELD_INHERITED_HASHES: {"feat-a": "abc", "feat-b": "def"},
            FIELD_BASELINE_REF: "v1.0.0",
        },
    )
    entry = next(e for e in read_ledger(tmp_path) if e["stage"] == STAGE_ANALYZE_CHANGES)
    assert FIELD_INHERITED_HASHES not in entry  # 剝除
    assert entry[FIELD_BASELINE_REF] == "v1.0.0"  # 小欄保留
