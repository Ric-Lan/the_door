"""S4 C6：analyze_tool emit confidence 經膜投影（值→signal、None→noise）、無裸 enum。"""
from __future__ import annotations

import asyncio

import pytest

from the_door.mcp.tools import analyze_tool
from the_door.core.reading.batch_reader import BatchReadResult
from the_door.models import ExtractionResult, Feature, L1Output


def _feature(confidence):
    return Feature(
        feature_id="feat-x", label="X", description="D",
        trigger="user_action", trigger_description="T",
        confidence=confidence, confidence_reason="R", source_nodes=["app.py::f"],
    )


def test_analyze_tool_confidence_membrane_projection(monkeypatch, tmp_path):
    """C6：features confidence 經膜投影（高→signal、None→noise indeterminate）、無裸 enum。"""
    monkeypatch.setattr(
        analyze_tool.ASTExtractor, "extract",
        lambda self, path: ExtractionResult(files=[], nodes=[], edges=[]),
    )
    monkeypatch.setattr(analyze_tool, "create_provider", lambda config: object())

    async def fake_read(self):
        return BatchReadResult(
            l1_output=L1Output(features=[_feature("high"), _feature(None)]),
        )

    monkeypatch.setattr(analyze_tool.BatchReader, "read", fake_read)

    out = asyncio.run(analyze_tool.execute({"codebase_path": str(tmp_path)}))
    feats = out["l1"]["features"]
    kinds = {f["confidence"]["position"]["kind"] for f in feats}
    assert kinds == {"signal", "noise"}                              # 值→signal、None→noise
    assert all(isinstance(f["confidence"], dict) for f in feats)     # 無裸 enum
    sig = next(f for f in feats if f["confidence"]["value"] == "high")
    assert sig["confidence"]["position"]["contrasts"] == ["high", "medium", "low"]
    noise = next(f for f in feats if f["confidence"]["value"] is None)
    assert noise["confidence"]["position"]["gap_kind"] == "indeterminate"
