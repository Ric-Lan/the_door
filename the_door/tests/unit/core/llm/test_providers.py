"""Unit tests for LLM provider modules.

Tests are written BEFORE implementation (TDD red phase).
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from the_door.core.llm.provider import (
    LLMProvider,
    create_provider,
    LLMCallError,
    ConfigError,
)
from the_door.core.llm.openai_provider import OpenAIProvider
from the_door.core.llm.anthropic_provider import AnthropicProvider
from the_door.core.llm.ollama_provider import OllamaProvider
from the_door.models import TheDoorConfig


# ============================================================================
# OpenAI Provider Tests
# ============================================================================


class TestOpenAIProvider:
    """Unit tests for OpenAIProvider."""

    def test_complete_with_mock_response(self):
        """OpenAIProvider.complete() with mock httpx response → correct response text."""
        provider = OpenAIProvider(api_key="sk-test", model="gpt-4o")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": '{"features": []}'}}]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
            result = asyncio.run(provider.complete("Analyze this code"))

        assert result == '{"features": []}'

    def test_timeout_raises_llm_call_error(self):
        """OpenAI timeout handling → LLMCallError raised."""
        import httpx

        provider = OpenAIProvider(api_key="sk-test", model="gpt-4o", timeout=1)

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, side_effect=httpx.TimeoutException("timeout")):
            with pytest.raises(LLMCallError):
                asyncio.run(provider.complete("test"))

    def test_auth_failure_immediate_no_retry(self):
        """Auth failure (401/403) → immediate failure, no retry."""
        import httpx

        provider = OpenAIProvider(api_key="sk-invalid", model="gpt-4o", max_retries=3)

        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Unauthorized", request=MagicMock(), response=mock_response
        )

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response) as mock_post:
            with pytest.raises(LLMCallError):
                asyncio.run(provider.complete("test"))
            # Should NOT retry on auth failure
            assert mock_post.call_count == 1

    def test_rate_limit_error(self):
        """Rate limit (429) → appropriate error."""
        import httpx

        provider = OpenAIProvider(api_key="sk-test", model="gpt-4o", max_retries=1)

        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {"Retry-After": "5"}
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Rate limited", request=MagicMock(), response=mock_response
        )

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
            with pytest.raises(LLMCallError) as exc_info:
                asyncio.run(provider.complete("test"))
            assert "rate" in str(exc_info.value).lower() or "429" in str(exc_info.value)

    def test_estimate_tokens_returns_reasonable_count(self):
        """estimate_tokens returns reasonable count (len/4 heuristic)."""
        provider = OpenAIProvider(api_key="sk-test", model="gpt-4o")
        text = "Hello world, this is a test prompt for token estimation."
        tokens = provider.estimate_tokens(text)

        assert tokens > 0
        # Rough heuristic: ~4 chars per token
        assert tokens >= len(text) // 6  # Allow some variance
        assert tokens <= len(text)  # Can't be more tokens than chars

    def test_provider_name_property(self):
        """provider_name returns 'openai'."""
        provider = OpenAIProvider(api_key="sk-test", model="gpt-4o")
        assert provider.provider_name == "openai"

    def test_model_name_property(self):
        """model_name returns correct model."""
        provider = OpenAIProvider(api_key="sk-test", model="gpt-4o")
        assert provider.model_name == "gpt-4o"

    def test_cost_properties(self):
        """cost_per_1k_input and cost_per_1k_output return correct values."""
        provider = OpenAIProvider(api_key="sk-test", model="gpt-4o")
        assert provider.cost_per_1k_input > 0
        assert provider.cost_per_1k_output > 0


# ============================================================================
# Anthropic Provider Tests
# ============================================================================


class TestAnthropicProvider:
    """Unit tests for AnthropicProvider."""

    def test_complete_with_mock_response(self):
        """AnthropicProvider.complete() with mock httpx response → correct response text."""
        provider = AnthropicProvider(api_key="ant-test", model="claude-sonnet-4-20250514")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "content": [{"type": "text", "text": '{"features": []}'}]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
            result = asyncio.run(provider.complete("Analyze this code"))

        assert result == '{"features": []}'

    def test_timeout_raises_llm_call_error(self):
        """Anthropic timeout → LLMCallError raised."""
        import httpx

        provider = AnthropicProvider(api_key="ant-test", model="claude-sonnet-4-20250514", timeout=1)

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, side_effect=httpx.TimeoutException("timeout")):
            with pytest.raises(LLMCallError):
                asyncio.run(provider.complete("test"))

    def test_auth_failure_immediate_no_retry(self):
        """Auth failure (401/403) → immediate failure, no retry."""
        import httpx

        provider = AnthropicProvider(api_key="ant-invalid", model="claude-sonnet-4-20250514", max_retries=3)

        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Forbidden", request=MagicMock(), response=mock_response
        )

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response) as mock_post:
            with pytest.raises(LLMCallError):
                asyncio.run(provider.complete("test"))
            assert mock_post.call_count == 1

    def test_provider_name_property(self):
        """provider_name returns 'anthropic'."""
        provider = AnthropicProvider(api_key="ant-test", model="claude-sonnet-4-20250514")
        assert provider.provider_name == "anthropic"

    def test_model_name_property(self):
        """model_name returns correct model."""
        provider = AnthropicProvider(api_key="ant-test", model="claude-sonnet-4-20250514")
        assert provider.model_name == "claude-sonnet-4-20250514"

    def test_cost_properties(self):
        """cost_per_1k_input and cost_per_1k_output return correct values."""
        provider = AnthropicProvider(api_key="ant-test", model="claude-sonnet-4-20250514")
        assert provider.cost_per_1k_input > 0
        assert provider.cost_per_1k_output > 0


# ============================================================================
# Ollama Provider Tests
# ============================================================================


class TestOllamaProvider:
    """Unit tests for OllamaProvider."""

    def test_complete_with_mock_response(self):
        """OllamaProvider.complete() with mock httpx response → correct response text."""
        provider = OllamaProvider(url="http://localhost:11434", model="qwen3:8b")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": '{"features": []}'
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
            result = asyncio.run(provider.complete("Analyze this code"))

        assert result == '{"features": []}'

    def test_connection_failure_raises_error(self):
        """Connection failure → clear error message."""
        import httpx

        provider = OllamaProvider(url="http://localhost:99999", model="qwen3:8b")

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, side_effect=httpx.ConnectError("Connection refused")):
            with pytest.raises(LLMCallError) as exc_info:
                asyncio.run(provider.complete("test"))
            assert "connect" in str(exc_info.value).lower() or "connection" in str(exc_info.value).lower()

    def test_provider_name_property(self):
        """provider_name returns 'ollama'."""
        provider = OllamaProvider(url="http://localhost:11434", model="qwen3:8b")
        assert provider.provider_name == "ollama"

    def test_model_name_property(self):
        """model_name returns correct model."""
        provider = OllamaProvider(url="http://localhost:11434", model="qwen3:8b")
        assert provider.model_name == "qwen3:8b"

    def test_cost_properties_are_zero(self):
        """cost_per_1k_input and cost_per_1k_output return 0.0 for local."""
        provider = OllamaProvider(url="http://localhost:11434", model="qwen3:8b")
        assert provider.cost_per_1k_input == 0.0
        assert provider.cost_per_1k_output == 0.0

    def test_estimate_tokens(self):
        """estimate_tokens returns reasonable count."""
        provider = OllamaProvider(url="http://localhost:11434", model="qwen3:8b")
        tokens = provider.estimate_tokens("Hello world test")
        assert tokens > 0


# ============================================================================
# Provider Factory Tests
# ============================================================================


class TestCreateProvider:
    """Unit tests for create_provider factory."""

    def test_create_openai_provider(self):
        """create_provider with valid OpenAI config → OpenAIProvider."""
        config = TheDoorConfig(
            default_provider="openai",
            openai_api_key="sk-test",
            openai_model="gpt-4o",
        )
        provider = create_provider(config)

        assert isinstance(provider, OpenAIProvider)
        assert provider.provider_name == "openai"
        assert provider.model_name == "gpt-4o"

    def test_create_anthropic_provider(self):
        """create_provider with valid Anthropic config → AnthropicProvider."""
        config = TheDoorConfig(
            default_provider="anthropic",
            anthropic_api_key="ant-test",
            anthropic_model="claude-sonnet-4-20250514",
        )
        provider = create_provider(config)

        assert isinstance(provider, AnthropicProvider)
        assert provider.provider_name == "anthropic"

    def test_create_ollama_provider(self):
        """create_provider with valid Ollama config → OllamaProvider."""
        config = TheDoorConfig(
            default_provider="ollama",
            ollama_url="http://localhost:11434",
            ollama_model="qwen3:8b",
        )
        provider = create_provider(config)

        assert isinstance(provider, OllamaProvider)
        assert provider.provider_name == "ollama"

    def test_create_provider_invalid_config_raises_error(self):
        """create_provider with invalid config → ConfigError."""
        config = TheDoorConfig(
            default_provider="invalid_provider_xyz",
        )

        with pytest.raises(ConfigError):
            create_provider(config)
