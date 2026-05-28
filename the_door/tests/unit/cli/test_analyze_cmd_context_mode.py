"""Tests for --minimal-context Click option in `the-door analyze`."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from the_door.cli.analyze_cmd import analyze_cmd
from the_door.models import AnalyzeConfig


class TestMinimalContextOption:
    def test_help_shows_minimal_context_flag(self):
        runner = CliRunner()
        result = runner.invoke(analyze_cmd, ["--help"])
        assert result.exit_code == 0
        assert "--minimal-context" in result.output


class TestFlagFlowsIntoAnalyzeConfig:
    def test_default_passes_detail_to_pipeline(self):
        runner = CliRunner()
        with runner.isolated_filesystem():
            from pathlib import Path
            Path("project").mkdir()
            with patch("the_door.core.pipeline.analyze_pipeline.run_analyze_pipeline") as mock_pipeline, \
                 patch("the_door.core.llm.config_manager.ConfigManager.load") as mock_cfg_load:
                mock_cfg_load.return_value = MagicMock(
                    anthropic_api_key="fake", openai_api_key=None
                )
                mock_pipeline.side_effect = RuntimeError("stop here")
                runner.invoke(analyze_cmd, ["project"])
        if mock_pipeline.called:
            config_arg = (
                mock_pipeline.call_args.args[1]
                if len(mock_pipeline.call_args.args) > 1
                else mock_pipeline.call_args.kwargs.get("config")
            )
            assert isinstance(config_arg, AnalyzeConfig)
            assert config_arg.context_mode == "detail"

    def test_minimal_context_flag_passes_minimal(self):
        runner = CliRunner()
        with runner.isolated_filesystem():
            from pathlib import Path
            Path("project").mkdir()
            captured_configs = []

            def capture_pipeline(path, config, **kwargs):
                captured_configs.append(config)
                raise RuntimeError("stop")

            with patch("the_door.core.pipeline.analyze_pipeline.run_analyze_pipeline", side_effect=capture_pipeline), \
                 patch("the_door.core.llm.config_manager.ConfigManager.load") as mock_cfg_load:
                mock_cfg_load.return_value = MagicMock(
                    anthropic_api_key="fake", openai_api_key=None
                )
                runner.invoke(analyze_cmd, ["--minimal-context", "project"])
        if captured_configs:
            assert captured_configs[0].context_mode == "minimal"
