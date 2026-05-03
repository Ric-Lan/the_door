"""Schema check — validates LLM output against JSON schemas."""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema

from the_door.models import CheckResult


# Load schemas once at module level
_SCHEMAS_DIR = Path(__file__).parent.parent.parent.parent.parent / "schemas"
_L1_SCHEMA_PATH = _SCHEMAS_DIR / "l1-output.schema.json"
_L1_5_SCHEMA_PATH = _SCHEMAS_DIR / "l1-5-output.schema.json"
_L2_SCHEMA_PATH = _SCHEMAS_DIR / "l2-output.schema.json"


class SchemaCheck:
    """Validate LLM output against JSON schemas."""

    def __init__(self):
        with open(_L1_SCHEMA_PATH) as f:
            self._l1_schema = json.load(f)
        with open(_L1_5_SCHEMA_PATH) as f:
            self._l1_5_schema = json.load(f)
        with open(_L2_SCHEMA_PATH) as f:
            self._l2_schema = json.load(f)
        self._validator_cls = jsonschema.Draft202012Validator

    def check(self, llm_output: dict) -> CheckResult:
        """Validate llm_output against l1-output.schema.json."""
        return self._validate_against(llm_output, self._l1_schema)

    def check_l1_5(self, llm_output: dict) -> CheckResult:
        """Validate llm_output against l1-5-output.schema.json."""
        return self._validate_against(llm_output, self._l1_5_schema)

    def check_l2(self, llm_output: dict) -> CheckResult:
        """Validate llm_output against l2-output.schema.json."""
        return self._validate_against(llm_output, self._l2_schema)

    def _validate_against(self, data: dict, schema: dict) -> CheckResult:
        """Validate data against a schema. Returns CheckResult."""
        validator = self._validator_cls(schema)
        errors = []
        for error in sorted(validator.iter_errors(data), key=lambda e: list(e.path)):
            path = ".".join(str(p) for p in error.absolute_path) or "(root)"
            errors.append(f"{path}: {error.message}")

        return CheckResult(passed=len(errors) == 0, errors=errors)
