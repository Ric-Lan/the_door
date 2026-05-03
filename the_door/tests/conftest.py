"""Shared test configuration."""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest
from hypothesis import HealthCheck, settings

# Suppress the function_scoped_fixture health check globally since our
# property tests intentionally use tmp_path with @given decorators.
# Each test creates unique files inside tmp_path so reuse is safe.
settings.register_profile(
    "default",
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
settings.load_profile("default")


# ============================================================================
# Fixtures directory path helper
# ============================================================================

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture()
def fixtures_dir() -> Path:
    """Return the path to the test fixtures directory."""
    return FIXTURES_DIR


# ============================================================================
# MockLLMProvider — complies with the LLMProvider protocol
# ============================================================================


class MockLLMProvider:
    """A mock LLM provider for testing.

    Supports pre-configured responses, call recording, and the full
    LLMProvider protocol interface. Responses can be:
    - A string (returned as-is)
    - A dict/list (serialized to JSON)
    - A callable (called with prompt, returns string)
    - A list of responses (consumed in order, cycling the last one)
    """

    def __init__(
        self,
        responses: str | dict | list | None = None,
        *,
        provider: str = "mock",
        model: str = "mock-model",
        cost_input: float = 0.0,
        cost_output: float = 0.0,
        tokens_per_char: float = 0.25,
    ) -> None:
        self._responses: list[Any] = []
        self._call_index = 0
        self._calls: list[dict[str, Any]] = []
        self._provider = provider
        self._model = model
        self._cost_input = cost_input
        self._cost_output = cost_output
        self._tokens_per_char = tokens_per_char

        if responses is not None:
            self.set_responses(responses)

    def set_responses(self, responses: str | dict | list | Any) -> None:
        """Configure responses. A list means sequential responses."""
        if isinstance(responses, list) and all(
            isinstance(r, (str, dict, list)) or callable(r) for r in responses
        ):
            self._responses = responses
        else:
            self._responses = [responses]
        self._call_index = 0

    def _get_next_response(self, prompt: str) -> str:
        """Get the next response, cycling the last one if exhausted."""
        if not self._responses:
            return "{}"

        idx = min(self._call_index, len(self._responses) - 1)
        response = self._responses[idx]
        self._call_index += 1

        if callable(response):
            return response(prompt)
        elif isinstance(response, (dict, list)):
            return json.dumps(response)
        return str(response)

    async def complete(self, prompt: str, system_prompt: str | None = None) -> str:
        """Send prompt and return pre-configured response."""
        call_record = {
            "prompt": prompt,
            "system_prompt": system_prompt,
            "call_index": len(self._calls),
        }
        self._calls.append(call_record)
        return self._get_next_response(prompt)

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count using configurable chars-per-token ratio."""
        return max(1, int(len(text) * self._tokens_per_char))

    @property
    def provider_name(self) -> str:
        """Return provider identifier."""
        return self._provider

    @property
    def model_name(self) -> str:
        """Return model name."""
        return self._model

    @property
    def cost_per_1k_input(self) -> float:
        """Cost per 1000 input tokens in USD."""
        return self._cost_input

    @property
    def cost_per_1k_output(self) -> float:
        """Cost per 1000 output tokens in USD."""
        return self._cost_output

    # === Test inspection helpers ===

    @property
    def calls(self) -> list[dict[str, Any]]:
        """Return all recorded calls."""
        return self._calls

    @property
    def call_count(self) -> int:
        """Return number of calls made."""
        return len(self._calls)

    @property
    def last_call(self) -> dict[str, Any] | None:
        """Return the last call record, or None if no calls made."""
        return self._calls[-1] if self._calls else None

    def reset(self) -> None:
        """Reset call history and response index."""
        self._calls.clear()
        self._call_index = 0


@pytest.fixture()
def mock_llm() -> MockLLMProvider:
    """Provide a fresh MockLLMProvider instance."""
    return MockLLMProvider()


@pytest.fixture()
def mock_llm_with_responses():
    """Factory fixture: create MockLLMProvider with pre-configured responses."""

    def _factory(responses, **kwargs):
        return MockLLMProvider(responses, **kwargs)

    return _factory


# ============================================================================
# Autouse fixtures
# ============================================================================


@pytest.fixture(autouse=True)
def _clean_tmp_path(tmp_path):
    """Clean tmp_path before each test / Hypothesis example reuse.

    Hypothesis reuses the same tmp_path across examples, so we clear it
    at the start of each invocation to avoid leftover files.
    """
    # Clean any existing contents
    for child in tmp_path.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()
    yield
