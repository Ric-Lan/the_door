"""Tier 0 — pure-local structural localization of data-model touch points."""
from __future__ import annotations

import os
from pathlib import Path

from the_door.models import ExtractionResult
from the_door.core.datamodel.models import DataModelCandidate, DataModelLocalization
from the_door.core.datamodel.datamodel_hints import code_site_reason, schema_file_reason


class DataModelLocalizer:
    """Locate persistence-suspect code nodes + declared schema files. Zero token, read-only."""

    def localize(self, result: ExtractionResult, codebase_path: str) -> DataModelLocalization:
        code: list[DataModelCandidate] = []
        for node in result.nodes:
            reason = code_site_reason(node.name, node.file)
            if reason is not None:
                code.append(DataModelCandidate(
                    node_id=node.node_id, file=node.file,
                    kind="code_site", flagged_reason=reason,
                ))

        schema: list[DataModelCandidate] = []
        root = Path(codebase_path)
        for dirpath, _dirs, files in os.walk(root):
            for fname in files:
                rel = os.path.relpath(os.path.join(dirpath, fname), root)
                rel_norm = rel.replace("\\", "/")
                reason = schema_file_reason(rel_norm)
                if reason is not None:
                    schema.append(DataModelCandidate(
                        node_id="", file=rel_norm,
                        kind="schema_file", flagged_reason=reason,
                    ))

        return DataModelLocalization(
            code_candidates=tuple(code),
            schema_candidates=tuple(sorted(schema, key=lambda c: c.file)),
        )
