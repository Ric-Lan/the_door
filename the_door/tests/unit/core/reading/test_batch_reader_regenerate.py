"""Tests for BatchReader.regenerate() mode parity with _process_batch."""
from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock

import pytest

from the_door.core.reading.batch_reader import BatchReader
from the_door.models import ASTNode, Feature, StructureJSON, TopologyEntry


def _build_structure() -> StructureJSON:
    nodes = [
        ASTNode(
            node_id="src/cart.py::checkout",
            type="function",
            name="checkout",
            file="src/cart.py",
            language="python",
            parameters=["cart_id: str", "user: User"],
            return_type="OrderResult",
            decorators=["@app.route('/checkout', methods=['POST'])"],
            docstring="Process payment and create order.",
            comments=[],
        ),
    ]
    topology = [TopologyEntry(
        node_id="src/cart.py::checkout", in_degree=0, out_degree=0,
        topology_rank=0, is_entry_point=True, batch_assignment=1
    )]
    return StructureJSON(files=[], nodes=nodes, edges=[], topology=topology)


def _build_previous_feature() -> Feature:
    return Feature(
        feature_id="feat-checkout",
        label="Old label",
        description="Old description",
        trigger="user_action",
        trigger_description="...",
        confidence="medium",
        confidence_reason="...",
        source_nodes=["src/cart.py::checkout"],
        needs_source_review=False,
        review_reason=None,
    )


def _build_provider(complete_response: str):
    provider = AsyncMock()
    provider.complete = AsyncMock(return_value=complete_response)
    provider.estimate_tokens = lambda text: len(text) // 4
    return provider


_OK_RESPONSE = json.dumps({
    "features": [
        {
            "feature_id": "feat-checkout",
            "label": "新標籤",
            "description": "讓使用者完成購物車付款。",
            "trigger_description": "使用者點擊結帳按鈕後觸發。",
            "confidence": "high",
            "confidence_reason": "三個信號齊備",
            "source_nodes": ["src/cart.py::checkout"],
        }
    ],
    "feature_relations": [],
})


class TestRegenerateDetailMode:
    def test_detail_mode_prompt_contains_docstring(self):
        s = _build_structure()
        provider = _build_provider(_OK_RESPONSE)
        br = BatchReader(provider, s, context_mode="detail")
        asyncio.run(br.regenerate("feat-checkout", _build_previous_feature()))
        called_prompt = provider.complete.call_args.args[0]
        assert "Process payment and create order." in called_prompt
        assert "parameters" in called_prompt

    def test_detail_mode_payload_includes_task_marker(self):
        s = _build_structure()
        provider = _build_provider(_OK_RESPONSE)
        br = BatchReader(provider, s, context_mode="detail")
        asyncio.run(br.regenerate("feat-checkout", _build_previous_feature()))
        called_prompt = provider.complete.call_args.args[0]
        data = json.loads(called_prompt)
        assert data.get("task") == "regenerate"
        assert data.get("feature_id") == "feat-checkout"


class TestRegenerateMinimalMode:
    def test_minimal_mode_prompt_excludes_docstring(self):
        s = _build_structure()
        provider = _build_provider(_OK_RESPONSE)
        br = BatchReader(provider, s, context_mode="minimal")
        asyncio.run(br.regenerate("feat-checkout", _build_previous_feature()))
        called_prompt = provider.complete.call_args.args[0]
        assert "Process payment" not in called_prompt
        assert "src/cart.py::checkout" in called_prompt

    def test_minimal_mode_payload_includes_task_marker(self):
        s = _build_structure()
        provider = _build_provider(_OK_RESPONSE)
        br = BatchReader(provider, s, context_mode="minimal")
        asyncio.run(br.regenerate("feat-checkout", _build_previous_feature()))
        data = json.loads(provider.complete.call_args.args[0])
        assert data["task"] == "regenerate"
        assert data["feature_id"] == "feat-checkout"


class TestRegenerateResultParsing:
    def test_successful_regenerate_returns_new_feature(self):
        s = _build_structure()
        provider = _build_provider(_OK_RESPONSE)
        br = BatchReader(provider, s, context_mode="detail")
        result = asyncio.run(br.regenerate("feat-checkout", _build_previous_feature()))
        assert result.new_result is not None
        assert result.new_result.label == "新標籤"
        assert result.differs is True

    def test_parser_failure_returns_none_new_result(self):
        s = _build_structure()
        provider = _build_provider("not-json garbage")
        br = BatchReader(provider, s, context_mode="detail")
        result = asyncio.run(br.regenerate("feat-checkout", _build_previous_feature()))
        assert result.new_result is None
        assert result.differs is False
        assert result.previous_result == _build_previous_feature()

    def test_empty_features_list_returns_none_new_result(self):
        s = _build_structure()
        provider = _build_provider('{"features": [], "feature_relations": []}')
        br = BatchReader(provider, s, context_mode="detail")
        result = asyncio.run(br.regenerate("feat-checkout", _build_previous_feature()))
        assert result.new_result is None
        assert result.differs is False

    def test_same_content_marks_differs_false(self):
        s = _build_structure()
        same_response = json.dumps({
            "features": [{
                "feature_id": "feat-checkout",
                "label": "Old label",
                "description": "Old description",
                "trigger_description": "...",
                "confidence": "medium",
                "confidence_reason": "...",
                "source_nodes": ["src/cart.py::checkout"],
            }],
            "feature_relations": [],
        })
        provider = _build_provider(same_response)
        br = BatchReader(provider, s, context_mode="detail")
        result = asyncio.run(br.regenerate("feat-checkout", _build_previous_feature()))
        assert result.new_result is not None
