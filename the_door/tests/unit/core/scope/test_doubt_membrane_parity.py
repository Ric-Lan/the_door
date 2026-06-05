"""J3：每值意義單一來源——schema description == doubt_membrane gloss（逐字）。"""
import json
from pathlib import Path

from the_door.core.scope import doubt_membrane as dm

_SCHEMA = json.loads(
    (Path(__file__).parents[4] / "schemas" / "doubt-record.schema.json").read_text(encoding="utf-8")
)


def _oneof_map(node):
    return {b["const"]: b["description"] for b in node["oneOf"]}


def test_current_state_schema_matches_gloss():
    m = _oneof_map(_SCHEMA["properties"]["current_state"])
    assert m == dm._STATE_GLOSS


def test_doubt_type_schema_matches_gloss():
    m = _oneof_map(_SCHEMA["properties"]["doubt_type"])
    assert m == dm._TYPE_GLOSS


def test_resolution_type_schema_matches_gloss():
    node = _SCHEMA["properties"]["resolution"]["oneOf"][1]["properties"]["type"]
    assert _oneof_map(node) == dm._RESOLUTION_GLOSS
