"""LLM Provider protocol and factory."""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from the_door.core.llm.config_manager import ConfigError
from the_door.models import TheDoorConfig


class LLMCallError(Exception):
    """Raised when an LLM API call fails."""

    pass


@runtime_checkable
class LLMProvider(Protocol):
    """Protocol for LLM API providers. Implementations handle transport only."""

    async def complete(self, prompt: str, system_prompt: str | None = None) -> str:
        """Send prompt to LLM and return raw response text.

        Raises LLMCallError on transport/API failure.
        """
        ...

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for the given text."""
        ...

    @property
    def provider_name(self) -> str:
        """Return provider identifier: 'openai', 'anthropic', 'ollama'."""
        ...

    @property
    def model_name(self) -> str:
        """Return the model being used."""
        ...

    @property
    def cost_per_1k_input(self) -> float:
        """Cost per 1000 input tokens in USD. 0.0 for local models."""
        ...

    @property
    def cost_per_1k_output(self) -> float:
        """Cost per 1000 output tokens in USD. 0.0 for local models."""
        ...


def create_provider(config: TheDoorConfig) -> LLMProvider:
    """Factory: create provider from config. Raises ConfigError if invalid."""
    provider = config.default_provider

    if provider == "openai":
        from the_door.core.llm.openai_provider import OpenAIProvider

        if not config.openai_api_key:
            raise ConfigError("OpenAI API key not configured")
        return OpenAIProvider(
            api_key=config.openai_api_key,
            model=config.openai_model,
            timeout=config.timeout_seconds,
            max_retries=config.max_retries,
        )
    elif provider == "anthropic":
        from the_door.core.llm.anthropic_provider import AnthropicProvider

        if not config.anthropic_api_key:
            raise ConfigError("Anthropic API key not configured")
        return AnthropicProvider(
            api_key=config.anthropic_api_key,
            model=config.anthropic_model,
            timeout=config.timeout_seconds,
            max_retries=config.max_retries,
        )
    elif provider == "ollama":
        from the_door.core.llm.ollama_provider import OllamaProvider

        return OllamaProvider(
            url=config.ollama_url,
            model=config.ollama_model,
            timeout=config.timeout_seconds,
        )
    else:
        raise ConfigError(f"Unknown provider: '{provider}'. Must be 'openai', 'anthropic', or 'ollama'.")
