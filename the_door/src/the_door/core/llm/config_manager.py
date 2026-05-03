"""Configuration manager for The Door LLM providers."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from the_door.models import TheDoorConfig


class ConfigError(Exception):
    """Raised when configuration is invalid or cannot be loaded."""

    pass


# Use tomllib (3.11+) or tomli (3.10)
if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ImportError:
        tomllib = None  # type: ignore[assignment]


class ConfigManager:
    """Read config from ~/.the-door/config.toml with env var override."""

    DEFAULT_CONFIG_PATH = Path.home() / ".the-door" / "config.toml"

    @staticmethod
    def load(config_path: Path | None = None) -> TheDoorConfig:
        """Load config. Env vars (THE_DOOR_*) override file values.

        If config_path is None, uses DEFAULT_CONFIG_PATH.
        If file doesn't exist, returns defaults with env var overrides.
        """
        if config_path is None:
            config_path = ConfigManager.DEFAULT_CONFIG_PATH

        config = TheDoorConfig()

        # Load from file if it exists
        if config_path.exists():
            try:
                with open(config_path, "rb") as f:
                    data = tomllib.loads(config_path.read_text(encoding="utf-8"))
            except Exception as e:
                raise ConfigError(f"Failed to parse TOML config at {config_path}: {e}")

            # Extract provider settings
            provider_section = data.get("provider", {})
            config.default_provider = provider_section.get("default", config.default_provider)

            # OpenAI
            openai = provider_section.get("openai", {})
            if openai.get("api_key"):
                config.openai_api_key = openai["api_key"]
            if openai.get("model"):
                config.openai_model = openai["model"]

            # Anthropic
            anthropic = provider_section.get("anthropic", {})
            if anthropic.get("api_key"):
                config.anthropic_api_key = anthropic["api_key"]
            if anthropic.get("model"):
                config.anthropic_model = anthropic["model"]

            # Ollama
            ollama = provider_section.get("ollama", {})
            if ollama.get("url"):
                config.ollama_url = ollama["url"]
            if ollama.get("model"):
                config.ollama_model = ollama["model"]

            # Settings
            settings = data.get("settings", {})
            if "max_retries" in settings:
                config.max_retries = settings["max_retries"]
            if "timeout_seconds" in settings:
                config.timeout_seconds = settings["timeout_seconds"]
            if "cost_warning_threshold" in settings:
                config.cost_warning_threshold = settings["cost_warning_threshold"]

        # Environment variable overrides (always take precedence)
        env_openai_key = os.environ.get("THE_DOOR_OPENAI_KEY")
        if env_openai_key:
            config.openai_api_key = env_openai_key

        env_anthropic_key = os.environ.get("THE_DOOR_ANTHROPIC_KEY")
        if env_anthropic_key:
            config.anthropic_api_key = env_anthropic_key

        env_ollama_url = os.environ.get("THE_DOOR_OLLAMA_URL")
        if env_ollama_url:
            config.ollama_url = env_ollama_url

        return config

    @staticmethod
    def init_default(config_path: Path | None = None) -> Path:
        """Create default config.toml at config_path. Returns path."""
        if config_path is None:
            config_path = ConfigManager.DEFAULT_CONFIG_PATH

        config_path.parent.mkdir(parents=True, exist_ok=True)

        default_content = """\
# The Door Configuration
# See: https://the-door.dev/docs/configuration

[provider]
default = "openai"

[provider.openai]
# api_key = "sk-your-key-here"
model = "gpt-4o"

[provider.anthropic]
# api_key = "your-anthropic-key-here"
model = "claude-sonnet-4-20250514"

[provider.ollama]
url = "http://localhost:11434"
model = "qwen3:8b"

[settings]
max_retries = 3
timeout_seconds = 120
cost_warning_threshold = 1.00
"""
        config_path.write_text(default_content, encoding="utf-8")
        return config_path

    @staticmethod
    def validate(config: TheDoorConfig) -> list[str]:
        """Check config validity. Returns list of warning messages."""
        warnings: list[str] = []

        provider = config.default_provider

        if provider == "openai" and not config.openai_api_key:
            warnings.append(
                "OpenAI selected as default provider but no API key configured. "
                "Set THE_DOOR_OPENAI_KEY env var or add api_key to config.toml."
            )
        elif provider == "anthropic" and not config.anthropic_api_key:
            warnings.append(
                "Anthropic selected as default provider but no API key configured. "
                "Set THE_DOOR_ANTHROPIC_KEY env var or add api_key to config.toml."
            )
        elif provider == "ollama":
            if not config.ollama_url:
                warnings.append(
                    "Ollama selected but no URL configured. "
                    "Set THE_DOOR_OLLAMA_URL env var or add url to config.toml."
                )

        return warnings
