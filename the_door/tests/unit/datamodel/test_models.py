from the_door.core.datamodel.models import (
    DataModelCandidate, DataModelLocalization,
    DeclaredField, CodeTouch, ContractEntry, ContractDiff,
)


def test_candidate_and_localization():
    c = DataModelCandidate(node_id="m1", file="models/user.py",
                           kind="code_site", flagged_reason="name contains 'save'")
    loc = DataModelLocalization(code_candidates=(c,), schema_candidates=())
    assert loc.code_candidates[0].node_id == "m1"
    assert loc.schema_candidates == ()


def test_declared_field_optional_type():
    assert DeclaredField(field="name").type is None
    assert DeclaredField(field="age", type="int").type == "int"


def test_code_touch_and_contract():
    t = CodeTouch(op="write", entity="User", fields=("name", "age"))
    assert t.fields == ("name", "age")
    diff = ContractDiff(entries=(
        ContractEntry(entity="User", field="name", status="match", detail="ok"),
    ))
    assert diff.entries[0].status == "match"


def test_dataclasses_are_frozen():
    import dataclasses
    import pytest
    c = DataModelCandidate(node_id="x", file="f", kind="code_site", flagged_reason="r")
    with pytest.raises(dataclasses.FrozenInstanceError):
        c.file = "y"  # type: ignore[misc]
