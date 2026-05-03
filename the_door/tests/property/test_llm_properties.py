"""Property-based tests for LLM layer.

Tests are written BEFORE implementation (TDD red phase).
Uses Hypothesis to verify universal correctness properties.
"""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from the_door.core.llm.config_manager import ConfigManager


# === Strategies ===

# Generate plausible API key strings (non-empty, ASCII alphanumeric + dash/underscore)
API_KEY = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="-_",
                           min_codepoint=32, max_codepoint=126),
    min_size=8,
    max_size=64,
).filter(lambda s: s.isascii())

# Generate plausible URL strings for Ollama
OLLAMA_URL = st.builds(
    lambda host, port: f"http://{host}:{port}",
    host=st.sampled_from(["localhost", "127.0.0.1", "192.168.1.100", "ollama.local"]),
    port=st.integers(min_value=1024, max_value=65535),
)


# === Property 22: Config environment variable precedence ===


class TestConfigEnvVarPrecedence:
    """Property 22: Environment variables always override config file values.

    When both a config file value and an environment variable exist for the
    same setting, the loaded config MUST use the environment variable value.
    """

    @given(
        file_openai_key=API_KEY,
        env_openai_key=API_KEY,
    )
    def test_openai_key_env_overrides_file(
        self, tmp_path: Path, file_openai_key: str, env_openai_key: str
    ):
        """THE_DOOR_OPENAI_KEY env var always overrides config file openai_api_key."""
        assume(file_openai_key != env_openai_key)

        # Write config file with one value
        config_path = tmp_path / "config.toml"
        config_path.write_text(
            f'[provider]\ndefault = "openai"\n\n[provider.openai]\napi_key = "{file_openai_key}"\nmodel = "gpt-4o"\n',
            encoding="utf-8",
        )

        # Set env var with different value
        env = {"THE_DOOR_OPENAI_KEY": env_openai_key}
        with patch.dict(os.environ, env, clear=False):
            config = ConfigManager.load(config_path)

        # Env var MUST win
        assert config.openai_api_key == env_openai_key

    @given(
        file_anthropic_key=API_KEY,
        env_anthropic_key=API_KEY,
    )
    def test_anthropic_key_env_overrides_file(
        self, tmp_path: Path, file_anthropic_key: str, env_anthropic_key: str
    ):
        """THE_DOOR_ANTHROPIC_KEY env var always overrides config file anthropic_api_key."""
        assume(file_anthropic_key != env_anthropic_key)

        config_path = tmp_path / "config.toml"
        config_path.write_text(
            f'[provider]\ndefault = "anthropic"\n\n[provider.anthropic]\napi_key = "{file_anthropic_key}"\nmodel = "claude-sonnet-4-20250514"\n',
            encoding="utf-8",
        )

        env = {"THE_DOOR_ANTHROPIC_KEY": env_anthropic_key}
        with patch.dict(os.environ, env, clear=False):
            config = ConfigManager.load(config_path)

        assert config.anthropic_api_key == env_anthropic_key

    @given(
        file_ollama_url=OLLAMA_URL,
        env_ollama_url=OLLAMA_URL,
    )
    def test_ollama_url_env_overrides_file(
        self, tmp_path: Path, file_ollama_url: str, env_ollama_url: str
    ):
        """THE_DOOR_OLLAMA_URL env var always overrides config file ollama_url."""
        assume(file_ollama_url != env_ollama_url)

        config_path = tmp_path / "config.toml"
        config_path.write_text(
            f'[provider]\ndefault = "ollama"\n\n[provider.ollama]\nurl = "{file_ollama_url}"\nmodel = "qwen3:8b"\n',
            encoding="utf-8",
        )

        env = {"THE_DOOR_OLLAMA_URL": env_ollama_url}
        with patch.dict(os.environ, env, clear=False):
            config = ConfigManager.load(config_path)

        assert config.ollama_url == env_ollama_url

    @given(env_openai_key=API_KEY)
    def test_env_var_used_when_no_config_file(self, tmp_path: Path, env_openai_key: str):
        """Env var provides value even when config file does not exist."""
        config_path = tmp_path / "nonexistent_config.toml"

        env = {"THE_DOOR_OPENAI_KEY": env_openai_key}
        with patch.dict(os.environ, env, clear=False):
            config = ConfigManager.load(config_path)

        assert config.openai_api_key == env_openai_key

    @given(file_openai_key=API_KEY)
    def test_file_value_used_when_no_env_var(self, tmp_path: Path, file_openai_key: str):
        """Config file value used when no env var is set."""
        config_path = tmp_path / "config.toml"
        config_path.write_text(
            f'[provider]\ndefault = "openai"\n\n[provider.openai]\napi_key = "{file_openai_key}"\nmodel = "gpt-4o"\n',
            encoding="utf-8",
        )

        # Ensure env vars are NOT set
        env_remove = {
            "THE_DOOR_OPENAI_KEY": None,
            "THE_DOOR_ANTHROPIC_KEY": None,
            "THE_DOOR_OLLAMA_URL": None,
        }
        clean_env = {k: v for k, v in os.environ.items() if k not in env_remove}
        with patch.dict(os.environ, clean_env, clear=True):
            config = ConfigManager.load(config_path)

        assert config.openai_api_key == file_openai_key
