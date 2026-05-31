import asyncio

from the_door.mcp.tools import localize_datamodel_tool


def _make_project(tmp_path):
    md = tmp_path / "models"
    md.mkdir()
    (md / "user.py").write_text("def save_user(name):\n    return name\n", encoding="utf-8")
    (tmp_path / "init.sql").write_text("CREATE TABLE u(id int);\n", encoding="utf-8")
    return tmp_path


def test_localize_happy(tmp_path):
    _make_project(tmp_path)
    result = asyncio.run(localize_datamodel_tool.execute({"codebase_path": str(tmp_path)}))
    code_files = {c["file"] for c in result["code_candidates"]}
    schema_files = {c["file"] for c in result["schema_candidates"]}
    assert any("user.py" in f for f in code_files)
    assert "init.sql" in schema_files
    assert "next_actions" in result          # envelope injected


def test_localize_missing_path():
    result = asyncio.run(localize_datamodel_tool.execute({}))
    assert "error" in result
