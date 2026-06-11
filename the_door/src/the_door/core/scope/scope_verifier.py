"""Scope verification engine — pure function comparison + file I/O utilities.

Compares a ScopeDefinition against L1Output to classify each feature into
one of three scope states: in_scope_complete, out_of_scope, in_scope_incomplete.
"""
from __future__ import annotations

import json
import re
from importlib.resources import files
from pathlib import Path
from typing import TYPE_CHECKING

import jsonschema

from the_door.models import (
    DoubtRecord,
    L1Output,
    ScopeCounts,
    ScopeDefinition,
    ScopeDefinitionError,
    ScopeEntry,
    ScopeFeatureEntry,
    ScopeResult,
)

if TYPE_CHECKING:
    from the_door.core.scope.doubt_store import DoubtStore

# ---------------------------------------------------------------------------
# Schema loading — same pattern as core/validation/schema_check.py
# ---------------------------------------------------------------------------
_SCHEMAS_DIR = files("the_door") / "schemas"
_SCOPE_DEF_SCHEMA_PATH = _SCHEMAS_DIR / "scope-definition.schema.json"


def _load_scope_schema() -> dict:
    """Load the scope-definition JSON schema (cached at module level)."""
    with _SCOPE_DEF_SCHEMA_PATH.open(encoding="utf-8") as f:
        return json.load(f)


_scope_schema: dict | None = None


def _get_scope_schema() -> dict:
    """Return the cached scope-definition schema, loading on first access."""
    global _scope_schema  # noqa: PLW0603
    if _scope_schema is None:
        _scope_schema = _load_scope_schema()
    return _scope_schema


# ---------------------------------------------------------------------------
# ScopeVerifier — pure function comparison engine
# ---------------------------------------------------------------------------


class ScopeVerifier:
    """範圍比對引擎。

    ``verify()`` is a **pure function** (no I/O): given a ScopeDefinition and
    an L1Output it produces a deterministic ScopeResult.
    """

    def verify(
        self,
        scope_def: ScopeDefinition,
        l1_output: L1Output,
    ) -> ScopeResult:
        """Compare *scope_def* against *l1_output* and classify every feature.

        Classification rules (by ``feature_id`` string equality):
        - present in **both** → ``in_scope_complete`` (✓)
        - present only in L1Output → ``out_of_scope`` (⚠)
        - present only in ScopeDefinition → ``in_scope_incomplete`` (○)

        Returns a :class:`ScopeResult` containing all :class:`ScopeEntry`
        records and aggregate :class:`ScopeCounts`.
        """
        # Build lookup maps
        scope_features: dict[str, ScopeFeatureEntry] = {
            sf.feature_id: sf for sf in scope_def.features
        }
        l1_features: dict[str, str] = {
            f.feature_id: f.label for f in l1_output.features
        }

        scope_ids = set(scope_features.keys())
        l1_ids = set(l1_features.keys())

        entries: list[ScopeEntry] = []

        # Features in both → in_scope_complete
        for fid in sorted(scope_ids & l1_ids):
            entries.append(
                ScopeEntry(
                    feature_id=fid,
                    scope_state="in_scope_complete",
                    feature_label=l1_features[fid],
                    expected_label=scope_features[fid].expected_label,
                )
            )

        # Features only in L1 → out_of_scope
        for fid in sorted(l1_ids - scope_ids):
            entries.append(
                ScopeEntry(
                    feature_id=fid,
                    scope_state="out_of_scope",
                    feature_label=l1_features[fid],
                    expected_label=None,
                )
            )

        # Features only in scope_def → in_scope_incomplete
        for fid in sorted(scope_ids - l1_ids):
            entries.append(
                ScopeEntry(
                    feature_id=fid,
                    scope_state="in_scope_incomplete",
                    feature_label=None,
                    expected_label=scope_features[fid].expected_label,
                )
            )

        counts = ScopeCounts(
            in_scope_complete=sum(
                1 for e in entries if e.scope_state == "in_scope_complete"
            ),
            out_of_scope=sum(
                1 for e in entries if e.scope_state == "out_of_scope"
            ),
            in_scope_incomplete=sum(
                1 for e in entries if e.scope_state == "in_scope_incomplete"
            ),
        )

        return ScopeResult(
            scope_name=scope_def.scope_name,
            entries=entries,
            counts=counts,
        )

    def verify_and_create_doubts(
        self,
        scope_def: ScopeDefinition,
        l1_output: L1Output,
        doubt_store: DoubtStore,
    ) -> tuple[ScopeResult, list[DoubtRecord]]:
        """Execute scope verification and auto-create doubt records (orchestration, has I/O side effects).

        1. Call verify() to get ScopeResult
        2. For each out_of_scope entry: check doubt_store.has_active_doubt(),
           if no active doubt exists, create_doubt(doubt_type="out_of_scope",
           source_node=feature_id, created_by="scope_verification")
        3. For each in_scope_incomplete entry: same, doubt_type="in_scope_incomplete"
        4. Return (ScopeResult, list of newly created DoubtRecords)
        """
        result = self.verify(scope_def, l1_output)

        new_doubts: list[DoubtRecord] = []

        for entry in result.entries:
            if entry.scope_state not in ("out_of_scope", "in_scope_incomplete"):
                continue

            if doubt_store.has_active_doubt(entry.feature_id, entry.scope_state):
                continue

            doubt = doubt_store.create_doubt(
                source_node=entry.feature_id,
                doubt_type=entry.scope_state,
                created_by="scope_verification",
            )
            new_doubts.append(doubt)

        return (result, new_doubts)


# ---------------------------------------------------------------------------
# File I/O utilities
# ---------------------------------------------------------------------------


def parse_scope_definition(file_path: Path) -> ScopeDefinition:
    """Parse a Scope Definition JSON file into a :class:`ScopeDefinition`.

    Steps:
    1. Read file with ``encoding="utf-8"``
    2. ``json.loads`` — catch :class:`json.JSONDecodeError` →
       :class:`ScopeDefinitionError` with file path and error details
    3. ``jsonschema.validate`` against ``scope-definition.schema.json`` —
       catch :class:`jsonschema.ValidationError` →
       :class:`ScopeDefinitionError`
    4. Convert to :class:`ScopeDefinition` dataclass

    Raises:
        ScopeDefinitionError: on parse or validation failure.
    """
    path = Path(file_path)
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ScopeDefinitionError(str(path), f"Cannot read file: {exc}") from exc

    # JSON parse
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ScopeDefinitionError(
            str(path),
            f"Malformed JSON: {exc}",
        ) from exc

    # Schema validation
    schema = _get_scope_schema()
    try:
        jsonschema.validate(data, schema, cls=jsonschema.Draft202012Validator)
    except jsonschema.ValidationError as exc:
        raise ScopeDefinitionError(
            str(path),
            f"Schema validation failed: {exc.message}",
        ) from exc

    # Convert to dataclass
    features = [
        ScopeFeatureEntry(
            feature_id=f["feature_id"],
            expected_label=f.get("expected_label"),
        )
        for f in data["features"]
    ]
    return ScopeDefinition(
        scope_name=data["scope_name"],
        features=features,
        description=data.get("description"),
    )


def serialize_scope_definition(scope_def: ScopeDefinition) -> dict:
    """Serialize a :class:`ScopeDefinition` to a JSON-compatible dict.

    Suitable for round-trip: ``parse → serialize → json.dumps → json.loads →
    parse`` should yield an equivalent object.
    """
    result: dict = {
        "scope_name": scope_def.scope_name,
        "features": [
            {
                k: v
                for k, v in [
                    ("feature_id", f.feature_id),
                    ("expected_label", f.expected_label),
                ]
                if v is not None
            }
            for f in scope_def.features
        ],
    }
    if scope_def.description is not None:
        result["description"] = scope_def.description
    return result


def scope_name_to_filename(scope_name: str) -> str:
    """Convert a scope name to a kebab-case filename component.

    Rules:
    - Lowercase
    - Replace spaces and underscores with hyphens
    - Strip non-alphanumeric characters except hyphens
    - Collapse consecutive hyphens

    Example::

        >>> scope_name_to_filename("Sprint 12")
        'sprint-12'
    """
    name = scope_name.lower()
    name = re.sub(r"[\s_]+", "-", name)
    name = re.sub(r"[^a-z0-9-]", "", name)
    name = re.sub(r"-{2,}", "-", name)
    name = name.strip("-")
    return name


def resolve_scope_path(scope_ref: str, project_root: Path) -> Path:
    """Resolve a scope reference to an actual file path.

    If *scope_ref* is an existing file path, return it directly.
    Otherwise treat it as a scope name and look in
    ``<project_root>/.the-door/scopes/<kebab-name>.json``.

    Raises:
        FileNotFoundError: if the resolved path does not exist.
    """
    # Direct file path?
    candidate = Path(scope_ref)
    if candidate.is_file():
        return candidate

    # Treat as scope name
    kebab = scope_name_to_filename(scope_ref)
    scopes_dir = project_root / ".the-door" / "scopes"
    resolved = scopes_dir / f"{kebab}.json"
    if resolved.is_file():
        return resolved

    raise FileNotFoundError(
        f"Scope definition not found: tried '{scope_ref}' as file path "
        f"and '{resolved}' as scope name lookup"
    )
