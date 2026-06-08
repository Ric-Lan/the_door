"""Unit tests for l2_generator.py — display-only loader (after T5-V).

L2 generation was retired in T5-V (丙案 D1). L2Generator is now a display-only
loader; only `load` remains. Generation/prompt tests were removed with the code.
"""
from __future__ import annotations

import json
from pathlib import Path

from the_door.core.ui.l2_generator import L2Generator
from the_door.models import L2Output

_VALID_L2_JSON = json.dumps(
    {
        "modules": [
            {
                "module_id": "mod_a",
                "label": "Module A",
                "confidence": "high",
                "source_nodes": ["node_1", "node_2"],
            }
        ],
        "module_interactions": [
            {
                "from_module": "mod_a",
                "to_module": "mod_a",
                "description": "self-loop",
                "relation_type": "static",
            }
        ],
        "anomalies": [
            {
                "anomaly_type": "dead_code",
                "affected_node_ids": ["node_1"],
                "explanation": "Unreachable",
                "confidence": "medium",
            }
        ],
    }
)


def test_load_returns_none_when_not_found(tmp_path: Path) -> None:
    """load() must return None when the persisted file does not exist."""
    result = L2Generator.load(project_root=tmp_path, feature_id="feat_missing")
    assert result is None


def test_load_returns_l2_output_when_found(tmp_path: Path) -> None:
    """load() must return an L2Output when the persisted file exists."""
    output_dir = tmp_path / ".the-door" / "l2-outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "feat_auth.json").write_text(_VALID_L2_JSON, encoding="utf-8")

    result = L2Generator.load(project_root=tmp_path, feature_id="feat_auth")

    assert result is not None
    assert isinstance(result, L2Output)
    assert len(result.modules) == 1
    assert result.modules[0].module_id == "mod_a"


def test_load_returns_none_when_file_is_corrupt(tmp_path: Path) -> None:
    """load() must return None when the persisted file contains invalid JSON."""
    output_dir = tmp_path / ".the-door" / "l2-outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "feat_corrupt.json").write_text("not valid json {{", encoding="utf-8")

    result = L2Generator.load(project_root=tmp_path, feature_id="feat_corrupt")
    assert result is None
