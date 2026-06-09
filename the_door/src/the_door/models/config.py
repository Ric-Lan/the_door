"""LLM response-parsing data models.

Provider configuration models (TheDoorConfig / CostEstimate) were removed in
T5-A (丙案): The Door's terminal state has no API-key interface — the single
path is agent-as-LLM (extract_structure → snapshot_write), so there is no
provider/api-key/cost configuration to model.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ParseResult:
    """Result of parsing an LLM response."""

    success: bool = False
    data: dict | None = None
    raw_text: str = ""
    error: str | None = None


# ============================================================================
# Phase 2: Diff Engine models
# ============================================================================
