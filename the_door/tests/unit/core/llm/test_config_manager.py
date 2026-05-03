"""Unit tests for config_manager module.

Tests are written BEFORE implementation (TDD red phase).
"""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from the_door.core.llm.config_manager import ConfigManager, ConfigError
from the_door.models import TheDoorConfig


class TestConfigManagerLoad:
    """Unit tests for ConfigManager.load()."""

    def test_load_valid_config_toml(self, tmp_path: Path):
        """Load from valid config.toml → TheDoorConfig with correct values."""
        config_path = tmp_path / "config.toml"
        config_path.write_text(
            '[provider]\n'
            'default = "openai"\n'
            '\n'
            '[provider.openai]\n'
            'api_key = "sk-test-key-123"\n'
            'model = "gpt-4o"\n'
            '\n'
            '[provider.anthropic]\n'
            'api_key = "ant-test-key-456"\n'
            'model = "claude-sonnet-4-20250514"\n'
            '\n'
            '[provider.ollama]\n'
            'url = "http://localhost:11434"\n'
            'model = "qwen3:8b"\n'
            '\n'
            '[settings]\n'
            'max_retries = 5\n'
            'timeout_seconds = 180\n'
            'cost_warning_threshold = 2.50\n'
        )

        # Clear env vars to avoid interference
        env_clear = {k: v for k, v in os.environ.items()
                     if k not in ("THE_DOOR_OPENAI_KEY", "THE_DOOR_ANTHROPIC_KEY", "THE_DOOR_OLLAMA_URL")}
        with patch.dict(os.environ, env_clear, clear=True):
            config = ConfigManager.load(config_path)

        assert isinstance(config, TheDoorConfig)
        assert config.default_provider == "openai"
        assert config.openai_api_key == "sk-test-key-123"
        assert config.openai_model == "gpt-4o"
        assert config.anthropic_api_key == "ant-test-key-456"
        assert config.anthropic_model == "claude-sonnet-4-20250514"
        assert config.ollama_url == "http://localhost:11434"
        assert config.ollama_model == "qwen3:8b"
        assert config.max_retries == 5
        assert config.timeout_seconds == 180
        assert config.cost_warning_threshold == 2.50

    def test_missing_config_file_uses_defaults(self, tmp_path: Path):
        """Missing config file → defaults + env vars used."""
        config_path = tmp_path / "nonexistent.toml"

        env_clear = {k: v for k, v in os.environ.items()
                     if k not in ("THE_DOOR_OPENAI_KEY", "THE_DOOR_ANTHROPIC_KEY", "THE_DOOR_OLLAMA_URL")}
        with patch.dict(os.environ, env_clear, clear=True):
            config = ConfigManager.load(config_path)

        assert isinstance(config, TheDoorConfig)
        assert config.default_provider == "openai"
        assert config.openai_model == "gpt-4o"

    def test_invalid_toml_syntax_raises_error(self, tmp_path: Path):
        """Invalid TOML syntax → clear error with parse location."""
        config_path = tmp_path / "config.toml"
        config_path.write_text(
            '[provider\n'  # Missing closing bracket
            'default = "openai"\n'
        )

        with pytest.raises(ConfigError) as exc_info:
            ConfigManager.load(config_path)

        assert "parse" in str(exc_info.value).lower() or "toml" in str(exc_info.value).lower()

    def test_env_var_openai_key_overrides_file(self, tmp_path: Path):
        """Env var THE_DOOR_OPENAI_KEY overrides file value."""
        config_path = tmp_path / "config.toml"
        config_path.write_text(
            '[provider]\ndefault = "openai"\n\n'
            '[provider.openai]\napi_key = "file-key"\nmodel = "gpt-4o"\n'
        )

        with patch.dict(os.environ, {"THE_DOOR_OPENAI_KEY": "env-key"}, clear=False):
            config = ConfigManager.load(config_path)

        assert config.openai_api_key == "env-key"

    def test_env_var_anthropic_key_overrides_file(self, tmp_path: Path):
        """Env var THE_DOOR_ANTHROPIC_KEY overrides file value."""
        config_path = tmp_path / "config.toml"
        config_path.write_text(
            '[provider]\ndefault = "anthropic"\n\n'
            '[provider.anthropic]\napi_key = "file-key"\nmodel = "claude-sonnet-4-20250514"\n'
        )

        with patch.dict(os.environ, {"THE_DOOR_ANTHROPIC_KEY": "env-key"}, clear=False):
            config = ConfigManager.load(config_path)

        assert config.anthropic_api_key == "env-key"

    def test_env_var_ollama_url_overrides_file(self, tmp_path: Path):
        """Env var THE_DOOR_OLLAMA_URL overrides file value."""
        config_path = tmp_path / "config.toml"
        config_path.write_text(
            '[provider]\ndefault = "ollama"\n\n'
            '[provider.ollama]\nurl = "http://localhost:11434"\nmodel = "qwen3:8b"\n'
        )

        with patch.dict(os.environ, {"THE_DOOR_OLLAMA_URL": "http://remote:8080"}, clear=False):
            config = ConfigManager.load(config_path)

        assert config.ollama_url == "http://remote:8080"

    def test_no_api_key_for_selected_provider_raises_error(self, tmp_path: Path):
        """No API key for selected provider → clear error message."""
        config_path = tmp_path / "config.toml"
        config_path.write_text(
            '[provider]\ndefault = "openai"\n\n'
            '[provider.openai]\nmodel = "gpt-4o"\n'  # No api_key!
        )

        env_clear = {k: v for k, v in os.environ.items()
                     if k not in ("THE_DOOR_OPENAI_KEY", "THE_DOOR_ANTHROPIC_KEY", "THE_DOOR_OLLAMA_URL")}
        with patch.dict(os.environ, env_clear, clear=True):
            # validate() should detect missing key
            config = ConfigManager.load(config_path)
            errors = ConfigManager.validate(config)
            assert any("key" in e.lower() or "api" in e.lower() for e in errors)


class TestConfigManagerInitDefault:
    """Unit tests for ConfigManager.init_default()."""

    def test_init_default_creates_config_file(self, tmp_path: Path):
        """init_default creates config.toml at expected path."""
        config_path = tmp_path / "config.toml"
        assert not config_path.exists()

        ConfigManager.init_default(config_path)

        assert config_path.exists()
        content = config_path.read_text()
        assert "[provider]" in content
        assert "openai" in content


class TestConfigManagerValidate:
    """Unit tests for ConfigManager.validate()."""

    def test_validate_warns_about_missing_provider_key(self):
        """validate() warns about unreachable/misconfigured providers."""
        config = TheDoorConfig(
            default_provider="openai",
            openai_api_key=None,  # Missing!
        )

        warnings = ConfigManager.validate(config)
        assert len(warnings) > 0
        assert any("openai" in w.lower() or "key" in w.lower() for w in warnings)
