# Requirements Document — Confidence Markers Visual Specification (Phase 0b)

## Introduction

Phase 0b defines the visual specification for confidence markers in The Door's Mermaid output and JSON output. Confidence markers communicate the trustworthiness of LLM-generated interpretations to non-technical stakeholders.

**核心驗收標準（來自 Spec v4.1）：** 非工程師能區分「這個標記代表需要追問」vs「這個標記代表可信任」。

**二分法映射：**
- **可信任（綠色系）：** high confidence, source-reviewed
- **需追問（非綠色系）：** medium, low, regenerated-differs, incomplete

This spec extends the existing Mermaid styling (high/medium/low border colors) to cover all four marker states, and standardizes the JSON output format for downstream consumption.

**Scope boundary:** This spec covers Mermaid rendering and JSON format only. CLI text formatting is out of scope (CLI outputs JSON; human-readable display is the AI medium's responsibility per spec §5.3).

## Glossary

- **Base_Confidence**: The primary confidence level (high, medium, low) assigned during analysis
- **Source_Reviewed**: Node was re-analyzed after reviewing original source code (confidence upgraded)
- **Regenerated_Differs**: Node was re-analyzed and the new result differs from previous (temporary state until user accepts)
- **Incomplete_Reading**: Node was not fully analyzed because batch limit was reached

## Requirements

### Requirement 1: Marker State Priority

**User Story:** As a non-technical user, I want each node to display exactly one confidence marker, so that I am not confused by overlapping indicators.

#### Acceptance Criteria

1. Each node SHALL display exactly one marker at a time
2. Priority order (highest to lowest): Incomplete_Reading, Regenerated_Differs, Source_Reviewed, Base_Confidence
3. JSON output SHALL preserve all applicable boolean states regardless of which one is visually displayed
4. Regenerated_Differs is a temporary state — it is cleared when the user accepts the new result (via `--accept` flag)

### Requirement 2: Mermaid Visual Encoding

**User Story:** As a non-technical user viewing a Mermaid diagram, I want to quickly distinguish trustworthy nodes from uncertain ones using visual cues that don't rely on color alone.

#### Acceptance Criteria

1. Each marker state SHALL be differentiated by three independent channels: fill color, border style, and text icon prefix
2. Visual encoding table:

| State | Fill | Border | Icon | classDef name |
|---|---|---|---|---|
| high | #d4edda (green) | solid, stroke:#28a745 | ✓ | `high` |
| medium | #fff3cd (yellow) | dashed (5 5), stroke:#ffc107 | ? | `medium` |
| low | #f8d7da (red) | dotted (2 2), stroke:#dc3545 | ⚠ | `low` |
| source-reviewed | #cce5ff (blue) | solid, stroke:#007bff, stroke-width:3 | ✔ | `reviewed` |
| regenerated-differs | #e8d5f5 (purple) | dash-dot (10 5 2 5), stroke:#6f42c1 | Δ | `regenerated` |
| incomplete | #e9ecef (grey) | dotted (2 2), stroke:#6c757d | … | `incomplete` |

3. Icon SHALL be prepended to the node label text (e.g., `"✓ User sign-in"`)
4. Colors SHALL be fixed and never reused across states

### Requirement 3: JSON Output Marker Format

**User Story:** As a developer consuming The Door's JSON output, I want confidence states to be machine-readable so downstream tools can render their own visual indicators.

#### Acceptance Criteria

1. Each feature in JSON output SHALL include a `confidence_marker` object:
   ```json
   {
     "confidence": "high|medium|low",
     "source_reviewed": false,
     "regenerated_differs": false,
     "incomplete_reading": false,
     "display_label": "high confidence"
   }
   ```
2. `display_label` SHALL contain the human-readable label for the active (highest-priority) state
3. `confidence_reason` (already exists on Feature) SHALL continue to explain why the confidence level was assigned

### Requirement 4: Mermaid Legend (Conditional)

**User Story:** As a first-time viewer, I want a legend when the diagram contains non-obvious states, so I can interpret the visual encoding.

#### Acceptance Criteria

1. Legend SHALL be generated only when the diagram contains at least one node with medium, low, source-reviewed, regenerated, or incomplete state
2. Legend SHALL NOT be generated when all nodes are high confidence (the common case for well-understood codebases)
3. Legend SHALL appear as a Mermaid subgraph at the bottom, showing only the states present in the current diagram
4. Legend generation SHALL be suppressible via a `show_legend=False` parameter

### Requirement 5: Accessibility

**User Story:** As a user with color vision deficiency, I want to distinguish confidence levels without relying on color alone.

#### Acceptance Criteria

1. Each state SHALL be distinguishable by border style alone (solid vs dashed vs dotted vs dash-dot)
2. Each state SHALL have a unique text icon prefix visible in the node label
3. The combination of border style + icon SHALL be sufficient to identify the state without color information

## Non-Requirements (Explicitly Out of Scope)

- CLI text renderer with ANSI colors (CLI outputs JSON; AI medium handles display)
- Marker transition history tracking (covered by existing narrative chain)
- Animated transitions between states
- Custom user-defined color themes
- Mermaid tooltip/subtitle text (inconsistent renderer support)
