"""LLM / configuration data models."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TheDoorConfig:
    """Parsed configuration for The Door one-click mode."""

    default_provider: str = "openai"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o"
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-4-20250514"
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:8b"
    max_retries: int = 3
    timeout_seconds: int = 120
    cost_warning_threshold: float = 1.00


@dataclass
class CostEstimate:
    """Estimated API cost for a codebase analysis."""

    total_input_tokens: int = 0
    total_output_tokens: int = 0
    estimated_cost_usd: float = 0.0
    provider: str = ""
    model: str = ""
    batch_count: int = 0
    is_local: bool = False


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
