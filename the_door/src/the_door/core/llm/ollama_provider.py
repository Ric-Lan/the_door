"""Ollama local model provider implementation."""
from __future__ import annotations

import httpx

from the_door.core.llm.provider import LLMCallError


class OllamaProvider:
    """Ollama local model provider. Connects to local Ollama server via HTTP."""

    def __init__(
        self,
        url: str = "http://localhost:11434",
        model: str = "qwen3:8b",
        timeout: int = 300,
    ) -> None:
        self._url = url.rstrip("/")
        self._model = model
        self._timeout = timeout

    async def complete(self, prompt: str, system_prompt: str | None = None) -> str:
        """Send prompt to Ollama and return response text."""
        payload: dict = {
            "model": self._model,
            "prompt": prompt,
            "stream": False,
        }
        if system_prompt:
            payload["system"] = system_prompt

        api_url = f"{self._url}/api/generate"

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(api_url, json=payload)
                response.raise_for_status()
                data = response.json()
                return data.get("response", "")

        except httpx.ConnectError as e:
            raise LLMCallError(
                f"Cannot connect to Ollama at {self._url}. "
                f"Ensure Ollama is running: {e}"
            )
        except httpx.TimeoutException as e:
            raise LLMCallError(f"Ollama request timed out after {self._timeout}s: {e}")
        except httpx.HTTPStatusError as e:
            raise LLMCallError(f"Ollama HTTP error: {e}")

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count using ~4 chars per token heuristic."""
        return max(1, len(text) // 4)

    @property
    def provider_name(self) -> str:
        return "ollama"

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def cost_per_1k_input(self) -> float:
        return 0.0

    @property
    def cost_per_1k_output(self) -> float:
        return 0.0
