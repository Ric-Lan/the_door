"""Packaging regression: JSON schemas must ship inside the import package.

Root cause of the v1.7.0 bug: schemas lived at `the_door/schemas/` (outside the
package) and code resolved them via `Path(__file__).parent*5/"schemas"` — works
in the dev/editable layout, breaks when pip-installed (overshoots into Lib/).

P-1 pins that schemas resolve via `importlib.resources.files("the_door")`
(robust dev + installed). P-2 pins the packaging config so the wheel/sdist
actually include them. The true wheel-inclusion is gated by the manual install
verification (spec T6a) — P-1 in dev only pins path resolution, not packaging.
"""
from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path

import pytest

SCHEMA_NAMES = [
    "ast-raw.schema.json",
    "diff-result.schema.json",
    "doubt-record.schema.json",
    "l1-5-output.schema.json",
    "l1-output.schema.json",
    "l2-output.schema.json",
    "narrative.schema.json",
    "scope-definition.schema.json",
    "snapshot.schema.json",
    "timeline-result.schema.json",
    "update-report.schema.json",
]

_PYPROJECT = Path(__file__).resolve().parents[2] / "pyproject.toml"
_MANIFEST = Path(__file__).resolve().parents[2] / "MANIFEST.in"


@pytest.mark.parametrize("name", SCHEMA_NAMES)
def test_p1_schema_resolvable_via_package_resources(name):
    """P-1: every schema resolves under the_door package + is valid JSON."""
    res = files("the_door") / "schemas" / name
    assert res.is_file(), f"schema not packaged inside the_door: {name}"
    json.loads(res.read_text(encoding="utf-8"))  # raises if invalid


def test_p2_pyproject_declares_schema_package_data():
    """P-2: pyproject package-data includes schemas/*.json (wheel inclusion)."""
    text = _PYPROJECT.read_text(encoding="utf-8")
    assert "[tool.setuptools.package-data]" in text
    assert "schemas/*.json" in text


def test_p2_manifest_includes_schemas():
    """P-2: MANIFEST.in includes the schemas dir (sdist inclusion)."""
    assert _MANIFEST.is_file(), "MANIFEST.in missing"
    assert "schemas" in _MANIFEST.read_text(encoding="utf-8")
