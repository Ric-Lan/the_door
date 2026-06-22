import pytest
from click.testing import CliRunner

from the_door.cli.main import main


@pytest.fixture()
def simple(fixtures_dir):
    return str(fixtures_dir / "sample_codebases" / "python_simple")


def test_cli_search(simple):
    r = CliRunner().invoke(main, ["locate", "search", "login", "--codebase-path", simple])
    assert r.exit_code == 0
    assert "app.py::login" in r.output


def test_cli_node(simple):
    r = CliRunner().invoke(
        main, ["locate", "node", "auth.py::authenticate_user", "--codebase-path", simple])
    assert r.exit_code == 0
    assert "callers:" in r.output
    assert "app.py::login" in r.output


def test_cli_search_missing_artifacts(tmp_path):
    r = CliRunner().invoke(main, ["locate", "search", "x", "--codebase-path", str(tmp_path)])
    assert r.exit_code != 0
    assert "extract_structure" in r.output


def test_cli_help_registered():
    r = CliRunner().invoke(main, ["locate", "--help"])
    assert r.exit_code == 0
    assert "search" in r.output and "node" in r.output
