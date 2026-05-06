"""Unit tests for l2_generator.py — Phase UI-3 Interactive Graph.

These tests are written TDD-first: they define the expected behaviour of
L2Generator before the implementation exists.

All tests will fail with ImportError until Task 3.2 is complete.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from the_door.core.ui.l2_generator import L2GenerationError, L2Generator
from the_door.models import L2Output, StructureJSON

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


def _make_structure_json() -> StructureJSON:
    return StructureJSON(nodes=[], edges=[], topology=[])


def _make_llm_provider(return_value: str = _VALID_L2_JSON) -> MagicMock:
    """Return a mock LLMProvider whose complete() is an AsyncMock."""
    provider = MagicMock()
    provider.complete = AsyncMock(return_value=return_value)
    return provider


# ---------------------------------------------------------------------------
# test_generate_calls_llm_with_prompt
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_calls_llm_with_prompt(tmp_path: Path) -> None:
    """generate() must call llm_provider.complete() with a prompt that
    contains the feature_id so the LLM knows which feature to analyse."""
    provider = _make_llm_provider()
    generator = L2Generator(project_root=tmp_path, llm_provider=provider)
    structure = _make_structure_json()

    await generator.generate(feature_id="feat_auth", structure_json=structure)

    provider.complete.assert_called_once()
    call_args = provider.complete.call_args
    # The prompt is the first positional argument
    prompt: str = call_args[0][0] if call_args[0] else call_args[1]["prompt"]
    assert "feat_auth" in prompt


# ---------------------------------------------------------------------------
# test_generate_persists_to_disk
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_persists_to_disk(tmp_path: Path) -> None:
    """generate() must write the L2Output to
    .the-door/l2-outputs/<feature_id>.json relative to project_root."""
    provider = _make_llm_provider()
    generator = L2Generator(project_root=tmp_path, llm_provider=provider)
    structure = _make_structure_json()

    await generator.generate(feature_id="feat_auth", structure_json=structure)

    expected_path = tmp_path / ".the-door" / "l2-outputs" / "feat_auth.json"
    assert expected_path.exists(), f"Expected file not found: {expected_path}"
    data = json.loads(expected_path.read_text(encoding="utf-8"))
    assert "modules" in data
    assert data["modules"][0]["module_id"] == "mod_a"


# ---------------------------------------------------------------------------
# test_generate_llm_error_raises_l2_generation_error
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_llm_error_raises_l2_generation_error(tmp_path: Path) -> None:
    """When llm_provider.complete() raises any exception, generate() must
    re-raise it as L2GenerationError."""
    provider = MagicMock()
    provider.complete = AsyncMock(side_effect=RuntimeError("LLM timeout"))
    generator = L2Generator(project_root=tmp_path, llm_provider=provider)
    structure = _make_structure_json()

    with pytest.raises(L2GenerationError):
        await generator.generate(feature_id="feat_auth", structure_json=structure)


# ---------------------------------------------------------------------------
# test_generate_invalid_json_raises_l2_generation_error
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_invalid_json_raises_l2_generation_error(tmp_path: Path) -> None:
    """When llm_provider.complete() returns non-JSON text, generate() must
    raise L2GenerationError (parse failure)."""
    provider = _make_llm_provider(return_value="This is not JSON at all.")
    generator = L2Generator(project_root=tmp_path, llm_provider=provider)
    structure = _make_structure_json()

    with pytest.raises(L2GenerationError):
        await generator.generate(feature_id="feat_auth", structure_json=structure)


# ---------------------------------------------------------------------------
# test_load_returns_none_when_not_found
# ---------------------------------------------------------------------------


def test_load_returns_none_when_not_found(tmp_path: Path) -> None:
    """load() must return None when the persisted file does not exist."""
    result = L2Generator.load(project_root=tmp_path, feature_id="feat_missing")
    assert result is None


# ---------------------------------------------------------------------------
# test_load_returns_l2_output_when_found
# ---------------------------------------------------------------------------


def test_load_returns_l2_output_when_found(tmp_path: Path) -> None:
    """load() must return an L2Output when the persisted file exists."""
    # Manually write the file that generate() would have created
    output_dir = tmp_path / ".the-door" / "l2-outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "feat_auth.json").write_text(_VALID_L2_JSON, encoding="utf-8")

    result = L2Generator.load(project_root=tmp_path, feature_id="feat_auth")

    assert result is not None
    assert isinstance(result, L2Output)
    assert len(result.modules) == 1
    assert result.modules[0].module_id == "mod_a"


# ---------------------------------------------------------------------------
# test_generate_markdown_fenced_json_parsed_correctly
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_markdown_fenced_json_parsed_correctly(tmp_path: Path) -> None:
    """generate() must strip markdown code fences before parsing JSON."""
    fenced_response = "```json\n" + _VALID_L2_JSON + "\n```"
    provider = _make_llm_provider(return_value=fenced_response)
    generator = L2Generator(project_root=tmp_path, llm_provider=provider)
    structure = _make_structure_json()

    result = await generator.generate(feature_id="feat_auth", structure_json=structure)

    assert result is not None
    assert len(result.modules) == 1
    assert result.modules[0].module_id == "mod_a"


# ---------------------------------------------------------------------------
# test_generate_missing_required_field_raises_l2_generation_error
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_missing_required_field_raises_l2_generation_error(tmp_path: Path) -> None:
    """When LLM returns JSON missing required fields (e.g. module_id), generate() must
    raise L2GenerationError (KeyError/TypeError path)."""
    bad_json = '{"modules": [{"label": "No ID here"}], "module_interactions": [], "anomalies": []}'
    provider = _make_llm_provider(return_value=bad_json)
    generator = L2Generator(project_root=tmp_path, llm_provider=provider)
    structure = _make_structure_json()

    with pytest.raises(L2GenerationError):
        await generator.generate(feature_id="feat_auth", structure_json=structure)


# ---------------------------------------------------------------------------
# test_load_returns_none_when_file_is_corrupt
# ---------------------------------------------------------------------------


def test_load_returns_none_when_file_is_corrupt(tmp_path: Path) -> None:
    """load() must return None when the persisted file contains invalid JSON."""
    output_dir = tmp_path / ".the-door" / "l2-outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "feat_corrupt.json").write_text("not valid json {{", encoding="utf-8")

    result = L2Generator.load(project_root=tmp_path, feature_id="feat_corrupt")
    assert result is None
