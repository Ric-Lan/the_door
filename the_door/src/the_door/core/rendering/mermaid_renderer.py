"""Mermaid renderer — generate Mermaid flowchart text from L1 and L1.5 output."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from the_door.core.rendering.mermaid_utils import escape_mermaid_label
from the_door.models import (
    Feature,
    FeatureRelation,
    L1Output,
    L1_5Block,
    L1_5Output,
    BlockRelation,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Confidence Marker Definitions
# ============================================================================


@dataclass(frozen=True)
class MarkerDef:
    """Visual definition for a single confidence marker state."""

    name: str  # classDef name in Mermaid
    icon: str  # Unicode prefix for node label
    fill: str  # CSS fill color
    stroke: str  # CSS stroke color
    stroke_dasharray: str | None  # None = solid
    stroke_width: int  # px
    display_label: str  # Human-readable label for JSON


MARKER_DEFS: dict[str, MarkerDef] = {
    "high": MarkerDef("high", "✓", "#d4edda", "#28a745", None, 2, "high confidence"),
    "medium": MarkerDef("medium", "?", "#fff3cd", "#ffc107", "5 5", 2, "medium confidence"),
    "low": MarkerDef("low", "⚠", "#f8d7da", "#dc3545", "2 2", 2, "low confidence"),
    "reviewed": MarkerDef("reviewed", "✔", "#cce5ff", "#007bff", None, 3, "source-reviewed"),
    "regenerated": MarkerDef("regenerated", "Δ", "#e8d5f5", "#6f42c1", "10 5 2 5", 2, "regenerated, differs from previous"),
    "incomplete": MarkerDef("incomplete", "…", "#e9ecef", "#6c757d", "2 2", 2, "incomplete reading"),
}


def resolve_marker_state(
    feature: Feature,
    *,
    regenerated_differs: bool = False,
    incomplete_reading: bool = False,
) -> str:
    """Return the MARKER_DEFS key for the active marker state.

    Priority (highest first): incomplete > regenerated > reviewed > base confidence.
    """
    if incomplete_reading:
        return "incomplete"
    if regenerated_differs:
        return "regenerated"
    if feature.source_reviewed:
        return "reviewed"
    return feature.confidence


def build_confidence_marker(
    feature: Feature,
    regenerated_differs: bool = False,
    incomplete_reading: bool = False,
) -> dict:
    """Build the confidence_marker JSON object for a feature."""
    state = resolve_marker_state(
        feature,
        regenerated_differs=regenerated_differs,
        incomplete_reading=incomplete_reading,
    )
    return {
        "confidence": feature.confidence,
        "source_reviewed": feature.source_reviewed,
        "regenerated_differs": regenerated_differs,
        "incomplete_reading": incomplete_reading,
        "display_label": MARKER_DEFS[state].display_label,
    }


class MermaidRenderer:
    """Generate Mermaid flowchart text from L1 and L1.5 output."""

    def render_l1(
        self,
        l1_output: L1Output,
        *,
        marker_context: dict[str, dict[str, bool]] | None = None,
        show_legend: bool = False,
        vulnerability_border_styles: dict[str, str] | None = None,
    ) -> str:
        """Generate Mermaid flowchart from L1 features and relations."""
        lines: list[str] = ["flowchart TD"]

        if not l1_output.features:
            lines.append('    empty["No features identified"]')
            return "\n".join(lines)

        # Style definitions from MARKER_DEFS
        lines.append("    %% Confidence-based styling")
        for key, mdef in MARKER_DEFS.items():
            parts = [f"fill:{mdef.fill}", f"stroke:{mdef.stroke}"]
            if mdef.stroke_dasharray:
                parts.append(f"stroke-dasharray:{mdef.stroke_dasharray}")
            if mdef.stroke_width != 2:
                parts.append(f"stroke-width:{mdef.stroke_width}")
            lines.append(f"    classDef {key} {','.join(parts)}")
        lines.append("")

        # Feature IDs for validation
        feature_ids = {f.feature_id for f in l1_output.features}

        # Track present states for legend
        present_states: set[str] = set()

        # Nodes
        for feature in l1_output.features:
            # Resolve marker state
            ctx = (marker_context or {}).get(feature.feature_id, {})
            state = resolve_marker_state(
                feature,
                regenerated_differs=ctx.get("regenerated_differs", False),
                incomplete_reading=ctx.get("incomplete_reading", False),
            )
            present_states.add(state)

            marker = MARKER_DEFS[state]
            label = self._escape_label(feature.label)
            trigger = self._escape_label(feature.trigger_description)
            node_label = f"{marker.icon} {label}<br/><i>{trigger}</i>"
            lines.append(f'    {feature.feature_id}["{node_label}"]')
            lines.append(f"    class {feature.feature_id} {state}")

        lines.append("")

        # Edges
        for rel in l1_output.feature_relations:
            if rel.from_feature not in feature_ids or rel.to_feature not in feature_ids:
                logger.warning(
                    f"Skipping relation with non-existent feature: "
                    f"{rel.from_feature} -> {rel.to_feature}"
                )
                continue
            lines.append(f"    {rel.from_feature} --> {rel.to_feature}")

        # Vulnerability classDefs and node overrides
        if vulnerability_border_styles:
            lines.append("")
            lines.append("    %% Vulnerability styling")
            lines.append("    classDef vuln_high fill:#f8d7da,stroke:#dc3545,stroke-width:3")
            lines.append("    classDef vuln_medium fill:#ffe0cc,stroke:#fd7e14,stroke-width:3")
            # Override classDef for affected feature nodes
            for fid, style in vulnerability_border_styles.items():
                if fid in feature_ids:
                    if "dc3545" in style:
                        lines.append(f"    class {fid} vuln_high")
                    elif "fd7e14" in style:
                        lines.append(f"    class {fid} vuln_medium")

        # Conditional legend
        if show_legend:
            legend_lines = self._render_legend(present_states)
            if legend_lines:
                lines.append("")
                lines.extend(legend_lines)

        return "\n".join(lines)

    def _render_legend(self, present_states: set[str]) -> list[str]:
        """Generate legend subgraph lines. Only when non-high states exist."""
        if not (present_states - {"high"}):
            return []

        lines = ['    subgraph Legend["Legend"]']
        for key in ["high", "medium", "low", "reviewed", "regenerated", "incomplete"]:
            if key in present_states:
                marker = MARKER_DEFS[key]
                lines.append(f'        legend_{key}["{marker.icon} {marker.display_label}"]')
                lines.append(f"        class legend_{key} {key}")
        lines.append("    end")
        return lines

    def render_l1_5(self, l1_5_output: L1_5Output) -> str:
        """Generate Mermaid flowchart from L1.5 blocks and relations."""
        lines: list[str] = ["flowchart TD"]

        if not l1_5_output.blocks and not l1_5_output.infrastructure_block:
            lines.append('    empty["No blocks identified"]')
            return "\n".join(lines)

        block_ids = {b.block_id for b in l1_5_output.blocks}

        # Blocks as nodes
        for block in l1_5_output.blocks:
            label = self._escape_label(block.label)
            resp = self._escape_label(block.responsibility)
            node_label = f"{label}<br/><i>{resp}</i>"
            lines.append(f'    {block.block_id}["{node_label}"]')

        lines.append("")

        # Block relations as edges
        for rel in l1_5_output.block_relations:
            if rel.from_block in block_ids and rel.to_block in block_ids:
                lines.append(f"    {rel.from_block} --> {rel.to_block}")

        # Infrastructure block as subgraph
        if l1_5_output.infrastructure_block and l1_5_output.infrastructure_block.components:
            lines.append("")
            infra = l1_5_output.infrastructure_block
            lines.append(f'    subgraph Infrastructure["{self._escape_label(infra.label)}"]')
            for i, comp in enumerate(infra.components):
                safe_id = f"infra_{i}"
                lines.append(f'        {safe_id}["{self._escape_label(comp)}"]')
            lines.append("    end")

        return "\n".join(lines)

    def _escape_label(self, text: str) -> str:
        """Escape Mermaid-unsafe characters in labels."""
        return escape_mermaid_label(text)
