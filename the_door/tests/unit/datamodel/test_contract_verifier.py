from the_door.core.datamodel.models import DeclaredField, CodeTouch
from the_door.core.datamodel.contract_verifier import ContractVerifier


def _status_map(diff):
    return {(e.entity, e.field): e.status for e in diff.entries}


def test_match_write_gap_coverage_gap():
    declared = {"User": [DeclaredField("id"), DeclaredField("name")]}
    touched = [CodeTouch(op="write", entity="User", fields=("name", "email"))]
    diff = ContractVerifier().verify(declared, touched)
    sm = _status_map(diff)
    assert sm[("User", "name")] == "match"
    assert sm[("User", "email")] == "write_gap"      # code writes undeclared field
    assert sm[("User", "id")] == "coverage_gap"        # declared, never touched


def test_entity_only_declared_and_only_touched():
    declared = {"Order": [DeclaredField("total")]}
    touched = [CodeTouch(op="read", entity="Cart", fields=("count",))]
    diff = ContractVerifier().verify(declared, touched)
    sm = _status_map(diff)
    assert sm[("Order", "total")] == "coverage_gap"
    assert sm[("Cart", "count")] == "write_gap"


def test_empty_inputs():
    diff = ContractVerifier().verify({}, [])
    assert diff.entries == ()


def test_multiple_touches_same_entity_union_fields():
    declared = {"User": [DeclaredField("a")]}
    touched = [
        CodeTouch(op="write", entity="User", fields=("a",)),
        CodeTouch(op="read", entity="User", fields=("b",)),
    ]
    sm = _status_map(ContractVerifier().verify(declared, touched))
    assert sm[("User", "a")] == "match"
    assert sm[("User", "b")] == "write_gap"


def test_entries_deterministic_order():
    declared = {"B": [DeclaredField("y")], "A": [DeclaredField("x")]}
    diff = ContractVerifier().verify(declared, [])
    entities = [e.entity for e in diff.entries]
    assert entities == sorted(entities)  # entity 排序穩定
