from click.testing import CliRunner

from the_door.cli.verify_datamodel_cmd import verify_datamodel_cmd


def _make_project(tmp_path):
    models_dir = tmp_path / "models"
    models_dir.mkdir()
    (models_dir / "user.py").write_text("def save_user(name):\n    return name\n", encoding="utf-8")
    (tmp_path / "init.sql").write_text("CREATE TABLE u(id int);\n", encoding="utf-8")
    return tmp_path


def test_default_runs_tier0(tmp_path):
    _make_project(tmp_path)
    result = CliRunner().invoke(verify_datamodel_cmd, [str(tmp_path)])
    assert result.exit_code == 0
    assert "Data-Model Localization (Tier 0)" in result.output
    assert "name contains 'save'" in result.output  # code candidate reason (deterministic)
    assert "init.sql" in result.output              # schema candidate (relpath)
    assert "Next (Tier 1" not in result.output      # no --deep


def test_deep_lists_candidate_files_and_instructions(tmp_path):
    _make_project(tmp_path)
    result = CliRunner().invoke(verify_datamodel_cmd, [str(tmp_path), "--deep"])
    assert result.exit_code == 0
    assert "Next (Tier 1" in result.output
    assert "read: init.sql" in result.output
    assert "verify_data_model_contract" in result.output
