"""Unit tests for response_parser module.

Tests are written BEFORE implementation (TDD red phase).
"""
from __future__ import annotations

import json

import pytest

from the_door.core.llm.response_parser import ResponseParser
from the_door.models import ParseResult


class TestResponseParser:
    """Unit tests for ResponseParser.parse()."""

    def test_valid_json_string_returns_success(self):
        """Valid JSON string → ParseResult(success=True, data=parsed_dict)."""
        raw = '{"features": [{"feature_id": "feat-1"}]}'
        parser = ResponseParser()
        result = parser.parse(raw)

        assert result.success is True
        assert result.data == {"features": [{"feature_id": "feat-1"}]}
        assert result.error is None

    def test_json_in_markdown_code_fence_extracted(self):
        """JSON wrapped in markdown code fence → extracted and parsed correctly."""
        raw = '```json\n{"key": "value"}\n```'
        parser = ResponseParser()
        result = parser.parse(raw)

        assert result.success is True
        assert result.data == {"key": "value"}

    def test_json_in_code_fence_without_language(self):
        """JSON in code fence without language tag → extracted correctly."""
        raw = '```\n{"key": "value"}\n```'
        parser = ResponseParser()
        result = parser.parse(raw)

        assert result.success is True
        assert result.data == {"key": "value"}

    def test_leading_text_before_json_extracted(self):
        """Leading text before JSON → JSON extracted correctly."""
        raw = 'Here is the analysis result:\n\n{"features": []}'
        parser = ResponseParser()
        result = parser.parse(raw)

        assert result.success is True
        assert result.data == {"features": []}

    def test_completely_invalid_response_returns_failure(self):
        """Completely invalid response → ParseResult(success=False, error=message)."""
        raw = "This is not JSON at all, just plain text without any braces."
        parser = ResponseParser()
        result = parser.parse(raw)

        assert result.success is False
        assert result.data is None
        assert result.error is not None
        assert len(result.error) > 0

    def test_empty_string_returns_failure(self):
        """Empty string → ParseResult(success=False)."""
        parser = ResponseParser()
        result = parser.parse("")

        assert result.success is False
        assert result.data is None

    def test_json_with_trailing_comma_handled(self):
        """JSON with trailing comma (common LLM error) → handled gracefully."""
        raw = '{"features": ["a", "b",]}'
        parser = ResponseParser()
        result = parser.parse(raw)

        # Should either fix the trailing comma and parse, or fail gracefully
        # The key requirement is no crash
        assert isinstance(result, ParseResult)
        if result.success:
            assert result.data is not None

    def test_nested_json_object_parsed(self):
        """Nested JSON objects are parsed correctly."""
        raw = '{"l1": {"summary": "test", "features": []}}'
        parser = ResponseParser()
        result = parser.parse(raw)

        assert result.success is True
        assert result.data["l1"]["summary"] == "test"

    def test_raw_text_preserved_in_result(self):
        """ParseResult.raw_text contains the original input."""
        raw = '{"key": "value"}'
        parser = ResponseParser()
        result = parser.parse(raw)

        assert result.raw_text == raw

    def test_json_array_response_parsed(self):
        """JSON array response is parsed correctly."""
        raw = '[{"id": 1}, {"id": 2}]'
        parser = ResponseParser()
        result = parser.parse(raw)

        assert result.success is True
        assert result.data == [{"id": 1}, {"id": 2}]

    def test_json_with_trailing_text_extracted(self):
        """JSON followed by trailing text → JSON extracted correctly."""
        raw = '{"key": "value"}\n\nI hope this helps!'
        parser = ResponseParser()
        result = parser.parse(raw)

        assert result.success is True
        assert result.data == {"key": "value"}
