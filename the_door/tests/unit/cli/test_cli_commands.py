"""Unit tests for CLI commands — extract, validate, mcp-serve."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from click.testing import CliRunner

from the_door.cli.main import main


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def fixtures_dir():
    return Path(__file__).resolve().parents[2] / "fixtures"


@pytest.fixture
def sample_codebase(fixtures_dir):
    return str(fixtures_dir / "sample_codebases" / "python_simple")


@pytest.fixture
def valid_l1_output(fixtures_dir):
    return str(fixtures_dir / "sample_l1_output" / "valid_output.json")


@pytest.fixture
def sample_structure_json(fixtures_dir):
    return str(fixtures_dir / "sample_structure_json" / "python_simple.json")


class TestExtractCommand:
    """Tests for the `extract` CLI command."""

    def test_extract_valid_path_produces_json(self, runner, sample_codebase):
        """Test: extract command with valid path produces JSON output."""
        result = runner.invoke(main, ["extract", sample_codebase])
        assert result.exit_code == 0
        output = json.loads(result.output)
        assert "files" in output
        assert "nodes" in output
        assert "edges" in output
        assert "topology" in output

    def test_extract_invalid_path_shows_error(self, runner):
        """Test: extract command with invalid path shows error, exit code 1."""
        result = runner.invoke(main, ["extract", "/nonexistent/path/to/codebase"])
        assert result.exit_code == 1
        assert "Error" in result.output or "Error" in (result.stderr_bytes or b"").decode()

    def test_extract_output_to_file(self, runner, sample_codebase, tmp_path):
        """Test: extract command with -o flag writes to file."""
        output_file = str(tmp_path / "output.json")
        result = runner.invoke(main, ["extract", sample_codebase, "-o", output_file])
        assert result.exit_code == 0
        assert Path(output_file).exists()
        data = json.loads(Path(output_file).read_text())
        assert "nodes" in data


class TestValidateCommand:
    """Tests for the `validate` CLI command."""

    def test_validate_valid_inputs(self, runner, valid_l1_output, sample_structure_json):
        """Test: validate command with valid inputs produces validation result."""
        result = runner.invoke(main, ["validate", valid_l1_output, sample_structure_json])
        output = json.loads(result.output)
        assert "passed" in output
        assert "schema" in output
        assert "coverage" in output
        assert "language" in output
        assert "anchor" in output
        assert "relation" in output

    def test_validate_missing_argument(self, runner):
        """Test: validate command with missing argument shows usage message."""
        result = runner.invoke(main, ["validate"])
        assert result.exit_code != 0
        # Click shows usage/error when required args are missing
        assert "Usage" in result.output or "Error" in result.output or "Missing" in result.output

    def test_validate_nonexistent_file(self, runner):
        """Test: validate command with nonexistent file shows error."""
        result = runner.invoke(main, ["validate", "/nonexistent/llm.json", "/nonexistent/struct.json"])
        assert result.exit_code == 1


class TestMcpServeCommand:
    """Tests for the `mcp-serve` CLI command."""

    def test_mcp_serve_registered(self, runner):
        """Test: mcp-serve command is registered in the CLI group."""
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "mcp-serve" in result.output

    def test_all_commands_registered(self, runner):
        """Test: all three commands are registered."""
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "extract" in result.output
        assert "validate" in result.output
        assert "mcp-serve" in result.output
