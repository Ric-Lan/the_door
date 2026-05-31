import json

from the_door.core.datamodel.models import (
    DataModelCandidate, DataModelLocalization, ContractEntry, ContractDiff,
)
from the_door.core.datamodel.datamodel_renderer import (
    render_localization, contract_diff_to_json,
)


def test_render_localization_with_candidates():
    loc = DataModelLocalization(
        code_candidates=(DataModelCandidate("m1", "models/u.py", "code_site", "name contains 'save'"),),
        schema_candidates=(DataModelCandidate("", "init.sql", "schema_file", "schema file (.sql)"),),
    )
    out = render_localization(loc)
    assert "Code candidates: 1" in out
    assert "m1" in out and "models/u.py" in out
    assert "Schema candidates: 1" in out
    assert "init.sql" in out


def test_render_localization_empty():
    out = render_localization(DataModelLocalization())
    assert "未偵測到資料模型觸點" in out


def test_contract_diff_to_json_roundtrip():
    diff = ContractDiff(entries=(
        ContractEntry("User", "name", "match", "declared and touched"),
    ))
    parsed = json.loads(contract_diff_to_json(diff))
    assert parsed["entries"][0] == {
        "entity": "User", "field": "name", "status": "match", "detail": "declared and touched",
    }
