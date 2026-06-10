"""C6 unit tests：snapshot_write 蓋章 snapshot_write stage ＋嵌 execution_ledger。

對應 spec §3.2-3.3 / plan Task 2-3。direct 模式、tmp_path 隔離。
"""
from __future__ import annotations

import asyncio
import shutil
from pathlib import Path

import pytest

from the_door.core.checklist import (
    STAGE_EDGE_RESIDUE,
    STAGE_SNAPSHOT_WRITE,
    read_checklist,
    stamp_stage,
)
from the_door.mcp.tools import edge_residue_tool, snapshot_write_tool
from the_door.models.snapshot import SNAPSHOT_CONTRACT_VERSION


def _feature(fid="feat-x", nodes=("a",)):
    return {
        "feature_id": fid,
        "label": "X",
        "description": "x feature",
        "confidence": "high",
        "source_nodes": list(nodes),
    }


def _run(args):
    return asyncio.run(snapshot_write_tool.execute(args))


def test_c6_6_stamps_and_embeds_ledger(tmp_path):
    """C6-6：成功寫入 → payload 含 execution_ledger（含 snapshot_write 項）；checklist 落 stage。"""
    # edge_residue 已跑（使 ledger 有前關）。
    stamp_stage(tmp_path, STAGE_EDGE_RESIDUE, covered_nodes=["a", "b"],
                contract_version=SNAPSHOT_CONTRACT_VERSION)

    result = _run({"codebase_path": str(tmp_path), "l1_features": [_feature()], "label": "v1"})

    assert "execution_ledger" in result
    sw = [e for e in result["execution_ledger"] if e["stage"] == STAGE_SNAPSHOT_WRITE]
    assert len(sw) == 1
    assert sw[0]["version_id"] == result["version_id"]
    assert sw[0]["feature_count"] == 1
    # checklist 真的落了 snapshot_write stage。
    assert STAGE_SNAPSHOT_WRITE in read_checklist(tmp_path)["stages"]


def test_c6_7_stamp_oserror_failsoft_ledger_still_has_stage(tmp_path, monkeypatch):
    """C6-7：磁碟蓋章拋 OSError → 仍回 snapshot 結果；ledger 仍含 snapshot_write（記憶體補回）。"""
    def _boom(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr("the_door.mcp.tools.snapshot_write_tool.stamp_stage", _boom)

    result = _run({"codebase_path": str(tmp_path), "l1_features": [_feature()], "label": "v1"})

    assert "error" not in result
    assert result["version_id"]  # snapshot 結果仍在
    sw = [e for e in result["execution_ledger"] if e["stage"] == STAGE_SNAPSHOT_WRITE]
    assert len(sw) == 1  # 記憶體補回、不與 payload 自相矛盾
    assert sw[0]["version_id"] == result["version_id"]


def test_c6_7b_non_oserror_propagates(tmp_path, monkeypatch):
    """C6-7b 負向樁：非 OSError（TypeError）不被吞 → 傳播（防 except 寬化回歸）。"""
    def _boom(*a, **k):
        raise TypeError("signature bug")

    monkeypatch.setattr("the_door.mcp.tools.snapshot_write_tool.stamp_stage", _boom)

    with pytest.raises(TypeError):
        _run({"codebase_path": str(tmp_path), "l1_features": [_feature()], "label": "v1"})


def test_c6_8_full_chain_ledger(tmp_path):
    """C6-8：整鏈 E2E（input-only fixture→tmp）→ ledger 兩 stage、edge_residue 在前、無 covered_nodes。"""
    fixture = (
        Path(__file__).resolve().parents[3]
        / "fixtures" / "sample_codebases" / "python_simple"
    )
    target = tmp_path / "codebase"
    shutil.copytree(fixture, target)

    asyncio.run(edge_residue_tool.execute({"codebase_path": str(target)}))
    covered = read_checklist(target)["stages"][STAGE_EDGE_RESIDUE]["covered_nodes"]
    assert covered, "edge_residue should have covered some nodes"

    result = _run({
        "codebase_path": str(target),
        "l1_features": [_feature(nodes=covered[:1])],
        "label": "v1",
    })

    ledger = result["execution_ledger"]
    assert [e["stage"] for e in ledger] == [STAGE_EDGE_RESIDUE, STAGE_SNAPSHOT_WRITE]
    assert all("covered_nodes" not in e for e in ledger)  # 投影剝除
    assert ledger[0]["node_count"] > 0
