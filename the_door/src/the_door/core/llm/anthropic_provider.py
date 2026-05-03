"""Anthropic API provider implementation."""
from __future__ import annotations

import asyncio

import httpx

from the_door.core.llm.provider import LLMCallError


class AnthropicProvider:
    """Anthropic API provider (Claude family). Uses httpx for async HTTP calls."""

    API_URL = "https://api.anthropic.com/v1/messages"

    # Pricing per 1K tokens (approximate, Claude Sonnet)
    _COST_INPUT = 0.003  # $3 per 1M input tokens
    _COST_OUTPUT = 0.015  # $15 per 1M output tokens

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-20250514",
        timeout: int = 120,
        max_retries: int = 3,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._timeout = timeout
        self._max_retries = max_retries

    async def complete(self, prompt: str, system_prompt: str | None = None) -> str:
        """Send prompt to Anthropic and return response text.

        Retries with exponential backoff on transient errors.
        Immediate failure on auth errors (401/403).
        """
        payload: dict = {
            "model": self._model,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system_prompt:
            payload["system"] = system_prompt

        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

        last_error: Exception | None = None

        for attempt in range(self._max_retries):
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    response = await client.post(
                        self.API_URL,
                        json=payload,
                        headers=headers,
                    )

                    # Auth failure — immediate, no retry
                    if response.status_code in (401, 403):
                        raise LLMCallError(
                            f"Anthropic authentication failed (HTTP {response.status_code})"
                        )

                    # Rate limit
                    if response.status_code == 429:
                        retry_after = response.headers.get("Retry-After", "5")
                        raise LLMCallError(
                            f"Anthropic rate limited (429). Retry-After: {retry_after}s"
                        )

                    response.raise_for_status()
                    data = response.json()
                    # Anthropic returns content as array of blocks
                    content_blocks = data.get("content", [])
                    text_parts = [
                        block["text"]
                        for block in content_blocks
                        if block.get("type") == "text"
                    ]
                    return "".join(text_parts)

            except LLMCallError:
                raise
            except httpx.TimeoutException as e:
                last_error = e
                if attempt < self._max_retries - 1:
                    await asyncio.sleep(2**attempt)
                continue
            except httpx.HTTPStatusError as e:
                if e.response.status_code in (401, 403):
                    raise LLMCallError(
                        f"Anthropic authentication failed (HTTP {e.response.status_code})"
                    )
                if e.response.status_code == 429:
                    raise LLMCallError(f"Anthropic rate limited (429)")
                last_error = e
                if attempt < self._max_retries - 1:
                    await asyncio.sleep(2**attempt)
                continue
            except httpx.ConnectError as e:
                last_error = e
                if attempt < self._max_retries - 1:
                    await asyncio.sleep(2**attempt)
                continue

        raise LLMCallError(
            f"Anthropic call failed after {self._max_retries} retries: {last_error}"
        )

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count using ~4 chars per token heuristic."""
        return max(1, len(text) // 4)

    @property
    def provider_name(self) -> str:
        return "anthropic"

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def cost_per_1k_input(self) -> float:
        return self._COST_INPUT

    @property
    def cost_per_1k_output(self) -> float:
        return self._COST_OUTPUT
