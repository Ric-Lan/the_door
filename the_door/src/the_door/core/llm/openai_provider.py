"""OpenAI API provider implementation."""
from __future__ import annotations

import asyncio

import httpx

from the_door.core.llm.provider import LLMCallError


class OpenAIProvider:
    """OpenAI API provider (GPT-4 family). Uses httpx for async HTTP calls."""

    API_URL = "https://api.openai.com/v1/chat/completions"

    # Pricing per 1K tokens (approximate, GPT-4o)
    _COST_INPUT = 0.005  # $5 per 1M input tokens
    _COST_OUTPUT = 0.015  # $15 per 1M output tokens

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o",
        timeout: int = 120,
        max_retries: int = 3,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._timeout = timeout
        self._max_retries = max_retries

    async def complete(self, prompt: str, system_prompt: str | None = None) -> str:
        """Send prompt to OpenAI and return response text.

        Retries with exponential backoff on transient errors.
        Immediate failure on auth errors (401/403).
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self._model,
            "messages": messages,
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
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
                            f"OpenAI authentication failed (HTTP {response.status_code})"
                        )

                    # Rate limit
                    if response.status_code == 429:
                        retry_after = response.headers.get("Retry-After", "5")
                        raise LLMCallError(
                            f"OpenAI rate limited (429). Retry-After: {retry_after}s"
                        )

                    response.raise_for_status()
                    data = response.json()
                    return data["choices"][0]["message"]["content"]

            except LLMCallError:
                raise
            except httpx.TimeoutException as e:
                last_error = e
                if attempt < self._max_retries - 1:
                    await asyncio.sleep(2**attempt)  # 1s, 2s, 4s
                continue
            except httpx.HTTPStatusError as e:
                # Auth errors already handled above
                if e.response.status_code in (401, 403):
                    raise LLMCallError(
                        f"OpenAI authentication failed (HTTP {e.response.status_code})"
                    )
                if e.response.status_code == 429:
                    raise LLMCallError(
                        f"OpenAI rate limited (429)"
                    )
                last_error = e
                if attempt < self._max_retries - 1:
                    await asyncio.sleep(2**attempt)
                continue
            except httpx.ConnectError as e:
                last_error = e
                if attempt < self._max_retries - 1:
                    await asyncio.sleep(2**attempt)
                continue

        raise LLMCallError(f"OpenAI call failed after {self._max_retries} retries: {last_error}")

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count using ~4 chars per token heuristic."""
        return max(1, len(text) // 4)

    @property
    def provider_name(self) -> str:
        return "openai"

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def cost_per_1k_input(self) -> float:
        return self._COST_INPUT

    @property
    def cost_per_1k_output(self) -> float:
        return self._COST_OUTPUT
