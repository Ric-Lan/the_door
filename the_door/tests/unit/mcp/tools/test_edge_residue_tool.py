"""T2 unit tests：edge_residue 工具（注入 extraction，測接線＋落盤）。

對應 spec §5（T-1..T-5）／plan Task 1。新責任＝把 extraction.edges 接成 edge_dicts →
餵 project_edges_for_prompt（既有純函式、已被 test_edge_projection* 覆蓋）→ 落盤 artifact。
⟹ 單元測試注入已知 extraction（monkeypatch ASTExtractor.extract），對殘餘做確定性斷言。
E2E（真 extraction）見 Task 3 同檔尾。
"""
from __future__ import annotations

import asyncio
import json
import shutil
import types
from pathlib import Path

from the_door.core.extraction import ast_extractor as ast_extractor_mod
from the_door.core.llm.edge_membrane import indeterminate_residue_element
from the_door.mcp.tools import edge_residue_tool


def _fake_extraction(edges):
    """edges＝[(from, to, resolution), ...] → 帶 .edges + .nodes + .files 的假 extraction。

    .nodes 由 edge 端點推導（union of from/to），供 C2 checklist 蓋章記 covered_nodes。
    .files＝[]（誠實鏡像真實 ExtractionResult 形狀；staleness 蓋章迭代 extraction.files）。
    """
    Edge = types.SimpleNamespace
    node_ids = sorted({f for (f, _t, _r) in edges} | {t for (_f, t, _r) in edges})
    return types.SimpleNamespace(
        edges=[
            Edge(from_node=f, to_node=t, type="call", resolution=r)
            for (f, t, r) in edges
        ],
        nodes=[types.SimpleNamespace(node_id=nid) for nid in node_ids],
        files=[],
    )


def _patch_extract(monkeypatch, edges):
    monkeypatch.setattr(
        ast_extractor_mod.ASTExtractor,
        "extract",
        lambda self, codebase_path, *a, **k: _fake_extraction(edges),
    )


def test_residue_computed_and_artifact_written(monkeypatch, tmp_path):
    """T-1：含 skipped_dynamic 邊 → indeterminate_count>0；artifact 落盤。"""
    _patch_extract(monkeypatch, [("a", "Bus.send", "skipped_dynamic")])
    result = asyncio.run(edge_residue_tool.execute({"codebase_path": str(tmp_path)}))

    assert result["indeterminate_count"] > 0
    assert (tmp_path / ".the-door" / "edge-residue.json").exists()


def test_artifact_shape(monkeypatch, tmp_path):
    """T-2：artifact 含四鍵；indeterminate[0] 結構＝NoisePosition.to_json()。"""
    _patch_extract(monkeypatch, [("a", "Bus.send", "skipped_dynamic")])
    asyncio.run(edge_residue_tool.execute({"codebase_path": str(tmp_path)}))

    artifact = json.loads(
        (tmp_path / ".the-door" / "edge-residue.json").read_text(encoding="utf-8")
    )
    assert set(artifact) >= {
        "indeterminate",
        "low_confidence_ambiguous",
        "total_edges",
        "kept_edges",
    }
    # 對齊真實 NoisePosition.to_json() 鍵集（不 hardcode 猜鍵）。
    expected_keys = set(
        indeterminate_residue_element("a", {"send": 1}, 1).to_json()
    )
    assert set(artifact["indeterminate"][0]) == expected_keys


def test_no_noise_empty_residue(monkeypatch, tmp_path):
    """T-5：全格內邊 → 空殘餘；artifact 仍寫出、不報錯、不謊報。"""
    _patch_extract(monkeypatch, [("a", "B.run", "scope_rule")])
    result = asyncio.run(edge_residue_tool.execute({"codebase_path": str(tmp_path)}))

    assert result["indeterminate_count"] == 0
    assert result["low_confidence_count"] == 0
    artifact_path = tmp_path / ".the-door" / "edge-residue.json"
    assert artifact_path.exists()
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert artifact["indeterminate"] == []
    assert artifact["low_confidence_ambiguous"] == []


def test_missing_codebase_path(tmp_path):
    """T-4：缺 codebase_path → {"error": ...}；不寫檔。"""
    result = asyncio.run(edge_residue_tool.execute({}))
    assert "error" in result
    assert not (tmp_path / ".the-door" / "edge-residue.json").exists()


def test_determinism(monkeypatch, tmp_path):
    """T-3：同輸入呼兩次 → artifact 位元組相同。"""
    edges = [
        ("a", "Bus.send", "skipped_dynamic"),
        ("b", "Q.push", "name_match_ambiguous"),
        ("c", "D.run", "scope_rule"),
    ]
    _patch_extract(monkeypatch, edges)
    artifact_path = tmp_path / ".the-door" / "edge-residue.json"

    asyncio.run(edge_residue_tool.execute({"codebase_path": str(tmp_path)}))
    first = artifact_path.read_bytes()
    asyncio.run(edge_residue_tool.execute({"codebase_path": str(tmp_path)}))
    second = artifact_path.read_bytes()

    assert first == second


def test_c2_5_stamps_checklist(monkeypatch, tmp_path):
    """C2-5：edge_residue 蓋章 checklist；covered_nodes==sorted node_ids、contract 當前、payload 含 checklist_path。"""
    from the_door.core.checklist import (
        STAGE_EDGE_RESIDUE, FIELD_STAGES, FIELD_COVERED_NODES, FIELD_CONTRACT_VERSION, read_checklist,
    )
    from the_door.models.snapshot import SNAPSHOT_CONTRACT_VERSION

    _patch_extract(monkeypatch, [("a", "B.run", "scope_rule"), ("c", "a", "scope_rule")])
    result = asyncio.run(edge_residue_tool.execute({"codebase_path": str(tmp_path)}))

    assert "checklist_path" in result
    data = read_checklist(tmp_path)
    assert data[FIELD_CONTRACT_VERSION] == SNAPSHOT_CONTRACT_VERSION
    covered = data[FIELD_STAGES][STAGE_EDGE_RESIDUE][FIELD_COVERED_NODES]
    assert covered == ["B.run", "a", "c"]  # sorted union of edge endpoints


def test_c2_5b_stamp_failure_surfaces(monkeypatch, tmp_path):
    """C2-5b：stamp_stage 失敗（patch 匯入端 ref）→ execute 回 error，不靜默成功。"""
    _patch_extract(monkeypatch, [("a", "B.run", "scope_rule")])

    def _boom(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr("the_door.mcp.tools.edge_residue_tool.stamp_stage", _boom)
    result = asyncio.run(edge_residue_tool.execute({"codebase_path": str(tmp_path)}))
    assert "error" in result
    assert "checklist" in result["error"]


def test_e2e_real_extraction(tmp_path):
    """E2E smoke：真 extraction（input-only fixture）→ artifact 鍵齊全、counts int≥0。

    用既有 input-only fixture python_simple；先 copytree 到 tmp 對副本跑，
    不污染 checked-in fixture。不斷言殘餘確切數值（依 extractor 啟發式、避免脆測）。
    """
    fixture = (
        Path(__file__).resolve().parents[3]
        / "fixtures"
        / "sample_codebases"
        / "python_simple"
    )
    target = tmp_path / "codebase"
    shutil.copytree(fixture, target)

    result = asyncio.run(edge_residue_tool.execute({"codebase_path": str(target)}))

    artifact_path = target / ".the-door" / "edge-residue.json"
    assert artifact_path.exists()
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert set(artifact) >= {
        "indeterminate",
        "low_confidence_ambiguous",
        "total_edges",
        "kept_edges",
    }
    for key in ("indeterminate_count", "low_confidence_count", "total_edges", "kept_edges"):
        assert isinstance(result[key], int) and result[key] >= 0

    # C2 §5 護欄：真實 codebase 跑 edge_residue → checklist 生成、covered_nodes 非空。
    from the_door.core.checklist import (
        STAGE_EDGE_RESIDUE, FIELD_STAGES, FIELD_COVERED_NODES, read_checklist,
    )
    checklist = read_checklist(target)
    assert checklist is not None
    covered = checklist[FIELD_STAGES][STAGE_EDGE_RESIDUE][FIELD_COVERED_NODES]
    assert len(covered) > 0


def test_s4_stamps_source_files_fingerprint(tmp_path):
    """S-4：edge_residue 蓋章記 source_files＝每個 extraction.files 的磁碟真實 (mtime_ns, size)。"""
    from the_door.core.checklist import (
        STAGE_EDGE_RESIDUE, FIELD_STAGES, FIELD_SOURCE_FILES, read_checklist,
    )
    fixture = (
        Path(__file__).resolve().parents[3]
        / "fixtures" / "sample_codebases" / "python_simple"
    )
    target = tmp_path / "codebase"
    shutil.copytree(fixture, target)

    asyncio.run(edge_residue_tool.execute({"codebase_path": str(target)}))

    source_files = read_checklist(target)[FIELD_STAGES][STAGE_EDGE_RESIDUE][FIELD_SOURCE_FILES]
    assert source_files  # non-empty (fixture has source files)
    for rel, fp in source_files.items():
        st = (target / rel).stat()
        assert fp == [st.st_mtime_ns, st.st_size]
