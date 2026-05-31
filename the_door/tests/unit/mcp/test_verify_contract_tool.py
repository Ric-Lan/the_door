import asyncio
import json

from the_door.mcp.tools import verify_contract_tool


def _args(tmp_path):
    return {
        "codebase_path": str(tmp_path),
        "declared_model": {"User": [{"field": "id", "type": "int"}, {"field": "name"}]},
        "code_touched_model": [{"op": "write", "entity": "User", "fields": ["name", "email"]}],
    }


def test_verify_happy_writes_report(tmp_path):
    result = asyncio.run(verify_contract_tool.execute(_args(tmp_path)))
    assert result["summary"] == {"write_gap": 1, "coverage_gap": 1, "match": 1}
    report = tmp_path / ".the-door" / "datamodel" / "contract.json"
    assert report.exists()
    parsed = json.loads(report.read_text(encoding="utf-8"))
    statuses = {(e["field"], e["status"]) for e in parsed["entries"]}
    assert ("email", "write_gap") in statuses
    assert ("id", "coverage_gap") in statuses
    assert ("name", "match") in statuses
    assert "next_actions" in result


def test_verify_missing_path():
    result = asyncio.run(verify_contract_tool.execute(
        {"declared_model": {}, "code_touched_model": []}))
    assert "error" in result


def test_verify_declared_not_dict(tmp_path):
    result = asyncio.run(verify_contract_tool.execute(
        {"codebase_path": str(tmp_path), "declared_model": [], "code_touched_model": []}))
    assert "error" in result


def test_verify_touched_not_list(tmp_path):
    result = asyncio.run(verify_contract_tool.execute(
        {"codebase_path": str(tmp_path), "declared_model": {}, "code_touched_model": {}}))
    assert "error" in result


def test_verify_malformed_field_set(tmp_path):
    # declared field dict missing required "field" key → caught, returns error
    result = asyncio.run(verify_contract_tool.execute({
        "codebase_path": str(tmp_path),
        "declared_model": {"User": [{"type": "int"}]},
        "code_touched_model": [],
    }))
    assert "error" in result
