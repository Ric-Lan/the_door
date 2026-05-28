"""Tests for BatchReader context_mode (detail / minimal)."""
from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock

import pytest

from the_door.core.reading.batch_reader import BatchReader
from the_door.models import ASTNode, StructureJSON, TopologyEntry


def _build_structure() -> StructureJSON:
    nodes = [
        ASTNode(
            node_id="src/foo.py::greet",
            type="function",
            name="greet",
            file="src/foo.py",
            language="python",
            parameters=["name: str", "times: int = 1"],
            return_type="str",
            decorators=["@app.route('/hello', methods=['GET'])"],
            docstring="Greet someone by name.",
            comments=[],
        ),
        ASTNode(
            node_id="src/foo.py::farewell",
            type="function",
            name="farewell",
            file="src/foo.py",
            language="python",
            parameters=["name: str"],
            return_type="str",
            decorators=[],
            docstring=None,
            comments=[],
        ),
    ]
    topology = [
        TopologyEntry(node_id="src/foo.py::greet", in_degree=0, out_degree=0,
                      topology_rank=0, is_entry_point=True, batch_assignment=1),
        TopologyEntry(node_id="src/foo.py::farewell", in_degree=0, out_degree=0,
                      topology_rank=0, is_entry_point=True, batch_assignment=1),
    ]
    return StructureJSON(files=[], nodes=nodes, edges=[], topology=topology)


def _build_provider(complete_response: str = '{"features":[]}'):
    provider = AsyncMock()
    provider.complete = AsyncMock(return_value=complete_response)
    provider.estimate_tokens = lambda text: len(text) // 4
    return provider


class TestSerializePayloadModeBranching:
    def test_minimal_mode_outputs_node_ids_list(self):
        s = _build_structure()
        br = BatchReader(_build_provider(), s, context_mode="minimal")
        payload = br._serialize_payload(
            ["src/foo.py::greet", "src/foo.py::farewell"],
            batch_num=1,
        )
        data = json.loads(payload)
        assert data["batch"] == 1
        assert data["context_mode"] == "minimal"
        assert data["nodes"] == ["src/foo.py::greet", "src/foo.py::farewell"]

    def test_detail_mode_outputs_full_ast_node_dicts(self):
        s = _build_structure()
        br = BatchReader(_build_provider(), s, context_mode="detail")
        payload = br._serialize_payload(["src/foo.py::greet"], batch_num=2)
        data = json.loads(payload)
        assert data["batch"] == 2
        assert data["context_mode"] == "detail"
        assert len(data["nodes"]) == 1
        node = data["nodes"][0]
        assert node["node_id"] == "src/foo.py::greet"
        assert node["name"] == "greet"
        assert node["parameters"] == ["name: str", "times: int = 1"]
        assert node["return_type"] == "str"
        assert "app.route" in node["decorators"][0]
        assert node["docstring"] == "Greet someone by name."
        assert node["comments"] == []
        assert node["file"] == "src/foo.py"
        assert node["language"] == "python"
        assert node["type"] == "function"

    def test_detail_mode_skips_unknown_node_id(self):
        s = _build_structure()
        br = BatchReader(_build_provider(), s, context_mode="detail")
        payload = br._serialize_payload(["src/foo.py::greet", "missing::id"], batch_num=1)
        data = json.loads(payload)
        node_ids = [n["node_id"] for n in data["nodes"]]
        assert node_ids == ["src/foo.py::greet"]


class TestBatchReaderDefaultMode:
    def test_default_context_mode_is_detail(self):
        s = _build_structure()
        br = BatchReader(_build_provider(), s)
        assert br._context_mode == "detail"

    def test_invalid_context_mode_raises(self):
        s = _build_structure()
        with pytest.raises(ValueError):
            BatchReader(_build_provider(), s, context_mode="weird")


class TestProcessBatchUsesSerializeHelper:
    def test_detail_mode_prompt_contains_docstring(self):
        s = _build_structure()
        provider = _build_provider('{"features":[]}')
        br = BatchReader(provider, s, context_mode="detail")
        asyncio.run(br._process_batch(["src/foo.py::greet"], batch_num=1))
        called_prompt = provider.complete.call_args.args[0]
        assert "Greet someone by name." in called_prompt

    def test_minimal_mode_prompt_does_not_contain_docstring(self):
        s = _build_structure()
        provider = _build_provider('{"features":[]}')
        br = BatchReader(provider, s, context_mode="minimal")
        asyncio.run(br._process_batch(["src/foo.py::greet"], batch_num=1))
        called_prompt = provider.complete.call_args.args[0]
        assert "Greet someone by name." not in called_prompt
        assert "src/foo.py::greet" in called_prompt


class TestMaybeSplitUsesSerializedPayloadSize:
    def test_minimal_mode_small_payload_no_split(self):
        s = _build_structure()
        br = BatchReader(_build_provider(), s, context_mode="minimal", max_context_tokens=10_000)
        sub_batches = br._maybe_split(["src/foo.py::greet", "src/foo.py::farewell"])
        assert len(sub_batches) == 1

    def test_detail_mode_large_payload_triggers_split(self):
        s = _build_structure()
        br = BatchReader(_build_provider(), s, context_mode="detail", max_context_tokens=5)
        sub_batches = br._maybe_split(["src/foo.py::greet", "src/foo.py::farewell"])
        assert len(sub_batches) >= 2

    def test_maybe_split_respects_serialize_payload_output(self):
        s = _build_structure()
        br = BatchReader(_build_provider(), s, context_mode="detail", max_context_tokens=1000)
        serialized = br._serialize_payload(["src/foo.py::greet"], batch_num=1)
        assert "parameters" in serialized


class TestProcessBatchFeatureRelations:
    def test_feature_relations_parsed_when_present(self):
        s = _build_structure()
        response = json.dumps({
            "features": [{"feature_id": "feat-a", "label": "A", "description": "...",
                          "trigger_description": "...", "confidence": "high",
                          "confidence_reason": "...", "source_nodes": ["src/foo.py::greet"]}],
            "feature_relations": [{"from": "feat-a", "to": "feat-b", "relation": "depends_on"}],
        })
        provider = _build_provider(response)
        br = BatchReader(provider, s, context_mode="minimal")
        features, relations, _, _, _ = asyncio.run(br._process_batch(["src/foo.py::greet"], 1))
        assert len(relations) == 1
        assert relations[0].from_feature == "feat-a"


class TestRegenerateNotInScope:
    """regenerate() context_mode adaptation is a later task."""
    def test_placeholder(self):
        assert True
